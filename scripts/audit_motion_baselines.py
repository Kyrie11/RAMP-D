#!/usr/bin/env python3
"""History-only baseline and offline weak motion-state diagnostics. No semantic labels."""
import argparse,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'python'))
import torch
from rampd_core.datasets.factual_dataset import load_cache
from rampd_core.datasets.collate import collate
from rampd_core.learning.rea_encoder import motion_features,historical_acceleration_baseline

def run(cache):
    sets,_=load_cache(cache);out={}
    with torch.no_grad():
        for split,rows in sets.items():
            groups={};actor_groups={};macro=[]
            for row in rows:
                b=collate([row]);i=b['inputs'];h=i['history'];valid=b['valid'];cur=h[:,:,-1];feat=motion_features(h,i['actor_mask']);speed=cur[...,4:6].norm(dim=-1)
                active=valid.any(-1); slow=speed<.3; moving=speed>=1.; lead=feat[...,8]>0.5
                disp=(b['target']-cur[:,:,None,:2]).norm(dim=-1).masked_fill(~valid,0.).amax(-1)
                ca=historical_acceleration_baseline(i);cv=b['cv'];y=b['target']; ce=(cv-y).norm(dim=-1);ae=(ca-y).norm(dim=-1)
                for name,mask in [('all',active),('slow_lt_0p3',active&slow),('slow_ge_0p3_lt_1',active&~slow&~moving),('moving_ge_1',active&moving),('slow_leader_proxy',active&slow&lead),('slow_no_leader_proxy',active&slow&~lead)]:
                    q=valid&mask[...,None];z=groups.setdefault(name,dict(knots=0,cv_sum=0.,ca_sum=0.));z['knots']+=int(q.sum());z['cv_sum']+=float(ce[q].sum());z['ca_sum']+=float(ae[q].sum());
                    z=actor_groups.setdefault(name,dict(actors=0,future_displacement_ge_0p5m=0));z['actors']+=int(mask.sum());z['future_displacement_ge_0p5m']+=int((mask&(disp>=.5)).sum())
                macro.append(dict(id=row['scenario_id'],cv=float(ce[valid].mean()),ca=float(ae[valid].mean())))
            for z in groups.values():
                z.update(cv_ADE_m=z['cv_sum']/z['knots'] if z['knots'] else None,ca_ADE_m=z['ca_sum']/z['knots'] if z['knots'] else None)
            out[split]=dict(groups=groups,actor_groups=actor_groups,scene_macro_cv=sum(x['cv'] for x in macro)/len(macro),scene_macro_ca=sum(x['ca'] for x in macro)/len(macro),per_scene=macro)
    return dict(scope='HISTORY_BASELINES_AND_OFFLINE_DISPLACEMENT_DIAGNOSTIC_NOT_INTENT_LABELS',data=out)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--cache',required=True);p.add_argument('--output',required=True);a=p.parse_args();torch.set_num_threads(2);Path(a.output).write_text(json.dumps(run(a.cache),indent=2,allow_nan=False)+'\n')
