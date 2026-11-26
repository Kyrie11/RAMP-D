"""Incident mechanism and TIM clocks; not a simulator or safety certificate.

Physical hazard, authority decisions and ego observations are independent
record types. Missing timestamps remain unknown, never imputed as zero.
The TIM clock ordering below applies to this explicitly chosen reference
mechanism (reactive incident management), not every possible jurisdiction.
"""
from dataclasses import dataclass
from fractions import Fraction
from .permission_schedule import exact

KINDS={'DISABLED_VEHICLE','ROAD_DEBRIS','CRASH','ENVIRONMENT_OBSTRUCTION'}
CAUSES={'EXOGENOUS_TRIGGER','TRAFFIC_DEPENDENT','UNKNOWN'}

@dataclass(frozen=True)
class IncidentEvent:
    incident_id: str
    kind: str
    cause: str
    trigger: Fraction
    resource_ids: tuple[str,...]
    mechanism_ref: str
    seed_ref: str
    def __post_init__(self):
        ids=tuple(sorted(self.resource_ids));object.__setattr__(self,'resource_ids',ids)
        if (not all((self.incident_id,self.mechanism_ref,self.seed_ref)) or self.kind not in KINDS or self.cause not in CAUSES or
                not ids or any(not isinstance(k,str) or not k for k in ids) or len(set(ids))!=len(ids)):
            raise ValueError('incident mechanism, identity, scope and provenance required')
        exact(self.trigger)
    def external_signature(self):
        # This is a candidate invariance key for a FIXED mechanism/draw, not
        # causal identification. A collision caused by traffic must not use it.
        if self.cause!='EXOGENOUS_TRIGGER': return None
        return (self.incident_id,self.kind,self.trigger,self.resource_ids,self.mechanism_ref,self.seed_ref)

@dataclass(frozen=True)
class IncidentTimeline:
    incident: IncidentEvent
    cutoff: Fraction
    hazard_on: Fraction | None = None
    first_authority_awareness: Fraction | None = None
    verification: Fraction | None = None
    dispatch: Fraction | None = None
    responder_arrival: Fraction | None = None
    blocked_lane_physically_clear: Fraction | None = None
    lanes_available: Fraction | None = None
    last_responder_left: Fraction | None = None
    normal_flow: Fraction | None = None
    evidence_ref: str = ''
    response_profile: str = 'VERIFY_THEN_DISPATCH'
    incident_occurrence: Fraction | None = None  # FHWA T0, not assumed equal to trigger
    tim_sequential_clearance_profile: bool = False  # optional reference mechanism, not universal
    def __post_init__(self):
        exact(self.cutoff)
        if not self.evidence_ref or self.cutoff<self.incident.trigger: raise ValueError('timeline evidence/cutoff required')
        names=('incident_occurrence','hazard_on','first_authority_awareness','verification','dispatch','responder_arrival','blocked_lane_physically_clear','lanes_available','last_responder_left','normal_flow')
        for k in names:
            t=getattr(self,k)
            if t is not None and not self.incident.trigger<=exact(t)<=self.cutoff: raise ValueError(f'{k} outside observation window')
        def ordered(a,b):
            x,y=getattr(self,a),getattr(self,b)
            if x is not None and y is not None and x>y: raise ValueError(f'{b} precedes {a}')
        # Awareness could precede physical lane blockage (e.g. a reported
        # developing breakdown); local ego awareness is not in this timeline.
        from itertools import combinations
        if self.response_profile=='VERIFY_THEN_DISPATCH':
            for a,b in combinations(('first_authority_awareness','verification','dispatch','responder_arrival'),2): ordered(a,b)
        elif self.response_profile=='PARALLEL_DISPATCH':
            for k in ('verification','dispatch','responder_arrival'): ordered('first_authority_awareness',k)
            ordered('dispatch','responder_arrival')
        else: raise ValueError('unknown response profile')
        if type(self.tim_sequential_clearance_profile) is not bool: raise ValueError('explicit reference profile required')
        if self.tim_sequential_clearance_profile:
            ordered('incident_occurrence','hazard_on')
            ordered('last_responder_left','normal_flow')
        ordered('incident_occurrence','first_authority_awareness')
        ordered('incident_occurrence','normal_flow')
        ordered('hazard_on','normal_flow')
        ordered('blocked_lane_physically_clear','normal_flow')
        ordered('hazard_on','blocked_lane_physically_clear')
        ordered('blocked_lane_physically_clear','lanes_available')
        ordered('first_authority_awareness','lanes_available')
        ordered('first_authority_awareness','last_responder_left')
        ordered('responder_arrival','last_responder_left')
        ordered('lanes_available','normal_flow')
        if self.lanes_available is not None and (self.hazard_on is None or self.blocked_lane_physically_clear is None):
            raise ValueError('lane reopening requires observed physical blocker clearance in this mechanism')
    def duration(self, endpoint):
        if endpoint not in ('lanes_available','last_responder_left','normal_flow'): raise ValueError('unrecognized TIM endpoint')
        # T5-T1 and T6-T1 are RCT/ICT. T7-T0 is time to return to normal flow.
        start=self.incident_occurrence if endpoint=='normal_flow' else self.first_authority_awareness
        end=getattr(self,endpoint)
        # Missing log is unknown, not necessarily right-censored. No
        # assumption of continuous logging/monitoring is made here.
        return None if start is None or end is None else end-start

@dataclass(frozen=True)
class IncidentRuleRecord:
    incident_id: str
    resource_id: str
    authority: str
    jurisdiction: str
    version: int
    effective_on: Fraction
    effective_off: Fraction | None
    issue: Fraction | None
    receipt: Fraction | None
    local_detection: Fraction | None
    alpha: bool
    beta: bool
    source_ref: str
    publication: Fraction | None = None
    def __post_init__(self):
        exact(self.effective_on)
        if not all((self.incident_id,self.resource_id,self.authority,self.jurisdiction,self.source_ref)) or type(self.version) is not int or self.version<0 or type(self.alpha) is not bool or type(self.beta) is not bool:
            raise ValueError('explicit authority, scope and permissions required')
        for t in (self.effective_off,self.issue,self.receipt,self.local_detection,self.publication):
            if t is not None: exact(t)
        if self.effective_off is not None and self.effective_off<=self.effective_on: raise ValueError('invalid rule interval')
        if self.receipt is not None and (self.issue is None or self.receipt<self.issue): raise ValueError('receipt without preceding issue')
        if self.publication is not None and (self.issue is None or self.publication<self.issue or (self.receipt is not None and self.receipt<self.publication)):
            raise ValueError('publication clock inconsistent with issue/receipt')
    def audit(self,timeline):
        if self.incident_id!=timeline.incident.incident_id or self.resource_id not in timeline.incident.resource_ids:
            raise ValueError('incident and rule scope mismatch')
        # Reactive response: authority cannot activate or issue an incident
        # rule before its declared awareness. No restriction between issue
        # and effectivity, or between local detection and message receipt.
        if timeline.first_authority_awareness is None: raise ValueError('authority awareness not recorded')
        if self.effective_on<timeline.first_authority_awareness or (self.issue is not None and self.issue<timeline.first_authority_awareness): raise ValueError('rule precedes authority awareness')
        if self.local_detection is not None and self.local_detection<timeline.incident.trigger: raise ValueError('local incident detection precedes trigger')
        if any(t is not None and t>timeline.cutoff for t in (self.issue,self.publication,self.receipt,self.local_detection)): raise ValueError('recorded observation after cutoff')
        return True
