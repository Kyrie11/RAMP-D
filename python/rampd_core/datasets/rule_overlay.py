"""Declared synthetic rule overlay; never changes real logged motion targets.
A rule proposal is not authoritative physical geometry or a simulator outcome.
"""
from dataclasses import dataclass
from fractions import Fraction as Q
from .split_manifest import canonical_digest

KINDS=('LANE_CLOSURE','ALTERNATING_DIRECTION','TEMPORARY_SPEED_LIMIT','STOP_SLOW')

def _time(v):
    if type(v) not in (str,int,Q): raise ValueError('use exact seconds as string/int/Fraction')
    q=Q(v)
    if q<0: raise ValueError('negative clock')
    return q

@dataclass(frozen=True)
class RuleOverlay:
    scenario_id: str
    record_sha256: str
    event_id: str
    lane_id: str
    kind: str
    generation: str
    effective_on: str
    effective_off: str
    issue: str
    receipt: str | None
    authority: str
    seed: int
    announce_window: bool = False
    def __post_init__(self):
        if (not all((self.scenario_id,self.event_id,self.lane_id,self.authority)) or self.kind not in KINDS
            or len(self.record_sha256)!=64 or any(c not in '0123456789abcdef' for c in self.record_sha256)
            or type(self.seed) is not int or type(self.announce_window) is not bool): raise ValueError('invalid event identity')
        g,on,off,i=map(_time,(self.generation,self.effective_on,self.effective_off,self.issue))
        if not g<=on<off or i<g or (self.receipt is not None and _time(self.receipt)<i): raise ValueError('invalid scheduled-rule/message clocks')
    def bind(self, record):
        s=record['scene']; m=s['manifest']; mc=s.get('map_context') or {}
        if m['scenario_id']!=self.scenario_id or record['record_sha256']!=self.record_sha256 or mc.get('scenario_id')!=self.scenario_id or mc.get('coordinate_frame')!=m['coordinate_frame']:
            raise ValueError('overlay source mismatch')
        if self.lane_id not in {str(p['feature_id']) for p in mc.get('primitives',[]) if p['kind']=='lane' and p['vertices']}:
            raise ValueError('overlay lane not present in base map')
        ts=m['timestamps']; start,end=Q(str(ts[0])),Q(str(ts[-1]))
        if _time(self.effective_on)>end or _time(self.effective_off)<=start: raise ValueError('overlay does not intersect logged time span')
        return dict(schema='rampd.rule_overlay.v1',event=dict(self.__dict__),event_digest=canonical_digest(self.__dict__),domain='SYNTHETIC_SCENARIO_SPEC_ONLY',joint_counterfactual_mask=False,all_training_masks=False,physical_resource_verified=False,scenario_time_span=[str(start),str(end)],off_beyond_log_window=_time(self.effective_off)>end,actual_execution='NOT_RUN')
    def public_view(self, cutoff):
        t=_time(cutoff)
        # No event identity, timestamps, lane or type before receipt. Silence is not negative evidence.
        if self.receipt is None or _time(self.receipt)>t: return {'received_messages': []}
        msg=dict(event_id=self.event_id,lane_id=self.lane_id,kind=self.kind,authority=self.authority,issue=self.issue,receipt=self.receipt)
        if self.announce_window: msg['announced_window']=[self.effective_on,self.effective_off]
        return {'received_messages':[msg]}  # actual effectivity not inferred from message
    def teacher_active(self, t):
        return _time(self.effective_on)<=_time(t)<_time(self.effective_off)

@dataclass(frozen=True)
class ScheduledDelivery:
    """One recipient's synthetic delivery. None means no delivery in this world,
    not a real-world negative observation or confirmed packet drop."""
    recipient: str
    publication: str
    receipt: str | None
    def validate(self, event):
        if not self.recipient or _time(self.publication)<_time(event.issue): raise ValueError('publication before issue or missing recipient')
        if self.receipt is not None and _time(self.receipt)<_time(self.publication): raise ValueError('receipt before publication')
    def public_view(self,event,cutoff):
        self.validate(event)
        if self.receipt is None or _time(self.receipt)>_time(cutoff): return {'received_messages': []}
        msg=dict(event_id=event.event_id,lane_id=event.lane_id,kind=event.kind,authority=event.authority,issue=event.issue,publication=self.publication,receipt=self.receipt)
        if event.announce_window: msg['announced_window']=[event.effective_on,event.effective_off]
        return {'received_messages':[msg]}


def replay_scheduled_world(record,event,deliveries,*,query_steps=30):
    """Future-only declared schedule replay. Does NOT simulate vehicle response.
    All worlds share the factual initialization; no hidden event changes its past.
    Teacher clock targets are for the declared schedule only, not physical ACK.
    """
    if type(query_steps) is not int or query_steps<1: raise ValueError('query_steps')
    s=record['scene'];m=s['manifest']; cutoff=_time(str(m['timestamps'][m['current_time_index']]))
    binding=event.bind(record)
    if _time(event.generation)<cutoff: raise ValueError('event history not regenerated: require generation >= decision cutoff')
    deliveries=tuple(deliveries)
    if not deliveries or len({d.recipient for d in deliveries})!=len(deliveries): raise ValueError('unique recipient deliveries required')
    if len({ _time(d.publication) for d in deliveries})!=1: raise ValueError('one report publication clock required')
    valid_roster={str(a['track_id']) for a in s['tracks'] if a['states'][m['current_time_index']]['valid'] is True}
    for d in deliveries:
        d.validate(event)
        if d.recipient not in valid_roster: raise ValueError('recipient outside current valid roster')
    if event.receipt is not None: raise ValueError('use recipient-specific receipts, not legacy ego receipt')
    ticks=[cutoff+Q(j,10) for j in range(query_steps+1)]
    rows=[]
    for t in ticks:
        rows.append(dict(time=str(t),public_by_recipient={d.recipient:d.public_view(event,t) for d in deliveries},teacher=dict(rule_active=event.teacher_active(t),rule_generated=t>=_time(event.generation),physical_execution='UNKNOWN',response='NOT_RUN')))
    # No event is a separate declared alternative, never a deduction from silence.
    no_event=[dict(time=str(t),public_by_recipient={d.recipient:{'received_messages':[]} for d in deliveries},teacher=dict(rule_active=False,rule_generated=False,physical_execution='UNKNOWN',response='NOT_RUN')) for t in ticks]
    return dict(schema='rampd.scheduled_rule_replay.v1',binding=binding,decision_time=str(cutoff),split=m['split'],family_id=m['scenario_id'],source_digest=record['record_sha256'],deliveries=[dict(d.__dict__) for d in deliveries],worlds={'EVENT':rows,'NO_EVENT':no_event},teacher_schedule=dict(generation=event.generation,effective_on=event.effective_on,effective_off=event.effective_off,issue=event.issue,publication=deliveries[0].publication,physical_activation=None,physical_clearance=None,first_local_detection=None),scope='DECLARED_SYNTHETIC_SCHEDULE_NOT_SIMULATOR_RESPONSE',event_training_allowed=False,joint_counterfactual_mask=False,formal_sc=False)
