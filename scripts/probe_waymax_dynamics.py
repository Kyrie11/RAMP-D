#!/usr/bin/env python3
"""Independent numeric probe of Waymax's documented *discrete* bicycle update.
No log playback, training labels or continuous safety certificate. Local coordinates
avoid loss of precision in the arithmetic check; global frame ULP is reported.
"""
import argparse,json,math,sys,hashlib,inspect
from pathlib import Path
from importlib.metadata import version


def wrap(a): return math.atan2(math.sin(a),math.cos(a))


def reference(x,y,yaw,vx,vy,acc,kappa,dt):
    """Real-valued reference for the discrete rule, not exact ODE integration."""
    speed=math.hypot(vx,vy); ds=speed*dt+0.5*acc*dt**2
    theta=wrap(yaw+kappa*ds); next_speed=speed+acc*dt
    return (x+vx*dt+0.5*acc*math.cos(yaw)*dt**2,
            y+vy*dt+0.5*acc*math.sin(yaw)*dt**2,theta,
            next_speed*math.cos(theta),next_speed*math.sin(theta))


def exact_arc(x,y,yaw,speed,acc,kappa,dt):
    """Constant a/kappa no-slip arc comparison, separately scoped from Waymax."""
    if min(speed,speed+acc*dt)<0: raise ValueError('stop/reverse boundary requires explicit model')
    ds=speed*dt+0.5*acc*dt**2
    angle=yaw+kappa*ds
    if kappa==0: return x+ds*math.cos(yaw),y+ds*math.sin(yaw),wrap(angle)
    return x+(math.sin(angle)-math.sin(yaw))/kappa,y+(math.cos(yaw)-math.cos(angle))/kappa,wrap(angle)


def run():
    import numpy as np
    import jax.numpy as jnp
    from waymax import dynamics,datatypes
    from dataclasses import replace
    model=dynamics.InvertibleBicycleModel(dt=0.1,max_accel=6.,max_steering=.3,normalize_actions=False)
    # Values are intentionally varied, including near zero speed and yaw wrap.
    cases=[('coast',0.,10.,0.,0.),('accel',.3,10.,2.,0.),('brake',-.5,8.,-3.,0.),('curved',.3,10.,0.,.1),('turn_and_brake',-.7,8.,-2.,-.1),('yaw_wrap',3.13,5.,0.,.1),('at_stop',0.,0.,0.,0.),('brake_past_zero',0.,.1,-3.,0.)]
    rows=[]
    for name,psi,v,a,k in cases:
        x,y=0.,0.; vx,vy=v*math.cos(psi),v*math.sin(psi)
        # Input reference uses the actual float32 values sent to the model.
        v0=[float(np.float32(z)) for z in (x,y,psi,vx,vy,a,k)]
        x,y,psi,vx,vy,a,k=v0
        t=datatypes.Trajectory.zeros((1,1))
        arr=lambda z:jnp.asarray([[z]],dtype=jnp.float32)
        t=replace(t,x=arr(x),y=arr(y),yaw=arr(psi),vel_x=arr(vx),vel_y=arr(vy),length=arr(4.5),width=arr(1.8),height=arr(1.5),valid=jnp.ones((1,1),dtype=bool))
        act=datatypes.Action(data=jnp.asarray([[a,k]],dtype=jnp.float32),valid=jnp.ones((1,1),dtype=bool))
        u=model.compute_update(act,t)
        actual=[float(np.asarray(getattr(u,f))[0,0]) for f in ('x','y','yaw','vel_x','vel_y')]
        expected=reference(x,y,psi,vx,vy,a,k,.1)
        error=[abs(o-e) if i!=2 else abs(wrap(o-e)) for i,(o,e) in enumerate(zip(actual,expected))]
        # Compare the documented discrete rule, not the physical model. Tolerance
        # is a numeric regression limit, never a certificate bound.
        parity=bool(np.asarray(u.valid).all()) and all(math.isfinite(e) and e<=2e-5 for e in error)
        next_v=math.hypot(vx,vy)+.1*a
        arc=None
        if next_v>=0:
            xp,yp,_=exact_arc(x,y,psi,math.hypot(vx,vy),a,k,.1)
            arc=math.hypot(actual[0]-xp,actual[1]-yp)
        rows.append(dict(case=name,actual=actual,expected=expected,abs_error=error,discrete_parity=parity,arc_position_difference_m=arc,negative_signed_terminal_speed=next_v<0))
    return dict(status='DISCRETE_PARITY_PASS' if all(r['discrete_parity'] for r in rows) else 'ERROR',scope='SYNTHETIC_WAYMAX_DISCRETE_DYNAMICS_ONLY',waymax=version('waymo-waymax'),source_sha256=hashlib.sha256(inspect.getsource(dynamics.InvertibleBicycleModel).encode()).hexdigest(),dt_s=.1,comparison_tolerance=2e-5,float32_ulp_at_9000m=float(np.spacing(np.float32(9000))),cases=rows,continuous_safety_certified=False,counterfactual_labels_generated=False)


def main():
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    try: out=run()
    except Exception as e: out=dict(status='ERROR',scope='SYNTHETIC_WAYMAX_DISCRETE_DYNAMICS_ONLY',reason=f'{type(e).__name__}: {e}',continuous_safety_certified=False,counterfactual_labels_generated=False)
    a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(out,indent=2,allow_nan=False)+'\n');print(json.dumps(out,indent=2));return 0 if out['status']=='DISCRETE_PARITY_PASS' else 4
if __name__=='__main__': raise SystemExit(main())
