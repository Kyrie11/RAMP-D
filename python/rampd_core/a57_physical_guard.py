"""Exact rational, forward 1-D corridor Post/guard reference (not 2-D SC).
Each world carries its complete declared roster, common ego acceleration and
actor acceleration intervals. Independent interval extensions overapproximate
within-world dependencies; no cross-world re-combination or observation pruning.
No proof of real detector coverage or behavior-model completeness is implied.
"""
from dataclasses import dataclass
from fractions import Fraction as Q
from itertools import product
from .a54_signal import SignalController
from .workzone_rule_models import FlowSnapshot
from .a53b_interlock import ClearanceObservation
from .a56_guard import GuardCase,GuardParent,advance_support

@dataclass(frozen=True)
class Box:
    lo: Q
    hi: Q
    def __post_init__(self):
        if type(self.lo) is not Q or type(self.hi) is not Q or self.lo>self.hi: raise ValueError('ordered exact box required')
    def __add__(self,b): return Box(self.lo+b.lo,self.hi+b.hi)
    def scale(self,k):
        if type(k) is not Q or k<0:raise ValueError('nonnegative exact scale required')
        return Box(self.lo*k,self.hi*k)

@dataclass(frozen=True)
class Actor:
    actor_id: str
    direction: str
    front: Box
    speed: Box
    length: Q
    accel: Box
    def __post_init__(self):
        if not self.actor_id or self.direction not in ('A','B') or not all(isinstance(x,Box) for x in (self.front,self.speed,self.accel)) or self.speed.lo<0 or type(self.length) is not Q or self.length<=0:raise ValueError('invalid forward roster actor')

@dataclass(frozen=True)
class World:
    world_id: str
    controller: SignalController
    actors: tuple[Actor,...]
    public_observations: tuple[str,...]=('silence',)
    switch_ready: tuple[bool,...]=(False,True)

@dataclass(frozen=True)
class PostCase:
    parent_id: str
    case_id: str
    controller: SignalController
    actors: tuple[Actor,...]
    flow: FlowSnapshot
    clearance: ClearanceObservation
    # possible crossing/rear-clear, not a task-progress witness
    possible_entries: tuple[str,...]
    possible_exits: tuple[str,...]
    unresolved_permissions: tuple[str,...]
    # stay/entry/exit are separate; absence of flags is scoped to declared model


def step_actor(a,h,common_ego):
    acc=common_ego if a.actor_id=='ego' else a.accel
    end_v=a.speed+acc.scale(h)
    if end_v.lo<0:raise ValueError('reverse or stop transition needs a separate admissible profile')
    end_x=a.front+a.speed.scale(h)+acc.scale(h*h/2)
    return Actor(a.actor_id,a.direction,end_x,end_v,a.length,acc)


def post(worlds,common_ego,*,entry,exit,detector_start,queue_speed=Q(1,10),max_cases=100000,exit_open=(True,True)):
    """Endpoint controller advance after old-phase motion; closed swept interval.
    Possible queue/end occupancy flags are conservatively enumerated; conflicting
    empty/occupied inputs are excluded by construction. Unknown -> no partial Post.
    exit_open applies through the step, independently of entry permissions.
    Public labels are a declared observation relation, not a sensor model.
    """
    worlds=tuple(worlds)
    if not worlds or len({w.world_id for w in worlds})!=len(worlds) or not isinstance(common_ego,Box):raise ValueError('unique world support and common action required')
    if any(type(t) is not Q for t in (entry,exit,detector_start,queue_speed)) or not detector_start<entry<exit or queue_speed<=0 or len(exit_open)!=2 or any(type(x) is not bool for x in exit_open):raise ValueError('invalid corridor geometry')
    if type(max_cases) is not int or max_cases<1:raise ValueError('bad budget')
    gp=[]; payload={};n=0
    for w in worlds:
        actors=tuple(w.actors);ids={a.actor_id for a in actors};h=w.controller.plan.tick
        if len(ids)!=len(actors) or 'ego' not in ids or not w.world_id or not w.switch_ready or any(type(x) is not bool for x in w.switch_ready) or len(set(w.switch_ready))!=len(w.switch_ready):raise ValueError('incomplete or invalid declared roster/readiness')
        ends=tuple(step_actor(a,h,common_ego) for a in actors)
        def flag(must,may):return (True,) if must else (False,True) if may else (False,)
        queues=[]; occs=[]; sweep_free=True; sweep_must=False; pe=[];px=[];bad=[]
        for a,b in zip(actors,ends):
            d='AB'.index(a.direction); ent,stay=w.controller.permissions[2*d:2*d+2]
            # Body spans [front-length, front]. Closed contact counts.
            may_sweep=b.front.hi>=entry and a.front.lo-a.length<=exit
            must_sweep=b.front.lo>=entry and a.front.hi-a.length<=exit
            sweep_free &= not may_sweep; sweep_must |= must_sweep
            may_end=b.front.hi>=entry and b.front.lo-b.length<=exit
            must_end=b.front.lo>=entry and b.front.hi-b.length<=exit
            occs.append(flag(must_end,may_end))
            may_q=b.front.hi>=detector_start and b.front.lo<entry and b.speed.lo<queue_speed
            must_q=b.front.lo>=detector_start and b.front.hi<entry and b.speed.hi<queue_speed
            queues.append(flag(must_q,may_q))
            # Equality is conservatively treated as possible boundary crossing.
            e=a.front.lo<=entry and b.front.hi>=entry
            x=a.front.lo-a.length<=exit and b.front.hi-b.length>=exit
            if e:pe.append(a.actor_id)
            if x:px.append(a.actor_id)
            if (e and not ent) or (may_sweep and not stay) or (x and not exit_open[d]):bad.append(a.actor_id)
        empties=(True,) if sweep_free else (False,) if sweep_must else (False,True)
        # Budget counts raw candidates before allocation and all observation branches.
        from math import prod
        n+=prod(map(len,queues+occs))*len(empties)*len(w.switch_ready)*len(w.public_observations)
        if n>max_cases:raise ValueError('physical guard budget exceeded; UNKNOWN')
        cases=[];t=w.controller.last_tick+h;c=w.controller
        for q,o,empty,ready in product(product(*queues),product(*occs),empties,w.switch_ready):
            if empty and any(o):continue
            if any(qi and oi for qi,oi in zip(q,o)):continue  # front<entry vs front>=entry
            f=FlowSnapshot(t,sum(v and a.direction=='A' for v,a in zip(q,actors)),sum(v and a.direction=='B' for v,a in zip(q,actors)),sum(o))
            ev=ClearanceObservation(c.last_tick,t,True,empty,'declared rational 1-D closed sweep',c.controller_id,c.version,c.resource_id)
            key=str(len(cases));cases.append(GuardCase(key,f,ev,w.public_observations,ready));payload[(w.world_id,key)]=(ends,tuple(pe),tuple(px),tuple(bad))
        gp.append(GuardParent(w.world_id,c,tuple(cases)))
    status,cells=advance_support(gp,max_cases=max_cases)
    return status,{obs:tuple(PostCase(s.parent_id,s.case_id,s.controller,payload[(s.parent_id,s.case_id)][0],s.flow,s.clearance,*payload[(s.parent_id,s.case_id)][1:]) for s in cases) for obs,cases in cells.items()}
