"""Joint mixture likelihood with one shared latent mode per scene.
Missing coordinates never contribute. Inactive heads are not instantiated/trained.
"""
import math
import torch


def joint_nll(pred,target,valid,sigma=1.):
    if not math.isfinite(sigma) or sigma<=0: raise ValueError('positive fixed Gaussian sigma required')
    if valid.dtype!=torch.bool or target.shape[:-1]!=valid.shape or pred['xy'].shape[0]!=target.shape[0] or pred['xy'].shape[2:]!=target.shape[1:]: raise ValueError('joint shape/mask')
    n=valid.sum((1,2)); eligible=n>0
    if not eligible.any(): return None
    # Select before arithmetic; invalid targets may be arbitrary, including NaN.
    y=torch.where(valid[...,None],target,0.); p=torch.where(valid[:,None,:,:,None],pred['xy'],0.)
    if not torch.isfinite(y).all() or not torch.isfinite(p).all() or not torch.isfinite(pred['logits']).all(): raise ValueError('nonfinite active tensor')
    sq=(p-y[:,None]).square().sum(-1)
    log_density=-(sq/(2*sigma*sigma)+math.log(2*math.pi*sigma*sigma))*valid[:,None]
    log_joint=log_density.sum((2,3))+pred['logits'].log_softmax(-1)
    return -torch.logsumexp(log_joint[eligible],dim=-1).sum()/n[eligible].sum()

@torch.no_grad()
def metric_sums(pred,target,valid,cv):
    n=valid.sum((1,2)); y=torch.where(valid[...,None],target,0.); xy=torch.where(valid[:,None,:,:,None],pred['xy'],0.)
    err=(xy-y[:,None]).norm(dim=-1)*valid[:,None]; sums=err.sum((2,3)); top=pred['logits'].argmax(-1); bi=torch.arange(len(top),device=top.device)
    # One best mode for entire scene, not per-agent oracle switching.
    cv_safe=torch.where(valid[...,None],cv,0.); cvsum=((cv_safe-y).norm(dim=-1)*valid).sum()
    # FDE at each actor's last valid future knot (not padded endpoint).
    H=valid.shape[-1]; idx=(valid*torch.arange(1,H+1,device=valid.device)).max(-1).values; actor_valid=idx>0
    top_err=err[bi,top]; end=top_err.gather(-1,(idx-1).clamp_min(0)[...,None]).squeeze(-1)*actor_valid
    return dict(knots=int(n.sum()),actors=int(actor_valid.sum()),scenes=int((n>0).sum()),top1_sum=float(sums[bi,top].sum()),joint_min_sum=float(sums.min(-1).values.sum()),cv_sum=float(cvsum),top1_fde_sum=float(end.sum()))
