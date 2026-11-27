#!/usr/bin/env python3
"""Train trajectory model on a proper subset, freeze it, train independent scene ranker
on held-out training families; original validation is only diagnostic evaluation.
No independent actor mode switching, no probability claims, no formal safety labels.
"""
import argparse,json,sys,random
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'python'))
import torch
from rampd_core.datasets.factual_dataset import load_cache,file_sha
from rampd_core.datasets.collate import collate
from rampd_core.learning.training import fit
from rampd_core.learning.mode_ranking import SceneRanker,ranking_inputs,geometric_teacher

def main():
    p=argparse.ArgumentParser();p.add_argument('--cache',required=True);p.add_argument('--output',required=True);p.add_argument('--base-epochs',type=int,default=3);p.add_argument('--rank-epochs',type=int,default=60);p.add_argument('--calibration-families',type=int,default=40);p.add_argument('--seed',type=int,default=7);p.add_argument('--threads',type=int,default=2);a=p.parse_args();torch.set_num_threads(a.threads)
    sets,s=load_cache(a.cache);tr=sorted(sets['training'],key=lambda x:x['scenario_id']);va=sets['validation'];random.Random(a.seed).shuffle(tr);n=a.calibration_families
    if not 1<=n<len(tr) or a.base_epochs<1 or a.rank_epochs<1:p.error('insufficient training families or epochs')
    calibration,base=tr[:n],tr[n:];ids=lambda x:[r['scenario_id'] for r in x]
    if set(ids(calibration))&set(ids(base)) or set(ids(calibration))&set(ids(va)):raise ValueError('ranking family leakage')
    # Use calibration set for ranker training only. Base checkpoint is fixed final
    # epoch: fit selects on a separate 10-family subset of base, not original val.
    if len(base)<12:raise ValueError('need at least 12 base families')
    inner=base[:10];base=base[10:];inner=[dict(r,split='validation',training_allowed=False) for r in inner]
    model,report=fit(base,inner,epochs=a.base_epochs,batch_size=4,seed=a.seed,modes=3,motion_context=True,soft_gate=True,query_modes=True,selection='nll')
    model.eval();out=Path(a.output);out.mkdir(parents=True,exist_ok=False)
    @torch.no_grad()
    def collect(rows):
        data=[]
        for r in rows:
            b=collate([r]);pred=model(b['inputs'],b['candidate']);f,xy=ranking_inputs(pred,b['inputs']);q,active,ade=geometric_teacher(xy,b['target'],b['valid']);n=int(b['valid'].sum());
            if not bool(active[0]):continue
            data.append(dict(id=r['scenario_id'],f=f[0],q=q[0],ade=ade[0],n=n,prior_top=int(pred['logits'].argmax(-1)[0])))
        return data
    c=collect(calibration);v=collect(va);torch.manual_seed(a.seed);rank=SceneRanker();opt=torch.optim.AdamW(rank.parameters(),lr=.01)
    X=torch.stack([x['f'] for x in c]);q=torch.stack([x['q'] for x in c]);hist=[]
    for ep in range(a.rank_epochs):
        opt.zero_grad();l=-(q*rank(X).log_softmax(-1)).sum(-1).mean();l.backward();opt.step();hist.append(float(l.detach()))
    @torch.no_grad()
    def metrics(rows):
        records=[]
        for r in rows:
            sc=rank(r['f'][None])[0];chosen=int(sc.argmax());e=r['ade'];records.append(dict(id=r['id'],knots=r['n'],selected=chosen,cv=float(e[-1]),top1=float(e[r['prior_top']]),ranked=float(e[chosen]),oracle=float(e.min()),rank_scores=sc.tolist()))
        total=sum(x['knots'] for x in records);return dict(scenes=len(records),cv_selected=sum(x['selected']==3 for x in records),**{k+'_ADE_m':sum(x[k]*x['knots'] for x in records)/total for k in ('cv','top1','ranked','oracle')},records=records)
    torch.save(model.state_dict(),out/'base_weights.pt');torch.save(rank.state_dict(),out/'ranker_weights.pt')
    result=dict(scope='GEOMETRIC_PROPOSAL_RANKING_DIAGNOSTIC_NOT_MIXTURE_CALIBRATION',manifest_sha256=s['manifest_sha256'],base_ids=ids(base),inner_selection_ids=ids(inner),calibration_ids=ids(calibration),validation_ids=ids(va),base_report=report,rank_loss_history=hist,calibration=metrics(c),validation=metrics(v),probabilities_unchanged=True,formal_sc=False)
    (out/'report.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n');print(json.dumps({k:v for k,v in result['validation'].items() if k!='records'}))
if __name__=='__main__':main()
