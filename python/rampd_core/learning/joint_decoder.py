"""Shared scene-level mixture modes, conditional on explicit ego prefix.
Non-autoregressive factual baseline; no claim of a causal simulator or full REA.
"""
import torch
from torch import nn
from .rea_encoder import FactualSceneEncoder, motion_features

class FactualJointModel(nn.Module):
    def __init__(self,d=64,modes=3,neighbors=16,*,motion_context=False,soft_gate=False,query_modes=False):
        super().__init__(); self.encoder=FactualSceneEncoder(d,neighbors,motion_context); self.candidate=nn.GRU(3,d,batch_first=True); self.mode=nn.Parameter(torch.randn(modes,d)*.1); self.logits=nn.Sequential(nn.Linear(d,d),nn.SiLU(),nn.Linear(d,modes)); self.decode=nn.Sequential(nn.Linear(3*d+1,d),nn.SiLU(),nn.Linear(d,2)); self.modes=modes
        self.soft_gate=soft_gate; self.query_modes=query_modes
        if soft_gate:
            self.gate=nn.Linear(d+11,1)
            nn.init.zeros_(self.gate.weight); nn.init.constant_(self.gate.bias,0.)
        if query_modes: self.query_logits=nn.Sequential(nn.Linear(3*d,d),nn.SiLU(),nn.Linear(d,modes))
    def encode_scene(self,inputs): return self.encoder(inputs)
    def decode_candidate(self,inputs,encoded,candidate):
        B,A,D=encoded.shape; H=candidate.shape[1]; K=self.modes
        c=candidate.clone(); c[...,:2]/=30.; cseq,_=self.candidate(c); mask=inputs['actor_mask']; pool=(encoded*mask[...,None]).sum(1)/mask.sum(1,keepdim=True).clamp_min(1)
        logits=self.logits(pool)
        if self.query_modes:
            # Conditional JOINT modes, not an external-event head.
            logits=self.query_logits(torch.cat((pool,encoded[:,0],cseq[:,-1]),-1))
        dt=inputs['dt']; cur=inputs['history'][:,:,-1]; cv=cur[:,:,:2,None].transpose(-1,-2)+cur[:,:,None,4:6]*dt[:,None,:,None]
        a=encoded[:,None,:,None,:].expand(B,K,A,H,D); q=cseq[:,None,None,:,:].expand(B,K,A,H,D); mode=self.mode[None,:,None,None,:].expand(B,K,A,H,D); t=dt[:,None,None,:,None].expand(B,K,A,H,1)
        residual=self.decode(torch.cat((a,q,mode,t),-1))*t
        if self.soft_gate:
            mf=motion_features(inputs['history'],mask)
            gate=.1+.9*torch.sigmoid(self.gate(torch.cat((encoded,mf),-1)))
            residual=residual*gate[:,None,:,None,:]
        return dict(logits=logits,xy=cv[:,None]+residual)
    def forward(self,inputs,candidate): return self.decode_candidate(inputs,self.encode_scene(inputs),candidate)
