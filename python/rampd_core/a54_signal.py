"""One-lane two-way reference timing plan (MUTCD 4A.03,4F.17,4O).

Desired indications only, not actual hardware confirmation. Yellow retains the
terminating movement under the chosen US straight-through semantics. Opposing
entry remains blocked until fixed red minimum plus verified contiguous empty
interval. No default universal red clearance time is assumed.
"""
from dataclasses import dataclass, replace
from fractions import Fraction as Q
from .a53_schedule import exact
from .a53_rule_models import FlowSnapshot
from .a53b_interlock import ClearanceObservation

@dataclass(frozen=True)
class SignalPlan:
    tick: Q
    min_green: Q
    max_green: Q
    yellow: Q
    red_min: Q
    empty_min: Q
    queue_advantage: int
    engineering_ref: str
    max_green_extension: Q = Q(0)  # explicit experimental comfort-gate allowance
    def __post_init__(self):
        times=(self.tick,self.min_green,self.max_green,self.yellow,self.red_min,self.empty_min)
        if exact(self.tick)<=0 or (exact(self.max_green_extension)/self.tick).denominator!=1: raise ValueError('invalid green extension')
        if any(exact(t)<=0 for t in times) or self.max_green<self.min_green or any((t/self.tick).denominator!=1 for t in times) or type(self.queue_advantage) is not int or self.queue_advantage<1 or not self.engineering_ref: raise ValueError('positive grid-aligned timing plan and engineering basis required')
    @property
    def yellow_guidance_met(self): return Q(3)<=self.yellow<=Q(6)

@dataclass(frozen=True)
class SignalController:
    controller_id: str
    version: int
    resource_id: str
    plan: SignalPlan
    phase: str
    since: Q
    last_tick: Q
    empty_since: Q|None=None
    def __post_init__(self):
        if not self.controller_id or not self.resource_id or type(self.version) is not int or self.version<0 or not isinstance(self.plan,SignalPlan) or self.phase not in {d+'_'+p for d in 'AB' for p in ('GREEN','YELLOW','RED_CLEAR')} or not exact(self.since)<=exact(self.last_tick): raise ValueError('invalid controller state')
        if self.empty_since is not None and (not self.phase.endswith('RED_CLEAR') or not self.since<=exact(self.empty_since)<=self.last_tick): raise ValueError('invalid continuous clearance state')
    @classmethod
    def initial(cls,controller_id,version,resource_id,plan,time=Q(0),direction='A'):
        # Initial green requires the simulator/operator to establish a cleared facility.
        return cls(controller_id,version,resource_id,plan,direction+'_GREEN',time,time)
    @property
    def displays(self):
        d,p=self.phase.split('_',1); active=p if p in ('GREEN','YELLOW') else 'RED'
        return (active,'RED') if d=='A' else ('RED',active)
    @property
    def permissions(self):
        d,p=self.phase.split('_',1); entry=p!='RED_CLEAR'
        return (entry,True,False,False) if d=='A' else (False,False,entry,True)
    def advance(self,flow:FlowSnapshot,clearance:ClearanceObservation, *, switch_ready=True):
        p=self.plan; t=flow.time
        if type(switch_ready) is not bool: raise ValueError("explicit boolean switch readiness required")
        if t!=self.last_tick+p.tick or (clearance.start,clearance.end)!=(self.last_tick,t) or (clearance.event_id,clearance.version,clearance.resource_id)!=(self.controller_id,self.version,self.resource_id): raise ValueError('wrong tick or scoped evidence')
        empty=clearance.complete and clearance.empty
        if empty and flow.occupants!=0: raise ValueError('clearance conflicts with detector')
        d,phase=self.phase.split('_',1); elapsed=t-self.since
        def fresh(new): return replace(self,phase=new,since=t,last_tick=t,empty_since=None)
        if phase=='GREEN':
            same,opp=(flow.queue_a,flow.queue_b) if d=='A' else (flow.queue_b,flow.queue_a)
            request=elapsed>=p.min_green and opp>0 and (opp-same>=p.queue_advantage or elapsed>=p.max_green)
            if request and switch_ready: return fresh(d+'_YELLOW')
            if request and not switch_ready and elapsed>=p.max_green+p.max_green_extension:
                raise RuntimeError('declared green extension exhausted; no comfortable switching witness')
            return replace(self,last_tick=t)
        if phase=='YELLOW':
            return fresh(d+'_RED_CLEAR') if elapsed>=p.yellow else replace(self,last_tick=t)
        since=(self.empty_since if self.empty_since is not None else clearance.start) if empty else None
        if elapsed>=p.red_min and since is not None and t-since>=p.empty_min:
            return fresh(('B' if d=='A' else 'A')+'_GREEN')
        return replace(self,last_tick=t,empty_since=since)
