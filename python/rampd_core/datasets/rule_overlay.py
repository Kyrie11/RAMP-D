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
