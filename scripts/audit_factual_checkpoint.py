#!/usr/bin/env python3
"""Replay uploaded weights safely and stratify factual diagnostics. Query ablation is not causal evidence."""
import argparse,json,sys,math
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'python'))
import torch
from rampd_core.datasets.factual_dataset import load_cache,file_sha
from rampd_core.datasets.collate import collate
from rampd_core.learning.joint_decoder import FactualJointModel
from rampd_core.learning.training import evaluate
from rampd_core.learning.masked_losses import metric_sums,joint_nll,mode_diagnostics

def audit(cache,run):
    run=Path(run); sets,s=load_cache(cache); report=json.loads((run/'training_report.json').read_text()); settings=report['settings']; w=run/'weights.pt'
    if report['cache_manifest_sha256']!=s['manifest_sha256'] or report['cache_summary_sha256']!=file_sha(Path(cache)/'summary.json') or report['weights_sha256']!=file_sha(w): raise ValueError('checkpoint/cache binding')
    model=FactualJointModel(settings['d'],settings['modes'],settings['neighbors'],**{k:settings.get(k,False) for k in ('motion_context','soft_gate','query_modes','local_history','anchor_cv','trajectory_modes')});model.load_state_dict(torch.load(w,map_location='cpu',weights_only=True));model.eval()
    val=evaluate(model,sets['validation'],settings['batch_size'],include_radial='radial_nll_per_knot' in report['checkpoint_validation']); delta=max(abs(val[k]-report['checkpoint_validation'][k]) for k in val)
    bins={}; per_scene=[]; sensitivity=[]; cv_nll=[]
    with torch.no_grad():
        for r in sets['validation']:
            b=collate([r]);i=b['inputs'];p=model(i,b['candidate']);y=b['target'];v=b['valid'];cv=b['cv'];top=p['xy'][0,p['logits'][0].argmax()];err=(top-y[0]).norm(dim=-1);ce=(cv[0]-y[0]).norm(dim=-1);sp=i['history'][0,:,-1,4:6].norm(dim=-1);cat=i['category'][0].argmax(-1)
            groups={'stationary_or_slow_lt_1mps':sp<1,'moving_ge_1mps':sp>=1,'vehicle':cat==0,'pedestrian':cat==1,'cyclist':cat==2}
            for name,actor in groups.items():
                mask=v[0]&actor[:,None];z=bins.setdefault(name,dict(knots=0,model_error_sum=0.,cv_error_sum=0.));z['knots']+=int(mask.sum());z['model_error_sum']+=float(err[mask].sum());z['cv_error_sum']+=float(ce[mask].sum())
            cv_pred=dict(logits=torch.zeros(1,1),xy=cv[:,None]);cv_nll.append((float(joint_nll(cv_pred,y,v)),int(v.sum())))
            cand=b['candidate'].clone();cand[0,:,:2]=cv[0,0];q=model(i,cand);diff=(p['xy']-q['xy']).norm(dim=-1);sensitivity.append(dict(scenario_id=r['scenario_id'],query_max_delta_m=float((cand-b['candidate'])[...,:2].norm(dim=-1).max()),prediction_max_delta_m=float(diff[0,:,v[0]].max()),scope='QUERY_SENSITIVITY_NOT_CAUSAL'))
            met=metric_sums(p,y,v,cv);per_scene.append(dict(scenario_id=r['scenario_id'],knots=met['knots'],top1_ADE_m=met['top1_sum']/met['knots'],cv_ADE_m=met['cv_sum']/met['knots'],mode_probabilities=p['logits'].softmax(-1)[0].tolist(),mode_diagnostics=mode_diagnostics(p,y,v,family=settings.get('objective','gaussian'))[0]))
    for z in bins.values():
        n=z['knots'];z.update(model_ADE_m=z['model_error_sum']/n if n else None,cv_ADE_m=z['cv_error_sum']/n if n else None)
    md=[r['mode_diagnostics'] for r in per_scene]; informative=[x for x in md if x['geometric_rank_informative']]
    ranking=dict(informative_scenes=len(informative),geometric_top1_accuracy=(sum(x['geometric_top_in_ties'] for x in informative)/len(informative) if informative else None),mean_top1_oracle_ADE_gap_m=sum(x['top1_oracle_ADE_gap_m'] for x in md)/len(md),mean_prior_entropy=sum(x['prior_entropy'] for x in md)/len(md),mean_posterior_entropy=sum(x['posterior_entropy'] for x in md)/len(md),scope='GEOMETRIC_RANKING_AND_MODEL_RESPONSIBILITY_NOT_TRUE_LATENT_CALIBRATION')
    return dict(mode_ranking=ranking,scene_macro_ADE_m=sum(r['top1_ADE_m'] for r in per_scene)/len(per_scene),scene_macro_CV_ADE_m=sum(r['cv_ADE_m'] for r in per_scene)/len(per_scene),replay_max_abs_delta=delta,replay_match=delta<1e-5,validation=val,cv_nll_per_knot=sum(x*n for x,n in cv_nll)/sum(n for x,n in cv_nll),strata=bins,scenes=per_scene,candidate_query_ablation=sensitivity,scope='FACTUAL_CACHE_REPLAY_NOT_ONLINE_OR_CAUSAL')

def main():
    p=argparse.ArgumentParser();p.add_argument('--cache',required=True);p.add_argument('--run',required=True);p.add_argument('--output',required=True);a=p.parse_args();torch.set_num_threads(2);r=audit(a.cache,a.run);Path(a.output).write_text(json.dumps(r,indent=2,allow_nan=False)+'\n');print(r['replay_match']);return 0 if r['replay_match'] else 4
if __name__=='__main__':raise SystemExit(main())
