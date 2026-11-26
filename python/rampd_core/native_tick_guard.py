"""2-D native continuous Post to tick guard, for declared complete rosters.
Not a mission verifier: all candidate outcomes carry the full endpoint box,
without using hidden truth for observation splitting. The overapproximate
relation is generated from Picard and Cartesian actor envelopes; queue detector
here means reference/body overlap with a declared rectangle plus speed test.
No actual detector, physical legality, or task progress is certified here.
"""
from dataclasses import dataclass
from itertools import product
from math import prod,isfinite
from .model import ControlBounds,BicycleParameters
from .interval import Interval,square
from .belief import SupportAtom
from .footprint import SweptFootprint,VehicleGeometry
from .resources import ResourceRegion,rectangular_separated,strict_rectangular_overlap
from .actor_response_envelope import actor_keys,propagate_other
from .a54_signal import SignalController
from .a56_guard import GuardCase,GuardParent,advance_support
from .a53b_interlock import ClearanceObservation
from .workzone_rule_models import FlowSnapshot
from .reachability import integrate,TubeStatus
from .certificate import to_dict,replay_certificate
from .native_protocol_replay import exact_step_endpoint,_subslab_box
from .exact_time import binary64_bracket

@dataclass(frozen=True)
class NativeParent:
    atom:SupportAtom
    controller:SignalController
    actor_models:tuple
    # Declared public observation relation. Do not equate a hidden phase with observations.
    observations:tuple[str,...]=('silence',)
    readiness:tuple[bool,...]=(False,True)

@dataclass(frozen=True)
class NativeSuccessor:
    parent_id:str
    case_id:str
    atom:SupportAtom
    controller:SignalController
    flow:FlowSnapshot
    clearance:ClearanceObservation
    # Metadata not an independent verification of physical legality.
    common_control:ControlBounds
    switch_ready:bool


def _flags(must,may):return (True,) if must else (False,True) if may else (False,)

def native_post(parents,control,*,params,ego_geometry,disturbance,resource,queue_a,queue_b,queue_speed=.1,options=None,max_cases=100000):
    """Generate finite overapproximation from 2-D continuous enclosures.
    Assumes fixed actor roster, one controller, two disjoint declared queue
    detectors, tick-only changes. Actor counting uses footprint overlap and
    bounded speed (not SUMO stop-bar detector semantics). Uncertain membership
    branches both ways. No pruning on overlap. Returns no partial result on
    failed replay or budget. Endpoint boxes repeat across conservative branches.
    """
    ps=tuple(parents)
    if not ps or len({p.atom.atom_id for p in ps})!=len(ps) or not isinstance(control,ControlBounds) or any(i.lo!=i.hi for i in control.as_tuple()):raise ValueError('common exact point control and unique parents required')
    if not isinstance(params,BicycleParameters) or not isinstance(ego_geometry,VehicleGeometry) or len(disturbance)!=6 or not all(isinstance(d,Interval) for d in disturbance):raise ValueError('explicit model and disturbance required')
    if not all(isinstance(r,ResourceRegion) for r in (resource,queue_a,queue_b)) or len({r.resource_id for r in (resource,queue_a,queue_b)})!=3:raise ValueError('explicit resource and detector geometry required')
    # A body could overlap both zones, so we conservatively enumerate both;
    # caller chooses a detector definition; no exclusive-lane assertion.
    if not isfinite(queue_speed) or queue_speed<=0 or type(max_cases) is not int or max_cases<1:raise ValueError('invalid queue threshold/budget')
    n=0;gparents=[];endpoints={};tubes={}
    for p in ps:
        a,c=p.atom,p.controller;h=c.plan.tick
        if resource.resource_id!=c.resource_id or set(a.other_dict)!=actor_keys(p.actor_models) or not p.readiness or len(set(p.readiness))!=len(p.readiness) or any(type(v) is not bool for v in p.readiness):raise ValueError('bad native parent contract')
        tube=integrate(a.ego,control,params,binary64_bracket(h)[1],options,disturbance)
        if tube.status is not TubeStatus.VALIDATED or not replay_certificate(to_dict(tube)).ok:raise ValueError('physical propagation/replay failed; UNKNOWN')
        x=exact_step_endpoint(tube,h);other=propagate_other(p.actor_models,a,h,h);tubes[a.atom_id]=tube
        endfps=[(SweptFootprint(x,ego_geometry,h,h,'ego'),square(x.v))]
        for m in p.actor_models:
            endfps.append((m.footprint(other,h,h),square(other[m.keys[2]])+square(other[m.keys[3]])))
        thresh=square(Interval.point(queue_speed));flags=[];occ=[]
        for fp,v2 in endfps:
            for detector in (queue_a,queue_b):
                flags.append(_flags(strict_rectangular_overlap(fp,detector) and v2.hi<thresh.lo,not rectangular_separated(fp,detector) and v2.lo<thresh.hi))
            occ.append(_flags(strict_rectangular_overlap(fp,resource),not rectangular_separated(fp,resource)))
        # Every segment must be uniformly separated for definitely-empty.
        # A strictly overlapping box for a segment suffices for definitely-not-empty.
        free=True;must=False;covered=False
        for seg in tube.segments:
            lo,hi=seg.start_time,min(seg.end_time,h)
            if lo>hi:continue
            covered=True;box=_subslab_box(seg,lo,hi);fps=[SweptFootprint(box,ego_geometry,lo,hi,'ego')];others=propagate_other(p.actor_models,a,lo,hi)
            fps.extend(m.footprint(others,lo,hi) for m in p.actor_models)
            free &= all(rectangular_separated(f,resource) for f in fps)
            must |= any(strict_rectangular_overlap(f,resource) for f in fps)
        if not covered:raise ValueError('missing slab coverage')
        empties=(True,) if free else (False,) if must else (False,True)
        n+=prod(map(len,flags+occ))*len(empties)*len(p.readiness)*len(p.observations)
        if n>max_cases:raise ValueError('native guard budget exceeded; UNKNOWN')
        cases=[];t=c.last_tick+h
        for q,o,e,ready in product(product(*flags),product(*occ),empties,p.readiness):
            if e and any(o):continue
            k=str(len(cases));cases.append(GuardCase(k,FlowSnapshot(t,sum(q[::2]),sum(q[1::2]),sum(o)),ClearanceObservation(c.last_tick,t,True,e,'hypothetical native physical guard member',c.controller_id,c.version,c.resource_id),p.observations,ready))
            endpoints[(a.atom_id,k)]=(a,x,other)
        gparents.append(GuardParent(a.atom_id,c,tuple(cases)))
    status,cells=advance_support(gparents,max_cases=max_cases)
    out={}
    for obs,posts in cells.items():
        rows=[]
        for s in posts:
            a,x,other=endpoints[(s.parent_id,s.case_id)]
            # Preserve all original latent mode attributes; phase stored explicitly
            # in successor object, not as public label or a precompiled protocol ID.
            atom=SupportAtom(f'{len(s.parent_id)}:{s.parent_id}:{s.case_id}',x,tuple(other.items()),a.mode)
            rows.append(NativeSuccessor(s.parent_id,s.case_id,atom,s.controller,s.flow,s.clearance,control,s.switch_ready))
        out[obs]=tuple(rows)
    return status,out,tubes
