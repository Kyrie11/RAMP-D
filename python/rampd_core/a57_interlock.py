"""Fail-closed supervisor for declared planned closure controller.
Require an independent current barrier registry while blocked. The existing
controller's authorization is not physical evidence. No automatic reopening
on intrusion or registry loss. A new fault recovery procedure is required.
"""
from .a53b_interlock import advance_interlock,BarrierAck

def advance_monitored(report,state,observation,*,tick,clearance,ack=None,registry=None):
    if state.phase=='BLOCKED':
        if not observation.complete or not observation.empty:
            raise RuntimeError('UNKNOWN: intrusion or unavailable protected-region coverage; maintain interlock, operator recovery required')
        if not isinstance(registry,BarrierAck) or not registry.settled or registry.physical_state!='PRESENT' or (registry.event_id,registry.version,registry.resource_id,registry.command_id,registry.time)!=(state.event_id,state.version,state.resource_id,state.command_id,observation.end):
            raise RuntimeError('UNKNOWN: barrier registry missing/stale; maintain interlock')
    return advance_interlock(report,state,observation,tick=tick,clearance=clearance,ack=ack)

from dataclasses import dataclass,replace
from .a53b_interlock import WorkZoneInterlock

@dataclass(frozen=True)
class ClosureMonitor:
    """Immutable latched supervisory state. Caller must retain returned state.
    Faulted state blocks both entry/stay commands; no physical evacuation or
    reset procedure is implied and no ordinary tick can clear the fault.
    """
    state:WorkZoneInterlock
    fault:str|None=None
    @property
    def permissions(self):
        # A monitor fault revokes NEW entry, but must not silently revoke a
        # preexisting incumbent's right to clear a resource during DRAIN.
        # Safe evacuation remains a separate physical/control obligation.
        return (False,self.state.permissions[1]) if self.fault else self.state.permissions
    def step(self,report,observation,**kw):
        if self.fault:return self
        try:return ClosureMonitor(advance_monitored(report,self.state,observation,**kw))
        except (RuntimeError,ValueError) as e:return replace(self,fault=f'{type(e).__name__}: {e}')
