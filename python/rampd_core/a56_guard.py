"""Finite tick-actuated signal support. Exact integers and rational time.

The caller supplies a complete *declared* joint relation of flow and evidence
for each latent parent. This module does not infer it from sampled trajectories,
certify detector coverage, or implement continuous physical Post/SC.
"""
from dataclasses import dataclass
from itertools import product
from .a54_signal import SignalController
from .workzone_rule_models import FlowSnapshot
from .a53b_interlock import ClearanceObservation

@dataclass(frozen=True)
class GuardCase:
    case_id: str
    flow: FlowSnapshot
    clearance: ClearanceObservation
    public_observations: tuple[str, ...] = ('silence',)
    switch_ready: bool = True
    def __post_init__(self):
        if isinstance(self.public_observations,str):raise ValueError("public observations must be a collection")
        o=tuple(self.public_observations)
        object.__setattr__(self,'public_observations',o)
        if not isinstance(self.case_id,str) or not self.case_id or not isinstance(self.flow,FlowSnapshot) or not isinstance(self.clearance,ClearanceObservation):
            raise ValueError('scoped joint guard case required')
        if type(self.switch_ready) is not bool:raise ValueError('explicit switch readiness required')
        if not o or any(not isinstance(x,str) or not x for x in o) or len(set(o))!=len(o):
            raise ValueError('nonempty unique public observation relation required')

@dataclass(frozen=True)
class GuardParent:
    world_id: str
    controller: SignalController
    cases: tuple[GuardCase,...]
    def __post_init__(self):
        cases=tuple(self.cases);object.__setattr__(self,'cases',cases)
        if not isinstance(self.world_id,str) or not self.world_id or not isinstance(self.controller,SignalController) or not cases or any(not isinstance(x,GuardCase) for x in cases) or len({x.case_id for x in cases})!=len(cases):
            raise ValueError('unique nonempty cases per parent required')

@dataclass(frozen=True)
class GuardSuccessor:
    parent_id: str
    case_id: str
    controller: SignalController
    flow: FlowSnapshot
    clearance: ClearanceObservation
    switch_ready: bool


def advance_support(parents, *, max_cases=100000):
    """Enumerate all declared joint cases, retain memory and observation preimage.

    Same public label => same information cell; hidden IDs never become labels.
    A case may yield several public labels (nondeterministic observation). No
    filtering by likelihood, nor independent recombination of correlated worlds.
    Limit overflow raises rather than truncating. Controller output is a result
    of the guard, not an ego action; caller must propagate one common ego action.
    """
    parents=tuple(parents)
    if not parents or any(not isinstance(p,GuardParent) for p in parents) or len({p.world_id for p in parents})!=len(parents):raise ValueError('nonempty unique support parents required')
    if type(max_cases) is not int or max_cases<1 or sum(len(c.public_observations) for p in parents for c in p.cases)>max_cases:raise ValueError('guard support budget exceeded; no sound result')
    c0=parents[0].controller
    if any((p.controller.last_tick,p.controller.controller_id,p.controller.version,p.controller.resource_id,p.controller.plan)!=(c0.last_tick,c0.controller_id,c0.version,c0.resource_id,c0.plan) for p in parents):raise ValueError('inconsistent shared clock/controller contract')
    cells={};transitions={}
    for p in parents:
        for case in p.cases:
            c=p.controller.advance(case.flow,case.clearance,switch_ready=case.switch_ready)
            out=GuardSuccessor(p.world_id,case.case_id,c,case.flow,case.clearance,case.switch_ready)
            transitions[(p.world_id,case.case_id)]=c.phase!=p.controller.phase
            for observation in case.public_observations:cells.setdefault(observation,[]).append(out)
    vals=set(transitions.values())
    return ('MAY' if len(vals)>1 else 'MUST' if True in vals else 'NEVER', {k:tuple(v) for k,v in sorted(cells.items())})


def queue_box_cases(controller, queue_a, queue_b, clearance, *, occupants, public_observations=('silence',), switch_ready=True, max_cases=100000):
    """Cartesian integer queue intervals only where independence is declared.
    For correlated counts use explicit GuardCase tuples instead. Does not
    assume a clearance sensor is truthful/complete without upstream evidence.
    """
    def limits(x):
        lo,hi=x
        if type(lo) is not int or type(hi) is not int or not 0<=lo<=hi:raise ValueError('invalid integer interval')
        return lo,hi
    alo,ahi=limits(queue_a);blo,bhi=limits(queue_b)
    if type(max_cases) is not int or max_cases<1 or (ahi-alo+1)*(bhi-blo+1)>max_cases:raise ValueError('guard support budget exceeded')
    t=controller.last_tick+controller.plan.tick
    return tuple(GuardCase(f'{a}:{b}',FlowSnapshot(t,a,b,occupants),clearance,public_observations,switch_ready) for a,b in product(range(alo,ahi+1),range(blo,bhi+1)))
