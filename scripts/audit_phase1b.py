#!/usr/bin/env python3
"""Seeded RK4 falsification audit; NOT a proof or a real-vehicle experiment.

All sampled controls/disturbances lie inside the declared support. The RK4
reference is an ordinary approximate integrator. No coverage tolerance is
silently added. A miss fails the audit and requires investigation of both
reference error and enclosure logic.
"""
import argparse
import json
import math
import random
from pathlib import Path
from rampd_core import *
from rampd_core.certificate import to_dict

def vector_field(x,u,w,L):
    px,py,psi,v,a,delta=x
    return [v*math.cos(psi)+w[0],v*math.sin(psi)+w[1],
            v*math.tan(delta)/L+w[2],a+w[3],u[0]+w[4],u[1]+w[5]]

def rk4(x,u,w,L,h):
    def shift(k,s): return [v+s*d for v,d in zip(x,k)]
    k1=vector_field(x,u,w,L)
    k2=vector_field(shift(k1,h/2),u,w,L)
    k3=vector_field(shift(k2,h/2),u,w,L)
    k4=vector_field(shift(k3,h),u,w,L)
    return [v+h*(a+2*b+2*c+d)/6 for v,a,b,c,d in zip(x,k1,k2,k3,k4)]

def run_audit(rollouts=64,seed=31701):
    if rollouts<1: raise ValueError("positive rollout count required")
    rng=random.Random(seed)
    x=StateBounds(Interval(-.02,.02),Interval(-.02,.02),Interval(.09,.11),
                  Interval(5.9,6.1),Interval(-.1,.1),Interval(.04,.06))
    u=ControlBounds(Interval(-.8,.8),Interval(-.03,.03))
    p=BicycleParameters(2.8,.9)
    w=(Interval(-.002,.002),)*6
    result=integrate(x,u,p,.5,PicardOptions(max_step_s=.025),w)
    if result.status!=TubeStatus.VALIDATED:
        raise RuntimeError(f"audit tube unresolved: {result.reason}")
    checks=0;misses=[]
    def sample(box):
        # Interior samples reduce numerical-reference boundary ambiguity.
        return [q.lo+(q.hi-q.lo)*rng.uniform(.1,.9) for q in box]
    for rollout in range(rollouts):
        state=sample(x.as_tuple())
        for index,segment in enumerate(result.segments):
            checks+=1
            if not segment.witness.tube.contains(state): misses.append([rollout,index,"start"])
            dt=segment.witness.duration_s/8
            for k in range(8):
                state=rk4(state,sample(u.as_tuple()),sample(w),p.wheelbase_m,dt)
                checks+=1
                if not segment.witness.tube.contains(state): misses.append([rollout,index,k])
            checks+=1
            if not segment.witness.endpoint.contains(state): misses.append([rollout,index,"endpoint"])
    return dict(audit="numerical_falsification_only",reference="ordinary_RK4_piecewise_constant_inputs",
                seed=seed,rollouts=rollouts,checked_state_vectors=checks,containment_misses=len(misses),
                first_misses=misses[:10],empirical_containment_fraction=(checks-len(misses))/checks,
                tube_status=result.status.value,accepted_steps=len(result.segments),
                witness_replay=replay_certificate(to_dict(result)).ok,
                false_safe_count=None,false_safe_note="not defined: no safety verifier implemented",stats=result.stats)

if __name__=="__main__":
    ap=argparse.ArgumentParser()
    ap.add_argument("--output",default="reports/empirical_audit.json")
    ap.add_argument("--rollouts",type=int,default=64)
    ap.add_argument("--seed",type=int,default=31701)
    args=ap.parse_args()
    result=run_audit(args.rollouts,args.seed)
    path=Path(args.output);path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(result,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    print(json.dumps(result,indent=2))
    raise SystemExit(0 if result['containment_misses']==0 and result['witness_replay'] else 1)
