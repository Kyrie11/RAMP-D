"""Typed public relation pilot. Not the complete REA or a safety verifier.
Per-agent query weights sources adaptively; unavailable sources are masked, not
interpreted as negative facts. Global events see only public protocol/context.
"""
import torch
from torch import nn

SOURCES=('motion','neighbor','resource','rule','information')
WIDTH=6

class RelationContext(nn.Module):
    def __init__(self, hidden=32, *, gated=True):
        super().__init__();self.gated=gated
        self.embed=nn.ModuleList(nn.Sequential(nn.Linear(WIDTH,hidden),nn.SiLU(),nn.Linear(hidden,hidden)) for _ in SOURCES)
        self.query=nn.Linear(hidden,hidden);self.keys=nn.Linear(hidden,hidden,bias=False)
        self.bias=nn.Parameter(torch.zeros(len(SOURCES)))
        self.out=nn.Sequential(nn.Linear(2*hidden,hidden),nn.SiLU())
    def forward(self,tokens,available):
        # [B,A,S,F], [B,A,S]. Motion contains self and must be present.
        if tokens.ndim!=4 or tokens.shape[-2:]!=(len(SOURCES),WIDTH) or available.shape!=tokens.shape[:-1] or available.dtype!=torch.bool or not available[...,0].all():raise ValueError('relation shape/self source')
        safe=torch.where(available[...,None],tokens,torch.zeros_like(tokens))
        if not torch.isfinite(safe).all():raise ValueError('nonfinite public relation')
        z=torch.stack([m(safe[:,:,i]) for i,m in enumerate(self.embed)],dim=2)
        q=self.query(z[:,:,0]);scores=(self.keys(z)*q[:,:,None]).sum(-1)/q.shape[-1]**.5+self.bias
        if not self.gated:scores=torch.zeros_like(scores)
        w=scores.masked_fill(~available,-torch.inf).softmax(-1)
        c=(w[...,None]*z).sum(2)
        return self.out(torch.cat((z[:,:,0],c),-1)),w

class RelationPilot(nn.Module):
    def __init__(self,horizon,head,variant='gated',hidden=32):
        super().__init__();self.head=head;self.horizon=horizon;self.variant=variant
        if variant not in ('flat','uniform','gated'):raise ValueError('variant')
        if variant=='flat':self.flat=nn.Sequential(nn.Linear(len(SOURCES)*(WIDTH+1),hidden),nn.SiLU(),nn.Linear(hidden,hidden),nn.SiLU())
        else:self.relation=RelationContext(hidden,gated=variant=='gated')
        self.global_head=head in ('event','observation')
        self.readout=nn.Sequential(nn.Linear(hidden*2,hidden),nn.SiLU(),nn.Linear(hidden,horizon+1 if self.global_head else horizon if head=='occupancy' else 1))
    def forward(self,x,mask):
        if self.variant=='flat':
            z=self.flat(torch.cat((torch.where(mask[...,None],x,0.),mask[...,None].to(x.dtype)),dim=-1).flatten(-2));w=None
        else:z,w=self.relation(x,mask)
        pooled=z.mean(1)
        if self.global_head:
            l=self.readout(torch.cat((z[:,0],pooled),-1));# existence and conditional time, normalized joint distribution
            return torch.cat((nn.functional.logsigmoid(-l[:,:1]),nn.functional.logsigmoid(l[:,:1])+l[:,1:].log_softmax(-1)),1),w
        l=self.readout(torch.cat((z,pooled[:,None].expand_as(z)),-1))
        return (l.transpose(1,2) if self.head=='occupancy' else l.squeeze(-1)),w


class PublicRelationAdapter(nn.Module):
    """Optional bridge for frozen factual Agent tokens. No data authorization.
    Upstream must provide public or explicitly hypothesized source embeddings,
    not actual hidden other-agent information. Missing evidence may be represented
    by an explicit public unknown token; availability mask is structural only.
    """
    TYPES=('agent','map','resource','rule','information','awareness_proxy')
    def __init__(self,d=64):
        super().__init__();self.d=d;self.query=nn.Linear(d,d);self.key=nn.ModuleList(nn.Linear(d,d) for _ in self.TYPES);self.value=nn.ModuleList(nn.Linear(d,d) for _ in self.TYPES);self.bias=nn.Parameter(torch.zeros(len(self.TYPES)));self.residual=nn.Linear(d,d,bias=False);nn.init.zeros_(self.residual.weight)
    def forward(self,agent,source,available,actor_mask):
        if agent.ndim!=3 or agent.shape[-1]!=self.d or source.shape!=(*agent.shape[:2],len(self.TYPES),self.d) or available.shape!=source.shape[:-1] or actor_mask.shape!=agent.shape[:2] or available.dtype!=torch.bool or actor_mask.dtype!=torch.bool:raise ValueError('typed adapter contract')
        mask=available&actor_mask[...,None];safe=torch.where(mask[...,None],source,0.)
        if not torch.isfinite(safe).all() or not torch.isfinite(agent).all():raise ValueError('nonfinite context')
        key=torch.stack([m(safe[:,:,j]) for j,m in enumerate(self.key)],2);value=torch.stack([m(safe[:,:,j]) for j,m in enumerate(self.value)],2);q=self.query(agent);score=(q[:,:,None]*key).sum(-1)/self.d**.5+self.bias
        # Null-source case: exact identity, no NaN from all masked softmax.
        w=score.masked_fill(~mask,-1e9).softmax(-1)*mask;w=w/w.sum(-1,keepdim=True).clamp_min(1e-8);delta=self.residual((w[...,None]*value).sum(2));return agent+delta,w
