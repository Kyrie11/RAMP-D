"""Simulator-facing work-zone interlock. Not a continuous-time proof.

A barrier command is not an acknowledgement. A physical object observation
must have the matching event identity and command generation. Clearance evidence
is an independently supplied complete interval measurement, not two point samples.
"""
from dataclasses import dataclass, replace
from fractions import Fraction
from .permission_schedule import exact
from .workzone_rule_models import ExternalReport


@dataclass(frozen=True)
class ClearanceObservation:
    start: Fraction
    end: Fraction
    complete: bool
    empty: bool
    source_ref: str
    event_id: str = ""
    version: int | None = None
    resource_id: str = ""

    def __post_init__(self):
        if not exact(self.start)<exact(self.end) or not self.source_ref or type(self.complete) is not bool or type(self.empty) is not bool:
            raise ValueError('invalid interval measurement')
        if self.empty and not self.complete:
            raise ValueError('cannot assert empty without complete coverage')
        if not self.event_id or not self.resource_id or type(self.version) is not int or self.version<0:
            raise ValueError('clearance evidence requires event, version and resource identity')


@dataclass(frozen=True)
class BarrierAck:
    event_id: str
    version: int
    resource_id: str
    command_id: str
    time: Fraction
    physical_state: str  # present / absent
    settled: bool        # no outstanding spawn/remove from earlier commands
    source_ref: str

    def __post_init__(self):
        exact(self.time)
        if (not all((self.event_id,self.resource_id,self.command_id,self.source_ref)) or
            type(self.version) is not int or self.version<0 or type(self.settled) is not bool or
            self.physical_state not in ('PRESENT','ABSENT')):
            raise ValueError('invalid physical acknowledgement')


@dataclass(frozen=True)
class WorkZoneInterlock:
    event_id: str
    version: int
    resource_id: str
    phase: str
    last_tick: Fraction
    empty_since: Fraction | None = None
    command_id: str | None = None
    command_time: Fraction | None = None
    report_signature: tuple = ()
    clearance_required: Fraction | None = None

    def __post_init__(self):
        if not self.event_id or not self.resource_id or type(self.version) is not int or self.version<0 or not self.report_signature:
            raise ValueError('invalid work-zone identity or missing report signature')
        exact(self.last_tick)
        if self.clearance_required is not None and exact(self.clearance_required)<=0: raise ValueError("invalid clearance requirement")
        if self.phase not in ('OPEN','DRAIN','DEPLOY_PENDING','BLOCKED','REMOVE_PENDING'):
            raise ValueError('invalid interlock phase')
        if self.empty_since is not None and (self.phase!='DRAIN' or exact(self.empty_since)>self.last_tick):
            raise ValueError('invalid clearance history')
        pending=self.phase in ('DEPLOY_PENDING','BLOCKED','REMOVE_PENDING')
        if pending != (self.command_id is not None and self.command_time is not None):
            raise ValueError('command identity required while barrier lifecycle active')
        if not pending and (self.command_id is not None or self.command_time is not None):
            raise ValueError('unexpected command')
        if pending and exact(self.command_time)>self.last_tick:
            raise ValueError('command in future')

    @classmethod
    def initial(cls, report: ExternalReport, time: Fraction):
        if exact(time)>=report.effective_on:
            raise ValueError('initialize before enforceable closure or restore explicit checkpoint')
        return cls(report.event_id,report.version,report.resource_id,'OPEN',time,report_signature=report.external_request_signature())

    @property
    def permissions(self):
        return {'OPEN':(True,True),'DRAIN':(False,True),
                'DEPLOY_PENDING':(False,False),'BLOCKED':(False,False),
                'REMOVE_PENDING':(False,False)}[self.phase]

    @property
    def requested_command(self):
        return {'DEPLOY_PENDING':'DEPLOY','REMOVE_PENDING':'CANCEL_AND_REMOVE'}.get(self.phase)


def advance_interlock(report, state, observation, *, tick, clearance, ack=None):
    """Advance a specified one-event controller at a synchronized tick.

    `observation` concerns [previous_tick, current_tick]; it must NOT be
    fabricated by comparing two instantaneous occupancies. The controller
    remains closed for missing/stale/failed acknowledgements. The closed
    permission during deployment is intentional; physical absence is separate.
    A new report version is a new reconciliation problem, not silently applied.
    """
    if ((state.event_id,state.version,state.resource_id)!=(report.event_id,report.version,report.resource_id) or
            state.report_signature != report.external_request_signature()):
        raise ValueError('report reconciliation not supplied')
    if (exact(tick)<=0 or exact(clearance)<=0 or observation.start!=state.last_tick or
            observation.end!=state.last_tick+tick):
        raise ValueError('nonconsecutive synchronized measurement')
    if (observation.event_id,observation.version,observation.resource_id)!=(state.event_id,state.version,state.resource_id):
        raise ValueError("clearance evidence scope mismatch")
    if state.clearance_required is not None and state.clearance_required!=clearance:
        raise ValueError("clearance timing plan changed without reconciliation")
    state=replace(state,clearance_required=clearance)
    t=observation.end
    active=report.effective_on<=t<report.effective_off
    # The tick-based reference does not skip a complete sub-tick activation.
    if any(observation.start<switch<t for switch in (report.effective_on,report.effective_off)):
        raise ValueError('effectivity boundary requires split tick')
    def fresh(phase,command=None,empty=None):
        return WorkZoneInterlock(state.event_id,state.version,state.resource_id,phase,t,empty,
                                 None if command is None else f'{state.event_id}:{state.version}:{state.resource_id}:{command}:{t}',
                                 None if command is None else t,state.report_signature,state.clearance_required)
    def acknowledged(physical):
        return (ack is not None and isinstance(ack,BarrierAck) and ack.settled and
                (ack.event_id,ack.version,ack.resource_id,ack.command_id)==
                (state.event_id,state.version,state.resource_id,state.command_id) and
                state.command_time<=ack.time==t and ack.physical_state==physical)
    if state.phase=='OPEN':
        return fresh('DRAIN') if active else fresh('OPEN')
    if state.phase=='DRAIN':
        if not active: return fresh('OPEN')  # no spawn was requested
        since=(state.empty_since if state.empty_since is not None else observation.start) if observation.complete and observation.empty else None
        if since is not None and t-since>=clearance:
            return fresh('DEPLOY_PENDING','deploy')
        return fresh('DRAIN',empty=since)
    if state.phase=='DEPLOY_PENDING':
        if not active or not (observation.complete and observation.empty):
            return fresh('REMOVE_PENDING','cancel-remove')
        if acknowledged('PRESENT'): return replace(state,phase='BLOCKED',last_tick=t)
        return replace(state,last_tick=t)
    if state.phase=='BLOCKED':
        return replace(state,last_tick=t) if active else fresh('REMOVE_PENDING','cancel-remove')
    if acknowledged('ABSENT'):
        # If deployment was aborted by intrusion or missing coverage, restart
        # clearance under the still-active rule; never reopen on that path.
        return fresh('DRAIN') if active else fresh('OPEN')
    return replace(state,last_tick=t)
