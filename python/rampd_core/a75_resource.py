"""Exact declared affine rectangular resource monitor. Closed-set contact is
conservative occupancy. History carries admitted actors with directions. Full
slab constant permissions with an explicit right-continuous endpoint guard.
If omitted, caller declares permissions constant on the closed slab. No physical ACK inferred from geometric contact.
"""
from fractions import Fraction as Q
from .a73_joint_reference import box,contact,q
from itertools import combinations

def monitor(paths,resource,prior,directions,guard,*,dt,empty_age,clearance=Q(0),endpoint_guard=None):
    dt=q(dt);empty_age=q(empty_age);clearance=q(clearance)
    if dt<=0 or min(empty_age,clearance)<0 or set(paths)!=set(directions) or not set(prior)<=set(paths):raise ValueError('invalid monitor context')
    endpoint_guard=guard if endpoint_guard is None else endpoint_guard
    if any(d not in ('A','B') for d in directions.values()):raise ValueError('invalid direction')
    for g in (guard,endpoint_guard):
        if any(type(g[k]) is not bool for k in ('entry','stay','exit','ack')) or type(g['capacity']) is not int or g['capacity']<0 or not isinstance(g['directions'],(list,tuple)) or any(d not in ('A','B') for d in g['directions']):raise ValueError('invalid guard')
    p=box(resource);spans={a:contact(*v,p,p) for a,v in paths.items()};spans={a:s for a,s in spans.items() if s is not None};errors=[]
    starts={a for a,(l,h) in spans.items() if l==0};ends={a for a,(l,h) in spans.items() if h==1}
    if set(prior)!=starts or any(prior[a]!=directions[a] for a in prior):errors.append('INITIAL_HISTORY_OR_DIRECTION_MISMATCH')
    # An outside->touch counts as entry, even if the footprint leaves within slab.
    entrants={a for a,(l,h) in spans.items() if a not in prior};exits={a for a,(l,h) in spans.items() if h<1}
    for a in entrants:
        l,h=spans[a];d=directions[a]
        g=endpoint_guard if l==1 else guard
        if not g['entry'] or not g['ack'] or d not in g['directions']:errors.append('ENTRY:'+a)
        if any(pd!=d for pd in prior.values()) or (not prior and empty_age+l*dt<clearance):errors.append('CLEARANCE:'+a)
    if any(l<1 for l,h in spans.values()) and not guard['stay']:errors.append('STAY')
    if ends and not endpoint_guard['stay']:errors.append('ENDPOINT_STAY')
    if exits and not guard['exit']:errors.append('EXIT')
    # Opposite directions conflict at any instant, including shared boundary.
    for x in {v for s in spans.values() for v in s}:
        active=[a for a,(l,h) in spans.items() if l<=x<=h]
        if len(active)>(endpoint_guard if x==1 else guard)['capacity']:errors.append('CAPACITY')
        if len({directions[a] for a in active})>1:errors.append('OPPOSING')
    # Even if two opposing vehicles never overlap, require empty dwell after last opposite occupancy.
    for a in entrants:
        l,_=spans[a]
        for b,(_,h) in spans.items():
            if a!=b and directions[a]!=directions[b] and h<l and (l-h)*dt<clearance:errors.append('CLEARANCE:'+a)
    age=Q(0) if ends else (1-max(h for _,h in spans.values()))*dt if spans else empty_age+dt
    return dict(ok=not errors,errors=sorted(set(errors)),entries=sorted(entrants),exits=sorted(exits),spans={a:[str(l*dt),str(h*dt)] for a,(l,h) in spans.items()},end_admitted={a:directions[a] for a in ends},empty_age=age,scope='EXACT_DECLARED_AFFINE_RECTANGLE_ONLY')
