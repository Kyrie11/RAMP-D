#!/usr/bin/env python3
"""Independent future-motion proxy probe + history baselines; no forecast weight updates."""
import argparse,json,sys,math
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'python'))
import torch
from rampd_core.datasets.factual_dataset import load_cache
from rampd_core.datasets.collate import collate
from rampd_core.learning.rea_encoder import motion_state_features,damped_acceleration_baseline,historical_acceleration_baseline
from rampd_core.learning.masked_losses import weak_motion_targets,weak_motion_bce

def collect(rows):
    xs=[];ys=[];ms=[];tot={}
    for r in rows:
        b=collate([r]);i=b['inputs'];y,m=weak_motion_targets(i,b['target'],b['valid']);n=int(i['actor_mask'].sum());xs.append(motion_state_features(i)[0,:n]);ys.append(y[0,:n]);ms.append(m[0,:n]);v=b['valid'];sp=i['history'][:,:,-1,4:6].norm(dim=-1)
        for name,pred in [('cv',b['cv']),('ca',historical_acceleration_baseline(i)),('damped_ca',damped_acceleration_baseline(i))]:
            e=(pred-b['target']).norm(dim=-1)
            for group,sel in [('all',v),('slow',v&(sp<1)[...,None]),('moving',v&(sp>=1)[...,None])]:
                z=tot.setdefault(name+':'+group,[0.,0]);z[0]+=float(e[sel].sum());z[1]+=int(sel.sum())
    return torch.cat(xs),torch.cat(ys),torch.cat(ms),{k:dict(knots=n,ADE_m=s/n if n else None) for k,(s,n) in tot.items()}

def metrics(p,y):
    n=len(y);k=int(y.sum())
    if n==0:return dict(n=0,positives=0,prevalence=None,average_precision=None,brier=None,logloss=None,recall_at_half=None)
    # AP with tied scores must be grouped; constant prior AP = prevalence.
    order=p.argsort(descending=True);z=p[order];yy=y[order].float();end=torch.cat((z[:-1]!=z[1:],torch.ones(1,dtype=torch.bool))).nonzero().flatten();cum=yy.cumsum(0)[end];inc=torch.diff(torch.cat((torch.zeros(1),cum)));ap=float((cum/(end+1)*inc).sum()/k) if k else None
    return dict(n=n,positives=k,prevalence=k/n,average_precision=ap,brier=float((p-y.float()).square().mean()),logloss=float(torch.nn.functional.binary_cross_entropy(p.clamp(1e-6,1-1e-6),y.float())),recall_at_half=float(((p>=.5)&y).sum()/k) if k else None)

def run(cache,epochs=150):
    sets,s=load_cache(cache);x,y,m,base=collect(sets['training']);v,vy,vm,vbase=collect(sets['validation']);res={}
    for j,name in enumerate(('low_speed_start','moving_deceleration')):
        sel=m[:,j];test=vm[:,j];t=y[sel,j];target=vy[test,j];
        if not len(t) or not t.any() or t.all():
            res[name]=dict(training_n=len(t),training_positive=int(t.sum()),status='UNKNOWN_NO_BOTH_CLASSES');continue
        p=t.float().mean();z={'constant_prevalence':metrics(torch.full_like(target.float(),p),target)}
        for label,dim in [('speed_only',1),('motion_context',x.shape[-1])]:
            a=x[sel,:dim];b=v[test,:dim];mean=a.mean(0);std=a.std(0,unbiased=False).clamp_min(.05);a=(a-mean)/std;b=(b-mean)/std
            torch.manual_seed(7);head=torch.nn.Linear(dim,1);opt=torch.optim.AdamW(head.parameters(),lr=.025,weight_decay=.01)
            for _ in range(epochs):
                opt.zero_grad();loss=weak_motion_bce(head(a).squeeze(-1),t,torch.ones_like(t));loss.backward();opt.step()
            z[label]=metrics(head(b).detach().squeeze(-1).sigmoid(),target)
        res[name]=dict(training_n=int(sel.sum()),training_positive=int(t.sum()),validation=z)
    return dict(scope='WEAK_OBSERVED_MOTION_PROXIES_NOT_INTENT_OR_AWARENESS',manifest_sha256=s['manifest_sha256'],training_baselines=base,validation_baselines=vbase,weak_motion=res,forecast_model_updated=False)

def main():
    p=argparse.ArgumentParser();p.add_argument('--cache',required=True);p.add_argument('--output',required=True);p.add_argument('--epochs',type=int,default=150);a=p.parse_args();torch.set_num_threads(2);r=run(a.cache,a.epochs);Path(a.output).write_text(json.dumps(r,indent=2,allow_nan=False)+'\n');print(json.dumps(r['weak_motion']))
if __name__=='__main__':main()
