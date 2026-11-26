"""Dynamic scene padding. Model receives inputs and candidate separately from targets."""
import torch
from .feature_contract import HISTORY_DIM, MAP_DIM, CATEGORIES

def collate(rows):
    B=len(rows); A=max(len(r['actor_ids']) for r in rows); M=max(len(r['inputs']['map']) for r in rows)
    T=len(rows[0]['inputs']['history'][0]); H=len(rows[0]['candidate']['path'])
    z=lambda *s:torch.zeros(s,dtype=torch.float32)
    hist=z(B,A,T,HISTORY_DIM); cat=z(B,A,len(CATEGORIES)); maps=z(B,M,MAP_DIM); av=torch.zeros(B,A,dtype=torch.bool); mv=torch.zeros(B,M,dtype=torch.bool)
    cand=z(B,H,3); target=z(B,A,H,2); cv=z(B,A,H,2); valid=torch.zeros(B,A,H,dtype=torch.bool); dt=z(B,H)
    for b,r in enumerate(rows):
        a,m=len(r['actor_ids']),len(r['inputs']['map']); i=r['inputs']
        if r['domain']!='REAL_FACTUAL_LOGGED_EGO_PATH_SURROGATE' or r['heads']['joint'] is not True or any(v for k,v in r['heads'].items() if k!='joint'): raise ValueError('unsupported label domain/head')
        if r['actor_ids'][0]!=r['ego_id'] or len(set(r['actor_ids']))!=a or any(r['targets']['valid'][0]): raise ValueError('ego/target identity')
        hist[b,:a]=torch.tensor(i['history']); cat[b,:a]=torch.tensor(i['category']); maps[b,:m]=torch.tensor(i['map']); av[b,:a]=True; mv[b,:m]=True
        cand[b]=torch.tensor(r['candidate']['path']); dt[b]=torch.tensor(i['forecast_dt']); target[b,:a]=torch.tensor(r['targets']['xy']); valid[b,:a]=torch.tensor(r['targets']['valid']); cv[b,:a]=torch.tensor(r['baseline_cv'])
    return dict(inputs=dict(history=hist,category=cat,map=maps,actor_mask=av,map_mask=mv,dt=dt),candidate=cand,target=target,valid=valid,cv=cv)
