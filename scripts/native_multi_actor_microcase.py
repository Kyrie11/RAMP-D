#!/usr/bin/env python3
"""Native per-actor proof, exact same clock support; one positive and one
possible-contact negative. Conditional declaration only, not real traffic."""
import argparse,json,sys
from pathlib import Path
from fractions import Fraction as Q
from dataclasses import asdict
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'python'))
from rampd_core.a60_clock_resource import ClockEvent
from rampd_core.a61_hybrid_partition import ClockWorld
from rampd_core.segmented_native_post import NativeSlabInput,replay_segmented_native
from rampd_core.model import BicycleParameters,ControlBounds,StateBounds
from rampd_core.interval import Interval
from rampd_core.reachability import integrate,TubeStatus
from rampd_core.native_protocol_replay import exact_step_endpoint
from rampd_core.exact_time import binary64_bracket
from rampd_core.native_multi_actor_screen import audit_joint_native
from rampd_core.public_successor_binding import audit_native_successors

def main():
    p=argparse.ArgumentParser();p.add_argument('--output-dir',type=Path,required=True);a=p.parse_args();out=a.output_dir
    if out.exists():raise SystemExit('REFUSE_OVERWRITE')
    out.mkdir(parents=True);h=Q(1,20);params=BicycleParameters(3,.9);u=ControlBounds.point(0,0);z=(Interval.point(0),)*6
    worlds=tuple(ClockWorld(w,(ClockEvent('switch-'+w,'RULE_EFFECTIVE',h,'DECLARED_TOY_MODEL'),),declared_complete=True,public_history_id='same') for w in ('A','B'))
    certs={};decl={};geometry={};guards={};resource={'r':[[-2,-2],[2,-2],[2,2],[-2,2]]}
    for actor,x in [('ego',0),('other',20)]:
        x0=StateBounds.point([x,0,0,4,0,0]);t=integrate(x0,u,params,binary64_bracket(h)[1]);nxt=exact_step_endpoint(t,h)
        rows=tuple(NativeSlabInput(w,lo,hi,'public-zero',s,u,z) for w in ('A','B') for lo,hi,s in ((Q(0),h,x0),(h,2*h,nxt)))
        report,certs[actor]=replay_segmented_native(worlds,rows,start=Q(0),end=2*h,params=params)
        if report['status']!='CONDITIONAL_DECLARED_EGO_NATIVE_PICARD_SEGMENTED_REPLAY':raise SystemExit('NATIVE_GENERATION_FAILED')
        decl[actor]={(r.world_id,r.start,r.end):dict(params=asdict(params),control=[[0,0]]*2,disturbance=[[0,0]]*6,initial=[[x,x],[0,0],[0,0],[4,4],[0,0],[0,0]] if r.start==0 else None) for r in rows}
        geometry[actor]=(2,1,0,0)
        for k,c in certs[actor].items():
            (out/(actor+'_'+k[0]+'_'+str(k[1]).replace('/','_')+'.json')).write_text(json.dumps(c,allow_nan=False))
            guards[k]={'r':dict(entry=True,stay=True,exit=True,all_directions=True,ack=True,version=1,ack_version=1,capacity=1)}
    run=lambda:audit_joint_native(certs,decl,geometry,resource,guards,[],worlds,start=Q(0),end=2*h,ego='ego')
    pos=run()
    # Independent generous endpoint cells for declared straight motion; not taken from certificates.
    target={w:dict(latent=w,actors={'ego':[[-1,1],[-1,1],[-1,1],[3,5],[-1,1],[-1,1]],'other':[[19,21],[-1,1],[-1,1],[3,5],[-1,1],[-1,1]]}) for w in ('A','B')}
    outcomes={w:[dict(observation='[]',atom=w,latent=w)] for w in ('A','B')}
    def succ(targets):return audit_native_successors(certs,decl,geometry,resource,guards,[],worlds,start=Q(0),end=2*h,ego='ego',roster=('ego','other'),outcomes=outcomes,targets=targets)
    post=succ({'[]':target});missing=succ({'[]':{'A':target['A']}})
    next(iter(guards.values()))['r']['entry']=False;neg=run()
    result={'positive':pos,'closed_guard':neg,'public_post':post,'missing_posterior_atom':missing,'formal_labels_authorized':False};(out/'review.json').write_text(json.dumps(result,indent=2)+'\n')
    print(pos['status'],neg['status']);return 0 if pos['status'].startswith('CONDITIONAL') and neg['status']=='UNKNOWN' and post['status']=='CONDITIONAL_DECLARED_NATIVE_POST_SUPPORT' and missing['status']=='UNKNOWN' else 4
if __name__=='__main__':raise SystemExit(main())
