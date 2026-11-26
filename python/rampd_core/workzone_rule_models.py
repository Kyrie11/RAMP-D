"""Model-specified work-zone/traffic-actuated rule mechanisms for future simulator use.

These are executable controller reference models, not observed real labels,
not a SUMO/CARLA adapter and not robust safety proofs. Truth-level detector
inputs must later be bound to a particular simulator snapshot and actor set.
"""
from dataclasses import dataclass, replace
from fractions import Fraction
from .permission_schedule import exact


@dataclass(frozen=True)
class ExternalReport:
    event_id: str
    source: str
    jurisdiction: str
    resource_id: str
    version: int
    activation: Fraction
    effective_on: Fraction
    effective_off: Fraction
    issue: Fraction
    receive: Fraction | None
    delivery_status: str
    condition: str
    physical_change: Fraction | None = None

    def __post_init__(self):
        if not all((self.event_id,self.source,self.jurisdiction,self.resource_id,self.condition)) or type(self.version) is not int or self.version<0:
            raise ValueError('event identity/authority/scope/version required')
        for t in (self.activation,self.effective_on,self.effective_off,self.issue): exact(t)
        if self.effective_off<=self.effective_on: raise ValueError('invalid effectivity')
        if self.delivery_status not in ('DELIVERED','PENDING','DROPPED_BY_MODEL'):
            raise ValueError('explicit delivery status required')
        if self.physical_change is not None: exact(self.physical_change)
        if (self.delivery_status=='DELIVERED')!=(self.receive is not None):
            raise ValueError('receipt/status mismatch')
        if self.receive is not None and exact(self.receive)<self.issue:
            raise ValueError('receipt before issue')

    def visible_to_ego(self, t):
        return self.receive is not None and self.receive<=exact(t)

    def external_request_signature(self):
        # Request and external channel draw can be fixed between interventions.
        # Actual deployment may be traffic-mediated, so physical_change is not
        # included in a claim of exogenous invariance.
        return (self.event_id,self.source,self.jurisdiction,self.resource_id,self.version,
                self.activation,self.effective_on,self.effective_off,self.issue,self.condition)


@dataclass(frozen=True)
class FlowSnapshot:
    """Counts at a decision boundary; timestamp is the state observation time.
    An advance() from the preceding boundary controls the *next* interval.
    No direct ego action input; dependence flows through physical state.
    """
    time: Fraction
    queue_a: int
    queue_b: int
    occupants: int

    def __post_init__(self):
        exact(self.time)
        if any(type(x) is not int or x<0 for x in (self.queue_a,self.queue_b,self.occupants)):
            raise ValueError('detector counts must be known nonnegative integers')


@dataclass(frozen=True)
class AlternatingConfig:
    tick: Fraction
    min_green: Fraction
    max_green: Fraction
    clearance: Fraction
    queue_advantage: int

    def __post_init__(self):
        if not (0<exact(self.tick)<=exact(self.min_green)<=exact(self.max_green) and exact(self.clearance)>0):
            raise ValueError('invalid phase timing')
        if type(self.queue_advantage) is not int or self.queue_advantage<1:
            raise ValueError('positive queue hysteresis required')


@dataclass(frozen=True)
class AlternatingState:
    phase: str
    phase_since: Fraction
    last_tick: Fraction
    empty_since: Fraction | None = None

    def __post_init__(self):
        if self.phase not in ('A_GREEN','B_GREEN','A_DRAIN','B_DRAIN') or exact(self.phase_since)>exact(self.last_tick):
            raise ValueError('invalid alternating controller state')
        if self.empty_since is not None:
            if not self.phase.endswith('_DRAIN') or not self.phase_since<=exact(self.empty_since)<=self.last_tick:
                raise ValueError('invalid clearance clock')

    @property
    def permissions(self):
        """(entry A, stay A, entry B, stay B); opposite entry never concurrent."""
        return {'A_GREEN':(True,True,False,False),'B_GREEN':(False,False,True,True),
                'A_DRAIN':(False,True,False,False),'B_DRAIN':(False,False,False,True)}[self.phase]


def advance_alternating(config: AlternatingConfig, state: AlternatingState, flow: FlowSnapshot):
    """Reference traffic-actuated interlock, not real signal timing calibration.

    On a switch request both entries close; current direction may clear.
    Require at least `clearance` of *sampled* empty time before opposite green.
    Unknown detector coverage must be handled by caller as unavailable, not 0.
    Continuous empty between ticks is not established by this controller.
    """
    t=flow.time
    if t!=state.last_tick+config.tick: raise ValueError('nonconsecutive tick')
    direction=state.phase[0]; same,opp=(flow.queue_a,flow.queue_b) if direction=='A' else (flow.queue_b,flow.queue_a)
    if state.phase.endswith('_GREEN'):
        elapsed=t-state.phase_since
        if elapsed>=config.min_green and opp>0 and (opp-same>=config.queue_advantage or elapsed>=config.max_green):
            return AlternatingState(direction+'_DRAIN',t,t,t if flow.occupants==0 else None)
        return replace(state,last_tick=t)
    empty=(state.empty_since if state.empty_since is not None else t) if flow.occupants==0 else None
    if empty is not None and t-empty>=config.clearance:
        return AlternatingState(('B' if direction=='A' else 'A')+'_GREEN',t,t)
    return replace(state,last_tick=t,empty_since=empty)


@dataclass(frozen=True)
class WorkZoneState:
    phase: str
    last_tick: Fraction
    empty_since: Fraction | None = None

    def __post_init__(self):
        if self.phase not in ('OPEN','DRAIN','BLOCKED','RELEASE_PENDING'): raise ValueError('invalid work-zone state')
        exact(self.last_tick)
        if self.empty_since is not None and (self.phase!='DRAIN' or exact(self.empty_since)>self.last_tick):
            raise ValueError('invalid drain clock')

    @property
    def permissions(self):
        return {'OPEN':(True,True),'DRAIN':(False,True),'BLOCKED':(False,False),'RELEASE_PENDING':(False,False)}[self.phase]


def advance_work_zone(report: ExternalReport,state: WorkZoneState, flow: FlowSnapshot, *, tick: Fraction,
                      clearance: Fraction, physical_barrier_removed: bool=False):
    """Planned closure request is external; actual barrier deployment is interlocked.

    `BLOCKED` requests the simulator to deploy a barrier after sampled clearance;
    this does NOT assert that an obstacle was actually spawned. Reopen only after
    explicit removal confirmation. Sudden incidents require a different model.
    """
    if exact(tick)<=0 or exact(clearance)<=0 or flow.time!=state.last_tick+tick or type(physical_barrier_removed) is not bool:
        raise ValueError('invalid work-zone tick or confirmation')
    t=flow.time; active=report.effective_on<=t<report.effective_off
    if state.phase=='OPEN':
        return WorkZoneState('DRAIN',t,t if flow.occupants==0 else None) if active else WorkZoneState('OPEN',t)
    if state.phase=='DRAIN':
        if not active: return WorkZoneState('OPEN',t)
        empty=(state.empty_since if state.empty_since is not None else t) if flow.occupants==0 else None
        if empty is not None and t-empty>=clearance: return WorkZoneState('BLOCKED',t)
        return WorkZoneState('DRAIN',t,empty)
    if active:
        if state.phase=='RELEASE_PENDING': raise ValueError('new request during release needs new event')
        return WorkZoneState('BLOCKED',t)
    return WorkZoneState('OPEN' if physical_barrier_removed else 'RELEASE_PENDING',t)
