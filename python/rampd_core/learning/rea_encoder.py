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

def motion_features(h, actor_mask):
    """History-only kinematics and geometric leader proxy, not true intent."""
    valid=h[...,9]>0.5; cur=h[:,:,-1]; vel=h[...,4:6]; speed=vel.norm(dim=-1)
    dt=h[:,:,1:,8]-h[:,:,:-1,8]; pair=valid[:,:,1:] & valid[:,:,:-1] & (dt>1e-4)
    acc=(vel[:,:,1:]-vel[:,:,:-1])/dt.clamp_min(1e-4)[...,None]
    acc=torch.where(pair[...,None],acc,0.).clamp(-8.,8.)
    recent=pair & (h[:,:,1:,8]>=-.5)
    mean_acc=(acc*recent[...,None]).sum(-2)/recent.sum(-1,keepdim=True).clamp_min(1)
    f=torch.stack((cur[...,3],cur[...,2]),-1); left=torch.stack((-f[...,1],f[...,0]),-1)
    dv=cur[:,:,None,4:6]-cur[:,None,:,4:6]; rel=cur[:,None,:,:2]-cur[:,:,None,:2]
    along=(rel*f[:,:,None]).sum(-1); lat=(rel*left[:,:,None]).sum(-1)
    alignment=(f[:,:,None]*f[:,None]).sum(-1)
    gap=along-(cur[:,:,None,6]+cur[:,None,:,6])/2
    lead=(gap>0)&(lat.abs()<2.)&(alignment>.8)&actor_mask[:,None,:]&actor_mask[:,:,None]
    gap_min,idx=gap.masked_fill(~lead,1e4).min(-1); found=lead.any(-1)
    closing=(dv*f[:,:,None]).sum(-1).gather(-1,idx[...,None]).squeeze(-1)
    slow=(valid & (speed<.3)).sum(-1)/valid.sum(-1).clamp_min(1)
    mean_speed=(speed*valid).sum(-1)/valid.sum(-1).clamp_min(1)
    suffix=(valid & (speed<.3)).flip(-1).int().cumprod(-1).sum(-1).float()
    disp=(h[...,:2]-cur[:,:,None,:2]).norm(dim=-1).masked_fill(~valid,0.).amax(-1)
    feat=torch.stack((speed[:,:,-1]/15,mean_speed/15,slow,suffix/h.shape[-2],disp/10,
        (mean_acc*f).sum(-1)/4,(mean_acc*left).sum(-1)/4,recent.any(-1).float(),
        found.float(),torch.where(found,gap_min.clamp(max=40)/40,0.),torch.where(found,closing/15,0.)), -1)
    return feat*actor_mask[...,None]

class FactualSceneEncoder(nn.Module):
    def __init__(self,d=64,neighbors=16,motion_context=False,local_history=False):
        super().__init__(); self.hist=nn.Sequential(nn.Linear(HISTORY_DIM,d),nn.SiLU(),nn.Linear(d,d)); self.agent=nn.Linear(2*d+len(CATEGORIES),d); self.ego_type=nn.Parameter(torch.zeros(d)); self.map=nn.Sequential(nn.Linear(MAP_DIM,d),nn.SiLU(),nn.Linear(d,d)); self.aa=NeighborAttention(d,neighbors); self.am=NeighborAttention(d,neighbors)
        self.motion_context=motion_context; self.local_history=local_history
        if local_history: self.pose=nn.Linear(4,d)
        if motion_context: self.motion=nn.Sequential(nn.Linear(11,d),nn.SiLU(),nn.Linear(d,d))
    def forward(self,inputs):
        h=inputs['history']; mask=h[...,9:10]; x=h.clone(); x[...,:2]/=30.; x[...,4:6]/=15.; x[...,6:8]/=5.
        if self.local_history:
            # Current actor-centered history, retaining global pose through current token.
            cur=h[:,:,-1]; delta=h[...,:2]-cur[:,:,None,:2]
            c=cur[...,3,None]; sn=cur[...,2,None]
            x[...,0]=(delta[...,0]*c+delta[...,1]*sn)/10
            x[...,1]=(-delta[...,0]*sn+delta[...,1]*c)/10
            x[...,2]=h[...,2]*c-h[...,3]*sn; x[...,3]=h[...,3]*c+h[...,2]*sn
            x[...,4]=(h[...,4]*c+h[...,5]*sn)/15
            x[...,5]=(-h[...,4]*sn+h[...,5]*c)/15
        enc=self.hist(x)*mask; pooled=enc.sum(-2)/mask.sum(-2).clamp_min(1.)
        a=self.agent(torch.cat((pooled,enc[:,:,-1],inputs['category']),-1)); ego_marker=torch.zeros_like(a); ego_marker[:,0]=self.ego_type; a=a+ego_marker
        if self.local_history: a=a+self.pose(torch.cat((h[:,:,-1,:2]/30,h[:,:,-1,2:4]),-1))
        if self.motion_context: a=a+self.motion(motion_features(h,inputs['actor_mask']))
        m=inputs['map']; m_scaled=m.clone(); m_scaled[...,:6]/=30.; mp=self.map(m_scaled)
        pos=h[:,:,-1,:2]; av=inputs['actor_mask']; mv=inputs['map_mask']
        a=self.aa(a,a,pos,pos,av,av); a=self.am(a,mp,pos,m[...,4:6],mv,av)
        return a


def historical_acceleration_baseline(inputs, *, max_accel=3.0):
    """Diagnostic, bounded Cartesian CA from last 0.5 s valid velocity differences.
    Not a vehicle-dynamics model; can be worse than CV. No future inputs.
    """
    if not math.isfinite(max_accel) or max_accel<=0:raise ValueError('acceleration bound')
    h=inputs['history']; cur=h[:,:,-1];dt=h[:,:,1:,8]-h[:,:,:-1,8]
    valid=(h[:,:,1:,9]>.5)&(h[:,:,:-1,9]>.5)&(dt>1e-4)&(h[:,:,1:,8]>=-.5)
    a=(h[:,:,1:,4:6]-h[:,:,:-1,4:6])/dt.clamp_min(1e-4)[...,None]
    a=torch.where(valid[...,None],a,0.);a=a.sum(-2)/valid.sum(-1,keepdim=True).clamp_min(1)
    a=a*(max_accel/a.norm(dim=-1,keepdim=True).clamp_min(max_accel))
    t=inputs['dt'][:,None,:,None];return cur[:,:,None,:2]+cur[:,:,None,4:6]*t+.5*a[:,:,None]*t.square()


def damped_acceleration_baseline(inputs, *, decay_s=.5, max_accel=3.):
    """Integrate a(t)=a_hist exp(-t/tau), a history-only diagnostic baseline."""
    if not math.isfinite(decay_s) or decay_s<=0: raise ValueError('decay_s')
    cv=inputs['history'][:,:,-1,:2][:,:,None]+inputs['history'][:,:,-1,4:6][:,:,None]*inputs['dt'][:,None,:,None]
    ca=historical_acceleration_baseline(inputs,max_accel=max_accel)
    t=inputs['dt'][:,None,:,None]
    # CA residual is .5*a*t². Integral of exponentially decaying a is
    # a*tau²*(t/tau + expm1(-t/tau)), evaluated stably for positive t.
    scale=2*decay_s**2*(t/decay_s+torch.expm1(-t/decay_s))/t.square().clamp_min(1e-8)
    return cv+(ca-cv)*scale


def motion_state_features(inputs):
    """History-only weak-state features. Geometry proxies, not true intent."""
    h=inputs['history']; av=inputs['actor_mask']; cur=h[:,:,-1]
    features=motion_features(h,av)
    # Stop-sign proximity is not a lane association or signal phase.
    m=inputs['map']; stop=inputs['map_mask'] & (m[...,11]>.5)
    dist=torch.cdist(cur[...,:2],m[...,4:6]).masked_fill(~stop[:,None],float('inf')).amin(-1)
    found=torch.isfinite(dist)
    extra=torch.stack((found.float(),torch.where(found,dist.clamp(max=60)/60,0.),(h[...,9]>.5).float().mean(-1)),dim=-1)
    return torch.cat((features,extra,inputs['category']),-1)*av[...,None]
