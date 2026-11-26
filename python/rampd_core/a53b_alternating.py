"""Reference two-direction interlock with scoped interval clearance evidence.

This is not a certified signal controller; it intentionally does not model
yellow/dilemma zones, detector error, conflicting authorities, power loss,
or real signal-head layout. No sampled count alone can reopen the resource.
"""
from dataclasses import dataclass, replace
from fractions import Fraction
from .workzone_rule_models import AlternatingConfig, AlternatingState, FlowSnapshot
from .a53b_interlock import ClearanceObservation


@dataclass(frozen=True)
class ContinuousAlternating:
    controller_id: str
    version: int
    resource_id: str
    config: AlternatingConfig
    state: AlternatingState
    def __post_init__(self):
        if not self.controller_id or not self.resource_id or type(self.version) is not int or self.version<0 or not isinstance(self.config,AlternatingConfig) or not isinstance(self.state,AlternatingState):
            raise ValueError('bound controller identity/configuration/state required')
    @classmethod
    def initial(cls,controller_id,version,resource_id,config,time=Fraction(0),direction='A'):
        if direction not in ('A','B'): raise ValueError('unknown direction')
        return cls(controller_id,version,resource_id,config,AlternatingState(direction+'_GREEN',time,time))

    def advance(self, flow: FlowSnapshot, clearance: ClearanceObservation):
        s=self.state; c=self.config; t=flow.time
        if (t!=s.last_tick+c.tick or (clearance.start,clearance.end)!=(s.last_tick,t) or
            (clearance.event_id,clearance.version,clearance.resource_id)!=(self.controller_id,self.version,self.resource_id)):
            raise ValueError('mismatched scoped clearance evidence or tick')
        if clearance.complete and clearance.empty and flow.occupants!=0:
            raise ValueError('detector and complete clearance evidence disagree; reconcile')
        direction=s.phase[0]; same,opp=(flow.queue_a,flow.queue_b) if direction=='A' else (flow.queue_b,flow.queue_a)
        if s.phase.endswith('_GREEN'):
            elapsed=t-s.phase_since
            if elapsed>=c.min_green and opp>0 and (opp-same>=c.queue_advantage or elapsed>=c.max_green):
                # Do not count prior GREEN time as a closed-entry clearance period.
                return replace(self,state=AlternatingState(direction+'_DRAIN',t,t))
            return replace(self,state=replace(s,last_tick=t))
        empty=(s.empty_since if s.empty_since is not None else clearance.start) if clearance.complete and clearance.empty else None
        if empty is not None and t-empty>=c.clearance:
            return replace(self,state=AlternatingState(('B' if direction=='A' else 'A')+'_GREEN',t,t))
        return replace(self,state=replace(s,last_tick=t,empty_since=empty))
