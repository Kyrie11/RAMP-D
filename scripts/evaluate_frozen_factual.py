#!/usr/bin/env python3
"""Evaluate a frozen factual checkpoint on a new exact-record-disjoint cache.
No selection or optimization; a logged ego future remains an offline query.
"""
import argparse,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'python'))
from rampd_core.datasets.factual_dataset import load_cache,file_sha
from rampd_core.datasets.split_manifest import validate_external_evaluation,canonical_digest
from rampd_core.learning.joint_decoder import FactualJointModel
from rampd_core.learning.training import evaluate
from rampd_core.datasets.collate import collate
from rampd_core.learning.rea_encoder import damped_acceleration_baseline
import torch

def main():
    p=argparse.ArgumentParser();p.add_argument('--original-cache',type=Path,required=True);p.add_argument('--cache',type=Path,required=True);p.add_argument('--run',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();torch.set_num_threads(2)
    old=json.loads((a.original_cache/'manifest.json').read_text());new=json.loads((a.cache/'manifest.json').read_text());gate=validate_external_evaluation(old,new)
    oldsummary=json.loads((a.original_cache/'summary.json').read_text());rows,s=load_cache(a.cache);r=json.loads((a.run/'training_report.json').read_text());w=a.run/'weights.pt';settings=r['settings']
    if canonical_digest(old)!=r['cache_manifest_sha256'] or file_sha(a.original_cache/'summary.json')!=r['cache_summary_sha256'] or file_sha(w)!=r['weights_sha256'] or oldsummary['settings']!=s['settings']:raise ValueError('frozen training source / feature contract mismatch')
    m=FactualJointModel(settings['d'],settings['modes'],settings['neighbors'],**{k:settings.get(k,False) for k in ('motion_context','soft_gate','query_modes','local_history','anchor_cv','trajectory_modes')});m.load_state_dict(torch.load(w,weights_only=True,map_location='cpu'));m.eval()
    v=evaluate(m,rows['validation'],settings['batch_size'],include_radial=settings.get('objective')=='radial_laplace');dca=0.;n=0;per=[]
    with torch.no_grad():
        for row in rows['validation']:
            b=collate([row]);x=damped_acceleration_baseline(b['inputs']);valid=b['valid'];k=int(valid.sum());d=float((x-b['target']).norm(dim=-1)[valid].sum());dca+=d;n+=k;per.append(dict(scenario_id=row['scenario_id'],knots=k,dca_ADE_m=d/k))
    report=dict(scope='FROZEN_EXTERNAL_FACTUAL_LOGGED_EGO_QUERY_ONLY',split_gate=gate,source_manifest_sha256=canonical_digest(old),evaluation_manifest_sha256=canonical_digest(new),weights_sha256=file_sha(w),settings=settings,metrics=v,dca_ADE_m=dca/n,per_scene=per,optimization_steps=0,formal_sc=False)
    a.output.parent.mkdir(parents=True,exist_ok=True)
    with a.output.open('x') as f:json.dump(report,f,indent=2,allow_nan=False)
if __name__=='__main__':main()
