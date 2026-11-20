"""Independent numeric geometric and control references; not native certificates."""
from math import sin,cos,hypot,isfinite,atan2,sqrt
from .a56_motion import center_from_rear

def rear_from_center(x,y,yaw,vx,vy,yaw_rate,ox,oy):
    if not all(isfinite(t) for t in (x,y,yaw,vx,vy,yaw_rate,ox,oy)):raise ValueError('nonfinite frame')
    dx=cos(yaw)*ox-sin(yaw)*oy;dy=sin(yaw)*ox+cos(yaw)*oy
    rx,ry=vx+yaw_rate*dy,vy-yaw_rate*dx
    return x-dx,y-dy,cos(yaw)*rx+sin(yaw)*ry,-sin(yaw)*rx+cos(yaw)*ry


def polyline_projection(point,points):
    """Nearest finite segment projection, reject ties at different arclengths."""
    if len(points)<2 or any(len(p)!=2 or not all(isfinite(z) for z in p) for p in (point,*points)):raise ValueError('finite polyline required')
    out=[];s=0.
    for a,b in zip(points,points[1:]):
        dx,dy=b[0]-a[0],b[1]-a[1];l=hypot(dx,dy)
        if not l:raise ValueError('zero segment')
        t=max(0.,min(1.,((point[0]-a[0])*dx+(point[1]-a[1])*dy)/(l*l)));p=(a[0]+t*dx,a[1]+t*dy)
        out.append((hypot(point[0]-p[0],point[1]-p[1]),s+t*l,p));s+=l
    best=min(out)
    if any(abs(a[0]-best[0])<=1e-10 and abs(a[1]-best[1])>1e-8 for a in out):raise ValueError('ambiguous route branch')
    return best


def first_contact_distance(follower,leader):
    """Continuous translation of fixed-heading OBB along follower heading.
    Each box is (center_x, center_y, yaw, length, width). Returns first contact
    distance or None. NOT lane/leader identity or rotating swept proof.
    """
    if any(len(b)!=5 or not all(isfinite(x) for x in b) or min(b[3:])<=0 for b in (follower,leader)):raise ValueError('invalid OBB')
    def axes(b):return ((cos(b[2]),sin(b[2])),(-sin(b[2]),cos(b[2])))
    dot=lambda a,b:a[0]*b[0]+a[1]*b[1]
    fa,la=axes(follower),axes(leader);d=(leader[0]-follower[0],leader[1]-follower[1]);lo,hi=0.,float('inf')
    for n in (*fa,*la):
        r=sum(abs(dot(n,a))*v/2 for box,ax in ((follower,fa),(leader,la)) for a,v in zip(ax,box[3:]))
        x=dot(d,n);v=dot(fa[0],n)
        if abs(v)<1e-14:
            if abs(x)>r:return None
        else:
            a,b=sorted(((x-r)/v,(x+r)/v));lo=max(lo,a);hi=min(hi,b)
            if lo>hi:return None
    return lo


def brake_screen(v,*,reaction,accel_upper,comfort,standstill_gap,extra=0.):
    """Stop-only screen with acceleration during response and standstill reserve.
    Not jerk-limited, not a guarantee of model response.
    """
    if not all(isfinite(x) for x in (v,reaction,accel_upper,comfort,standstill_gap,extra)) or min(v,reaction,accel_upper,standstill_gap,extra)<0 or comfort<=0:raise ValueError('invalid stop assumptions')
    return v*reaction+.5*accel_upper*reaction**2+(v+accel_upper*reaction)**2/(2*comfort)+standstill_gap+extra


def bicycle_reference(state,control,horizon,wheelbase,steps):
    """Independent RK4 pose quadrature with exact v,a,delta polynomials.
    Numeric reference only, no clipping, no friction/admissibility certificate.
    Reject reverse/pole crossing on the whole polynomial interval.
    """
    from math import tan,pi
    x,y,psi,v,a,d=state;j,w=control
    if not all(isfinite(t) for t in (*state,*control,horizon,wheelbase)) or min(horizon,wheelbase)<=0 or type(steps) is not int or steps<1:raise ValueError('invalid reference')
    vel=lambda t:v+a*t+j*t*t/2
    if min(vel(t) for t in (0,horizon,*([-a/j] if j and 0<-a/j<horizon else [])))<0 or max(abs(d),abs(d+w*horizon))>=pi/2:raise ValueError('inadmissible reference domain')
    def f(t,p):return (vel(t)*cos(p),vel(t)*sin(p),vel(t)*tan(d+w*t)/wheelbase)
    step=horizon/steps
    for k in range(steps):
        t=k*step;k1=f(t,psi);k2=f(t+step/2,psi+step*k1[2]/2);k3=f(t+step/2,psi+step*k2[2]/2);k4=f(t+step,psi+step*k3[2]);dx,dy,dp=(step*(q+2*r+2*s+z)/6 for q,r,s,z in zip(k1,k2,k3,k4));x+=dx;y+=dy;psi+=dp
    return x,y,psi,vel(horizon),a+j*horizon,d+w*horizon


def nominal_control_screen(state,control,h,*,wheelbase,mu,a_min,a_max,jerk_max,steering_max,steering_rate_max,v_max,g=9.80665):
    """Conservative numerical screen for the nominal jerk/steering-rate step.
    All extrema of v,a,delta occur at endpoints or the velocity stationary
    point. Friction bound uses separate absolute extrema (conservative, not
    outward-rounded); no saturation or emergency ability inferred.
    Use MPFR/native state constraints for certificates.
    """
    from math import tan,pi
    _,_,_,v,a,d=state;j,w=control
    nums=(*state,*control,h,wheelbase,mu,a_min,a_max,jerk_max,steering_max,steering_rate_max,v_max,g)
    if not all(isfinite(x) for x in nums) or min(h,wheelbase,mu,g,jerk_max,steering_max,steering_rate_max,v_max)<=0 or not a_min<0<a_max or steering_max>=pi/2:raise ValueError('explicit finite physical limits required')
    vvals=[v+a*t+j*t*t/2 for t in (0,h,*([-a/j] if j and 0<-a/j<h else []))];aris=(a,a+j*h);ds=(d,d+w*h)
    vv=max(map(abs,vvals));aa=max(map(abs,aris));dd=max(map(abs,ds));rho=None if dd>=pi/2 else hypot(aa,vv*vv*tan(dd)/wheelbase)/(mu*g)
    checks=dict(speed=min(vvals)>=0 and max(vvals)<=v_max,actuator_accel=min(aris)>=a_min and max(aris)<=a_max,jerk=abs(j)<=jerk_max,steering=dd<=steering_max,steering_rate=abs(w)<=steering_rate_max,friction=rho is not None and rho<=1)
    return dict(checks=checks,screen_pass=all(checks.values()),friction_ratio_upper_numeric=rho,certificate=False)
