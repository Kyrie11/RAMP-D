"""A71 *exact-rational* conservative polygon separation from a 6D native tube.

This deliberately uses an orientation-INDEPENDENT body-radius bound. It loses
precision but never needs to infer unverified heading interpolation or use
ordinary floating-point SAT as a certificate. A fixed axis with strict gap
separates the FULL body outer envelope from a convex hull enclosing any
possibly concave declared resource polygon. The Native Picard certificate
MUST still be independently replayed by the caller: mere JSON is untrusted.
"""
from __future__ import annotations
from fractions import Fraction as Q
import math


def _q(x):
    if isinstance(x,bool):raise ValueError('boolean not a physical length')
    if isinstance(x,float):
        if not math.isfinite(x):raise ValueError('nonfinite physical coordinate')
        return Q.from_float(x)
    if isinstance(x,int):return Q(x)
    if isinstance(x,Q):return x
    if isinstance(x,str):return Q(x)
    raise TypeError('exact or finite binary64 number required')


def polygon_vertices(poly):
    if type(poly) not in (tuple,list) or not 3<=len(poly)<=5000:
        raise ValueError('polygon requires 3..5000 vertices')
    pts=tuple((_q(x),_q(y)) for x,y in poly)
    if len(set(pts))<3 or len(set(pts))!=len(pts):raise ValueError('duplicate or degenerate vertices')
    # Reject collinear polygons; nonconvex polygons remain conservative because
    # every polygon point belongs to the convex hull of the provided vertices.
    if not any((b[0]-pts[0][0])*(c[1]-pts[0][1])-(b[1]-pts[0][1])*(c[0]-pts[0][0])
               for b in pts[1:] for c in pts[1:]):
        raise ValueError('degenerate collinear polygon')
    # A polygon with self-crossing boundary has ambiguous road-resource
    # interior.  Its convex-hull exclusion may be conservative, but silently
    # accepting an invalid map is not a valid road-topology contract.
    def cross(a,b,c):
        return (b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0])
    def on(a,b,c):
        return cross(a,b,c)==0 and min(a[0],b[0])<=c[0]<=max(a[0],b[0]) and min(a[1],b[1])<=c[1]<=max(a[1],b[1])
    def intersects(a,b,c,d):
        q1,q2,q3,q4=cross(a,b,c),cross(a,b,d),cross(c,d,a),cross(c,d,b)
        return ((q1==0 and on(a,b,c)) or (q2==0 and on(a,b,d)) or
                (q3==0 and on(c,d,a)) or (q4==0 and on(c,d,b)) or
                (q1*q2<0 and q3*q4<0))
    count=len(pts)
    for i in range(count):
        a,b=pts[i],pts[(i+1)%count]
        if a==b:raise ValueError('zero polygon edge')
        for j in range(i+1,count):
            if j==i+1 or (i==0 and j==count-1):continue
            if intersects(a,b,pts[j],pts[(j+1)%count]):
                raise ValueError('self-intersecting or self-touching polygon')
    return pts


def guaranteed_polygon_separation(state_tube,polygon,*,length_m,width_m,offset_x_m=0,offset_y_m=0):
    """Pure rational outer-separation proof for ONE complete state tube.

    state_tube = [px_interval, py_interval, psi_interval, v, a, delta]
    with each interval [lo,hi] from an already *verified* Native tube.
    Concludes only geometric exclusion in the *declared* coordinate frame.
    """
    verts=polygon_vertices(polygon)
    length,width,ox,oy=map(_q,(length_m,width_m,offset_x_m,offset_y_m))
    if length<=0 or width<=0:raise ValueError('positive vehicle geometry required')
    if type(state_tube) not in (tuple,list) or len(state_tube)!=6:raise ValueError('six-dimensional tube required')
    (xlo,xhi),(ylo,yhi)=(tuple(map(_q,state_tube[i])) for i in (0,1))
    if xlo>xhi or ylo>yhi:raise ValueError('invalid physical tube ordering')
    # For all yaw and every vehicle point: |q_body.x|+|q_body.y| <= R,
    # |n . R_yaw q_body| <= (|nx|+|ny|)*R by triangle inequality.
    R=abs(ox)+abs(oy)+(length+width)/2
    axes=[(Q(1),Q(0)),(Q(0),Q(1))]
    axes += [(b[1]-a[1],a[0]-b[0]) for a,b in zip(verts,verts[1:]+verts[:1])]
    for nx,ny in axes:
        if nx==0 and ny==0:continue
        low=min(nx*xlo,nx*xhi)+min(ny*ylo,ny*yhi)
        high=max(nx*xlo,nx*xhi)+max(ny*ylo,ny*yhi)
        radius=(abs(nx)+abs(ny))*R
        plow=min(nx*x+ny*y for x,y in verts)
        phigh=max(nx*x+ny*y for x,y in verts)
        if high+radius<plow or phigh<low-radius:
            return dict(status='DECLARED_TUBE_POLYGON_STRICTLY_SEPARATED',
                 separating_axis=[str(nx),str(ny)],
                 min_unscaled_gap=str(plow-(high+radius) if high+radius<plow else low-radius-phigh),
                 geometry_orientation_independent=True,exact_rational_arithmetic=True,
                 native_proof_replayed_here=False)
    return dict(status='MAY_INTERSECT_DECLARED_POLYGON',separating_axis=None,
                min_unscaled_gap=None,geometry_orientation_independent=True,
                exact_rational_arithmetic=True,native_proof_replayed_here=False)


def audit_native_polygon_resources(native_report,certs,resources,*,length_m,width_m,
                                  offset_x_m=0,offset_y_m=0,verify_native=None):
    """Replay all declared native certificates and all polygon resources.

    If verify_native is omitted the actual repo's MPFR certificate checker is
    loaded; a callback is allowed only for transparent isolated unit testing.
    Even full exclusion is conditional: no unlisted actor or resource theorem.
    """
    from hashlib import sha256
    import json
    reasons=[];rows=[];may=[]
    if native_report.get('status')!='CONDITIONAL_DECLARED_EGO_NATIVE_PICARD_SEGMENTED_REPLAY':
        reasons.append('NATIVE_SEGMENTED_DECLARATION_NOT_PASSED')
    expected=set()
    for r in native_report.get('rows',()):
        k=(r.get('world'),r.get('start'),r.get('end'))
        if k in expected:reasons.append('DUPLICATE_NATIVE_WORLD_SLAB')
        expected.add(k)
    if len(expected)!=native_report.get('expected_world_slabs') or len(expected)!=native_report.get('replayed_world_slabs') or not expected:
        reasons.append('INCOMPLETE_NATIVE_WORLD_SUPPORT')
    if set(certs)!=set((w,Q(a),Q(b)) for w,a,b in expected):
        reasons.append('NATIVE_CERTIFICATE_WORLD_SLAB_MISMATCH')
    if type(resources) is not dict or not resources:raise ValueError('nonempty resource polygon dictionary required')
    polygons={name:polygon_vertices(poly) for name,poly in resources.items()}
    if not all(type(k) is str and k for k in polygons):raise ValueError('nonempty resource identities required')
    if verify_native is None:
        from .certificate import replay_certificate
        verify_native=lambda cert:replay_certificate(cert).ok
    for r in native_report.get('rows',()):
        key=(r['world'],Q(r['start']),Q(r['end']))
        cert=certs.get(key)
        if cert is None:continue
        try:
            raw=json.dumps(cert,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
            if sha256(raw).hexdigest()!=r.get('certificate_sha256') or not verify_native(cert):
                reasons.append('INVALID_NATIVE_PROOF_OR_BYTES:'+str(key));continue
            if not cert.get('segments'):
                reasons.append('EMPTY_NATIVE_SEGMENT_LIST:'+str(key));continue
            # Native segments are sequential and the report's certificate
            # has been independently checked for exact coverage/inclusion.
            for seg in cert['segments']:
                for resource,polygon in polygons.items():
                    s=guaranteed_polygon_separation(seg['tube'],polygon,length_m=length_m,
                        width_m=width_m,offset_x_m=offset_x_m,offset_y_m=offset_y_m)
                    rows.append(dict(world=key[0],slab=[str(key[1]),str(key[2])],
                                     resource=resource,geometric_status=s['status'],
                                     segment_start_exact=seg['start_time_exact'],
                                     segment_end_exact=seg['end_time_exact']))
                    if s['status']!='DECLARED_TUBE_POLYGON_STRICTLY_SEPARATED':
                        may.append([key[0],str(key[1]),str(key[2]),resource])
        except (ValueError,TypeError,KeyError,OverflowError,ZeroDivisionError) as e:
            reasons.append('MALFORMED_NATIVE_SEGMENT:'+str(key)+':'+str(e))
    if may:reasons.append('POSSIBLE_RESOURCE_CONTACT_REQUIRES_ENTER_STAY_EXIT_PROOF')
    reasons=sorted(set(reasons))
    return dict(schema='rampd.a71.native_polygon_exclusion.v1',
       status='CONDITIONAL_DECLARED_NATIVE_POLYGON_EXCLUSION' if not reasons else 'UNKNOWN',
       reasons=reasons,per_segment_resource_checks=rows,possible_contacts=may,
       all_possible_hidden_worlds_physically_proven=False,
       all_other_actor_tubes_verified=False,
       physically_authoritative_resource_polygons_verified=False,
       full_protocol_and_terminal_sc_verified=False,formal_safe_training_labels_allowed=False)
