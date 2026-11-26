"""Pilot typed encoder, not the full paper REA-Encoder.
Local top-k neighbors are gathered, but neighbor search itself is dense.
No rule/commitment/awareness tokens until their observation contracts exist.
"""
import math
import torch
from torch import nn
from ..datasets.feature_contract import HISTORY_DIM, MAP_DIM, CATEGORIES

class NeighborAttention(nn.Module):
    def __init__(self,d,k):
        super().__init__(); self.k=k; self.q=nn.Linear(d,d); self.kproj=nn.Linear(d,d); self.v=nn.Linear(d,d); self.out=nn.Linear(d,d); self.norm=nn.LayerNorm(d)
    def forward(self, query, keys, qxy, kxy, key_mask, qmask):
        dist=torch.cdist(qxy,kxy); dist=dist.masked_fill(~key_mask[:,None,:],float('inf'))
        ds,idx=dist.topk(min(self.k,keys.shape[1]),largest=False)
        b=torch.arange(keys.shape[0],device=keys.device)[:,None,None]
        kk=self.kproj(keys)[b,idx]; vv=self.v(keys)[b,idx]
        score=(self.q(query)[:,:,None,:]*kk).sum(-1)/math.sqrt(query.shape[-1])-ds.clamp(max=1000)/30
        mask=torch.isfinite(ds); score=score.masked_fill(~mask,-1e9)
        w=score.softmax(-1)*mask; w=w/w.sum(-1,keepdim=True).clamp_min(1e-8)
        return self.norm(query+self.out((w[...,None]*vv).sum(-2)))*qmask[...,None]

class FactualSceneEncoder(nn.Module):
    def __init__(self,d=64,neighbors=16):
        super().__init__(); self.hist=nn.Sequential(nn.Linear(HISTORY_DIM,d),nn.SiLU(),nn.Linear(d,d)); self.agent=nn.Linear(2*d+len(CATEGORIES),d); self.ego_type=nn.Parameter(torch.zeros(d)); self.map=nn.Sequential(nn.Linear(MAP_DIM,d),nn.SiLU(),nn.Linear(d,d)); self.aa=NeighborAttention(d,neighbors); self.am=NeighborAttention(d,neighbors)
    def forward(self,inputs):
        h=inputs['history']; mask=h[...,9:10]; x=h.clone(); x[...,:2]/=30.; x[...,4:6]/=15.; x[...,6:8]/=5.
        enc=self.hist(x)*mask; pooled=enc.sum(-2)/mask.sum(-2).clamp_min(1.)
        a=self.agent(torch.cat((pooled,enc[:,:,-1],inputs['category']),-1)); ego_marker=torch.zeros_like(a); ego_marker[:,0]=self.ego_type; a=a+ego_marker
        m=inputs['map']; m_scaled=m.clone(); m_scaled[...,:6]/=30.; mp=self.map(m_scaled)
        pos=h[:,:,-1,:2]; av=inputs['actor_mask']; mv=inputs['map_mask']
        a=self.aa(a,a,pos,pos,av,av); a=self.am(a,mp,pos,m[...,4:6],mv,av)
        return a
