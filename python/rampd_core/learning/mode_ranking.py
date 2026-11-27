"""Scene-level geometric ranker. Never replaces normalized mixture probabilities.
Uses predicted trajectories and public history only. Includes a CV fallback proposal.
"""
import torch
from torch import nn

FEATURE_DIM=11

def ranking_inputs(pred,inputs):
    h=inputs['history'];av=inputs['actor_mask'].clone();av[:,0]=False
    cur=h[:,:,-1];t=inputs['dt'][:,None,:,None];cv=cur[:,:,None,:2]+cur[:,:,None,4:6]*t
    xy=torch.cat((pred['xy'],cv[:,None]),dim=1)
    B,K,A,H,_=xy.shape;v=cur[...,4:6].norm(dim=-1);slow=(v<1)&av;moving=(v>=1)&av
    def avg(z,mask):return (z*mask[:,None,:,None]).sum((2,3))/(mask.sum(-1)[:,None]*H).clamp_min(1)
    res=(xy-cv[:,None]).norm(dim=-1);disp=(xy-cur[:,None,:,None,:2]).norm(dim=-1)
    probs=torch.cat((pred['logits'].softmax(-1),torch.zeros(B,1,device=xy.device)),1)
    anchor=torch.zeros(B,K,device=xy.device);anchor[:,-1]=1
    f=torch.stack((probs,anchor,avg(res,av),avg(res,slow),avg(res,moving),avg(disp,av)/10,
        res.masked_fill(~av[:,None,:,None],0.).amax((2,3))/10,
        (av.sum(-1).float()/100)[:,None].expand(B,K),
        (slow.sum(-1)/av.sum(-1).clamp_min(1))[:,None].expand(B,K),
        (v*av).sum(-1)[:,None].expand(B,K)/av.sum(-1).clamp_min(1)[:,None]/15,
        ((res[:,:,:,-1]*av[:,None]).sum(-1)/av.sum(-1).clamp_min(1)[:,None])), -1)
    return f,xy

def geometric_teacher(xy,target,valid,temperature_m=.2):
    if temperature_m<=0:raise ValueError('ranking temperature')
    n=valid.sum((1,2));active=n>0;y=torch.where(valid[...,None],target,0.);x=torch.where(valid[:,None,:,:,None],xy,0.)
    ade=(x-y[:,None]).norm(dim=-1).sum((2,3))/n[:,None].clamp_min(1)
    return (-ade/temperature_m).softmax(-1),active,ade

class SceneRanker(nn.Module):
    def __init__(self):
        super().__init__();self.score=nn.Sequential(nn.Linear(FEATURE_DIM,24),nn.SiLU(),nn.Linear(24,1))
    def forward(self,f):return self.score(f).squeeze(-1)
