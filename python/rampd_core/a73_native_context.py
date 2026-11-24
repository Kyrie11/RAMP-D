"""Pure context checks for serialized Native tube certificates. Mathematical
inclusion must still be replayed with MPFR independently. Exact rational
arithmetic avoids trusting the report's asserted endpoint or rounded horizon.
"""
from fractions import Fraction as Q
import math

def q(x):
    if type(x) not in (int,float) or not math.isfinite(x):raise ValueError('numeric certificate field')
    return Q(x)

def bounds(a,n=6):
    if len(a)!=n:raise ValueError('box dimension')
    z=[tuple(map(q,v)) for v in a]
    if any(len(x)!=2 or x[0]>x[1] for x in z):raise ValueError('box ordering')
    return z

def contains(a,b):return all(x<=u<=v<=y for (x,y),(u,v) in zip(a,b))

def exact_endpoint(cert,dt):
    for seg in cert['segments']:
        lo=Q(*map(int,seg['start_time_exact']));hi=Q(*map(int,seg['end_time_exact']))
        if lo<=dt<=hi:
            if dt==lo:return bounds(seg['initial'])
            if dt==hi:return bounds(seg['endpoint'])
            h=dt-lo;init=bounds(seg['initial']);f=bounds(seg['field']);tube=bounds(seg['tube']);z=[(max(x+h*u,a),min(y+h*v,b)) for (x,y),(u,v),(a,b) in zip(init,f,tube)]
            if any(x>y for x,y in z):raise ValueError('empty endpoint')
            return z
    raise ValueError('time not covered')

def audit_context(certs, declarations):
    """declarations keyed (world, exact start,end), values independently given
    params/control/disturbance/initial for first slab; later initial must cover
    exact endpoint. All rows require an explicit independent context."""
    errors=[];prev={}
    if set(certs)!=set(declarations) or not certs:return ['DECLARED_CERT_CONTEXT_SUPPORT_MISMATCH']
    for key in sorted(certs,key=lambda k:(k[0],k[1],k[2])):
        c=certs[key];d=declarations[key];w,lo,hi=key
        try:
            dt=hi-lo;h=float.fromhex(c['horizon_hex']);hq=q(h)
            if dt<=0 or hq<dt or q(math.nextafter(h,-math.inf))>=dt:raise ValueError('wrong exact enclosing horizon')
            if c['params']!=d['params'] or bounds(c['control'],2)!=bounds(d['control'],2) or bounds(c['derivative_disturbance'])!=bounds(d['disturbance']):raise ValueError('physical context mismatch')
            init=bounds(c['initial']); declared=d.get('initial')
            if declared is not None and not contains(init,bounds(declared)):raise ValueError('initial support undercovered')
            if w in prev:
                end,z=prev[w]
                if lo!=end or not contains(init,z):raise ValueError('handoff undercovered')
            elif declared is None:raise ValueError('no independent initial declaration')
            prev[w]=(hi,exact_endpoint(c,dt))
        except (ValueError,TypeError,KeyError,OverflowError,ZeroDivisionError) as e:errors.append(f'{key}:{e}')
    return errors
