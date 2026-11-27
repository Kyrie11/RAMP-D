#!/usr/bin/env python3
import argparse,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'python'))
import torch
from rampd_core.datasets.factual_dataset import load_cache,file_sha
from rampd_core.learning.training import fit,evaluate
from rampd_core.learning.joint_decoder import FactualJointModel

def main():
    p=argparse.ArgumentParser();p.add_argument('--cache',required=True);p.add_argument('--output',required=True);p.add_argument('--epochs',type=int,default=10);p.add_argument('--batch-size',type=int,default=2);p.add_argument('--seed',type=int,default=7);p.add_argument('--hidden',type=int,default=64);p.add_argument('--modes',type=int,default=3);p.add_argument('--neighbors',type=int,default=16);p.add_argument('--lr',type=float,default=.001);p.add_argument('--device',default='cpu');p.add_argument('--threads',type=int,default=2);p.add_argument('--freeze-encoder',action='store_true');p.add_argument('--overfit-one',action='store_true');p.add_argument('--residual-init',choices=('cv','legacy'),default='cv');p.add_argument('--objective',choices=('gaussian','radial_laplace'),default='gaussian');p.add_argument('--selection',choices=('nll','ade'),default='nll');p.add_argument('--weight-decay',type=float,default=.01);p.add_argument('--motion-context',action='store_true');p.add_argument('--soft-gate',action='store_true');p.add_argument('--query-modes',action='store_true');p.add_argument('--local-history',action='store_true');p.add_argument('--anchor-cv',action='store_true');p.add_argument('--trajectory-modes',action='store_true');a=p.parse_args()
    if min(a.hidden,a.modes,a.neighbors,a.threads)<=0: p.error('positive model dimensions and thread count required')
    torch.set_num_threads(a.threads); sets,summary=load_cache(a.cache); out=Path(a.output);out.mkdir(parents=True,exist_ok=False)
    model,report=fit(sets['training'],sets['validation'],epochs=a.epochs,batch_size=a.batch_size,seed=a.seed,d=a.hidden,modes=a.modes,neighbors=a.neighbors,lr=a.lr,device=a.device,freeze_encoder=a.freeze_encoder,diagnostic_overfit=a.overfit_one,residual_init=a.residual_init,objective=a.objective,selection=a.selection,weight_decay=a.weight_decay,motion_context=a.motion_context,soft_gate=a.soft_gate,query_modes=a.query_modes,local_history=a.local_history,anchor_cv=a.anchor_cv,trajectory_modes=a.trajectory_modes)
    ck=out/'weights.pt';torch.save(model.state_dict(),ck)
    copy=FactualJointModel(a.hidden,a.modes,a.neighbors,motion_context=a.motion_context,soft_gate=a.soft_gate,query_modes=a.query_modes,local_history=a.local_history,anchor_cv=a.anchor_cv,trajectory_modes=a.trajectory_modes).to(a.device);copy.load_state_dict(torch.load(ck,map_location=a.device,weights_only=True));replay=evaluate(copy,sets['validation'],a.batch_size,a.device,include_radial=a.objective=='radial_laplace')
    report.update(cache_manifest_sha256=summary['manifest_sha256'],cache_summary_sha256=file_sha(Path(a.cache)/'summary.json'),weights_sha256=file_sha(ck),replay_validation=replay,checkpoint_replay_match=all(abs(replay[k]-report['checkpoint_validation'][k])<1e-5 for k in replay),torch_version=torch.__version__,formal_sc=False)
    ok=report['checkpoint_replay_match'] and (not a.overfit_one or report['overfit_diagnostic_pass'] is True)
    report['prediction_beats_cv_ADE']=replay['top1_ADE_m']<replay['cv_ADE_m']-1e-7
    report['prediction_matches_or_beats_cv_ADE']=replay['top1_ADE_m']<=replay['cv_ADE_m']+1e-7
    report['status']=('DIAGNOSTIC_OVERFIT_PASS' if a.overfit_one else 'PILOT_TRAINED') if ok else 'REVIEW'
    (out/'training_report.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n'); print(json.dumps(dict(status=report['status'],best_epoch=report['best_epoch'],validation=replay)))
    return 0 if ok else 4
if __name__=='__main__': raise SystemExit(main())
