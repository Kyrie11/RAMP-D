"""Forward-only constant-acceleration, constant-curvature reference.
Not a replacement for the jerk/steering-rate MPFR certificate. State is at the
chosen no-slip reference point; caller must establish frame and calibration.
"""
from math import sin,cos,atan2,isfinite


def forward_arc(x,y,yaw,v,a,kappa,dt):
    if not all(isfinite(z) for z in (x,y,yaw,v,a,kappa,dt)) or v<0 or dt<=0:
        raise ValueError('finite forward state and positive dt required')
    moving=min(dt,v/-a) if a<0 else dt
    ds=v*moving+.5*a*moving*moving
    vf=max(0.,v+a*moving)
    turn=kappa*ds
    if not all(isfinite(z) for z in (ds,vf,turn,yaw+turn)):
        raise ValueError("nonfinite integrated state")
    # Mid-angle chord form avoids cancellation as curvature approaches zero.
    half=turn/2
    sinc=sin(half)/half if half else 1.
    chord=ds*sinc
    angle=atan2(sin(yaw+turn),cos(yaw+turn))
    out=(x+chord*cos(yaw+half),y+chord*sin(yaw+half),angle,vf*cos(angle),vf*sin(angle))
    if not all(isfinite(z) for z in out):
        raise ValueError("nonfinite integrated state")
    return out
