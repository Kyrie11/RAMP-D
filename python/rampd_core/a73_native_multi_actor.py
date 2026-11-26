"""Native multi-actor geometry/Guard screening with independently declared
contexts. Each actor's Picard inclusion is replayed; axis-aligned outer
hulls are orientation-independent. A possible contact is NOT actual contact.
No physical authority, complete external protocol, dynamics-limit or SC claim.
"""
from fractions import Fraction as Q
from itertools import combinations
from .a71_native_polygon_geometry import _q,polygon_vertices,guaranteed_polygon_separation
from .a73_native_context import audit_context


def outer_hull(cert,geometry):
    l,w,ox,oy=map(_q,geometry)
    if l<=0 or w<=0:raise ValueError('invalid footprint')
    r=abs(ox)+abs(oy)+(l+w)/2
    ts=[s['tube'] for s in cert['segments']]
    if not ts:raise ValueError('empty tube')
    xs=[tuple(map(_q,t[0])) for t in ts];ys=[tuple(map(_q,t[1])) for t in ts]
    if any(a>b for a,b in xs+ys):raise ValueError('inverted tube')
    return (min(a for a,b in xs)-r,min(a for a,b in ys)-r,max(b for a,b in xs)+r,max(b for a,b in ys)+r)

def separated(a,b):return a[2]<b[0] or b[2]<a[0] or a[3]<b[1] or b[3]<a[1]

def geometry_guard_screen(certs,geometry,resources,guards,conflicts):
    """All certs here must already be independently verified. This function
    only derives conservative geometry checks. Entire slab hull (not endpoints).
    Every potentially occupying actor counts; possible entry/stay/exit each
    needs permission. Direction must be unrestricted in this reference gate.
    """
    if not certs or set(certs)!=set(geometry) or set(resources)!=set(guards):raise ValueError('roster/guard coverage')
    reasons=[];hulls={a:outer_hull(c,geometry[a]) for a,c in certs.items()};may={}
    for a,b in combinations(sorted(hulls),2):
        if not separated(hulls[a],hulls[b]):reasons.append('POSSIBLE_ACTOR_CONTACT:'+a+':'+b)
    for r,p in resources.items():
        polygon_vertices(p);g=guards[r]
        if type(g['capacity']) is not int or g['capacity']<0:raise ValueError('invalid capacity')
        may[r]=[]
        for a,c in certs.items():
            l,w,ox,oy=geometry[a]
            if any(guaranteed_polygon_separation(s['tube'],p,length_m=l,width_m=w,offset_x_m=ox,offset_y_m=oy)['status']!='DECLARED_TUBE_POLYGON_STRICTLY_SEPARATED' for s in c['segments']):may[r].append(a)
        if may[r] and (not all(g.get(k) is True for k in ('entry','stay','exit','all_directions','ack')) or type(g.get('version')) is not int or g['version']<0 or type(g.get('ack_version')) is not int or g.get('ack_version')!=g['version']):reasons.append('POSSIBLE_CONTACT_WITH_UNRESOLVED_GUARD:'+r)
        if len(may[r])>g['capacity']:reasons.append('POSSIBLE_CAPACITY_VIOLATION:'+r)
    for r,s in conflicts:
        if r==s or r not in may or s not in may:raise ValueError('bad conflict')
        if any(a!=b for a in may[r] for b in may[s]):reasons.append('POSSIBLE_RESOURCE_CONFLICT:'+r+':'+s)
    return dict(reasons=sorted(set(reasons)),may_occupy=may,hulls={a:list(map(str,h)) for a,h in hulls.items()},actual_occupancy_known=False)


def audit_joint_native(certs,declarations,geometry,resources,guard_by_slab,conflicts,worlds,*,start,end,ego,history_events=()):
    """certs[actor][(world,lo,hi)]; declarations are independent input model.
    Each actor has its own disturbance/control envelope (not ego awareness).
    Shared ego controls are checked by value over each public-history class.
    """
    from .certificate import replay_certificate
    from .a61_hybrid_partition import partition_clock_worlds
    clock=partition_clock_worlds(tuple(worlds),start=start,end=end,history_events=tuple(history_events));reasons=list(clock.reasons)
    expected={(w,lo,hi) for lo,hi,groups in clock.posterior_worlds_by_slab for _,ids in groups for w in ids}
    if not expected or not certs or set(certs)!=set(declarations) or set(certs)!=set(geometry) or ego not in certs or set(guard_by_slab)!=expected:reasons.append('MISSING_ROSTER_OR_CLOCK_SUPPORT')
    for a,rows in certs.items():
        if set(rows)!=expected or a not in declarations:reasons.append('ACTOR_WORLD_SLAB_MISSING:'+a);continue
        reasons.extend(a+':'+e for e in audit_context(rows,declarations[a]))
        for k,c in rows.items():
            if not replay_certificate(c).ok:reasons.append('NATIVE_REPLAY_FAILED:'+a+':'+str(k))
    if not reasons:
        for lo,hi,groups in clock.posterior_worlds_by_slab:
            for _,ids in groups:
                values={tuple(tuple(v) for v in certs[ego][(w,lo,hi)]['control']) for w in ids}
                if len(values)!=1:reasons.append('HIDDEN_WORLD_EGO_CONTROL_MISMATCH')
    rows=[]
    if not reasons:
        for k in sorted(expected):
            s=geometry_guard_screen({a:r[k] for a,r in certs.items()},geometry,resources,guard_by_slab[k],conflicts);rows.append(dict(world=k[0],start=str(k[1]),end=str(k[2]),**s));reasons.extend(s['reasons'])
    return dict(status='CONDITIONAL_DECLARED_NATIVE_MULTI_ACTOR_GEOMETRY_GUARD_SCREEN' if not reasons else 'UNKNOWN',reasons=sorted(set(reasons)),rows=rows,expected_actor_slabs=len(expected)*len(geometry),full_sc=False,formal_labels_authorized=False,external_roster_verified=False,dynamics_limits_verified=False,terminal_tail_verified=False)
