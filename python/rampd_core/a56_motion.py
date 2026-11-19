"""Uncertified numerical/analytic baselines for forward road-motion diagnostics.
Not a replacement for the native jerk/steering-rate continuous verifier.
"""
from fractions import Fraction as Q
from math import sin, cos, sqrt, isfinite, hypot


def center_from_rear(x,y,yaw,v,yaw_rate,ox,oy):
    """Rigid body transform (pose AND translational velocity, SI units)."""
    if not all(isfinite(t) for t in (x,y,yaw,v,yaw_rate,ox,oy)):raise ValueError('nonfinite frame transform')
    c,s=cos(yaw),sin(yaw); dx,dy=c*ox-s*oy,s*ox+c*oy
    return (x+dx,y+dy,v*c-yaw_rate*dy,v*s+yaw_rate*dx)


def idm_net_gap(v,lead_v,gap,*,desired=13.9,spacing=2.,headway=1.5,a_max=2.,b_comfort=3.,exponent=4.):
    """Common clipped IDM variant; positive bumper gap or no lead (None pair).
    b_comfort affects desired gap, not a hard acceleration bound.
    """
    if not all(isfinite(z) for z in (v,desired,spacing,headway,a_max,b_comfort,exponent)) or v<0 or min(desired,a_max,b_comfort,exponent)<=0 or min(spacing,headway)<0:raise ValueError('invalid IDM state/parameters')
    free=(v/desired)**exponent
    if lead_v is None and gap is None:return a_max*(1-free)
    if lead_v is None or gap is None or not isfinite(lead_v) or not isfinite(gap) or lead_v<0 or gap<=0:raise ValueError('nonpositive/missing bumper gap: collision or invalid leader')
    s=spacing+max(0.,v*headway+v*(v-lead_v)/(2*sqrt(a_max*b_comfort)))
    return a_max*(1-free-(s/gap)**2)


def straight_jerk_step(v,a,j,h):
    """Exact constant jerk scalar displacement, no negative speed anywhere.
    Fraction inputs: reject a reverse-going step instead of clipping jerk state.
    """
    if any(type(x) is not Q for x in (v,a,j,h)) or h<=0 or v<0:raise ValueError('exact positive-duration state required')
    v1=v+a*h+j*h*h/2; vs=[v,v1]
    if j>0 and 0<-a/j<h:
        t=-a/j;vs.append(v+a*t+j*t*t/2)
    if min(vs)<0:raise ValueError('reverse-going jerk segment; explicit stop profile required')
    return (v*h+a*h*h/2+j*h*h*h/6,v1,a+j*h)


def smooth_stop_profile(steps,dt=Q(1,10)):
    """Known initial v=10, a=0. |j|<=2.5; brake -2.5 over 1/3/1 s.
    Ends at exactly v=a=0 after 5 s. Subsequent ticks remain stopped.
    """
    if type(steps) is not int or steps<1 or dt!=Q(1,10):raise ValueError('fixture grid only')
    x,v,a=Q(0),Q(10),Q(0); rows=[(x,v,a)]
    for k in range(steps):
        j=Q(-5,2) if k<10 else Q(5,2) if 40<=k<50 else Q(0)
        dx,v,a=straight_jerk_step(v,a,j,dt);x+=dx;rows.append((x,v,a))
    return tuple(rows)


def arc_friction_ratio(v,a,kappa,dt,mu,g=9.80665):
    """Max declared moving-state friction utilization for constant a,kappa.
    Flat no-slip reference only; not tire-force or physical certificate.
    """
    if not all(isfinite(t) for t in (v,a,kappa,dt,mu,g)) or v<0 or dt<=0 or mu<=0 or g<=0:raise ValueError('invalid friction parameters')
    vmax=max(v,max(0.,v+a*dt))
    return hypot(a,vmax*vmax*kappa)/(mu*g)
