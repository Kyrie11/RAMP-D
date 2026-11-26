"""Joint mixture likelihood with one shared latent mode per scene.
Missing coordinates never contribute. Inactive heads are not instantiated/trained.
"""
import math
import torch


def joint_nll(pred,target,valid,sigma=1., *, family="gaussian"):
    """Scene-shared mixture. Radial Laplace is an optional proper robust density,
    with scale sigma in metres; Gaussian remains the paper pilot baseline."""
    if family not in ("gaussian", "radial_laplace"): raise ValueError("unknown likelihood family")
    if not math.isfinite(sigma) or sigma<=0: raise ValueError('positive fixed Gaussian sigma required')
    if valid.dtype!=torch.bool or target.ndim!=4 or target.shape[-1]!=2 or target.shape[:-1]!=valid.shape or pred['xy'].ndim!=5 or pred['xy'].shape[0]!=target.shape[0] or pred['xy'].shape[2:]!=target.shape[1:] or pred['logits'].shape!=pred['xy'].shape[:2] or not pred['xy'].shape[1]: raise ValueError('joint shape/mask')
    n=valid.sum((1,2)); eligible=n>0
    if not eligible.any(): return None
    # Select before arithmetic; invalid targets may be arbitrary, including NaN.
    y=torch.where(valid[...,None],target,0.); p=torch.where(valid[:,None,:,:,None],pred['xy'],0.)
    if not torch.isfinite(y).all() or not torch.isfinite(p).all() or not torch.isfinite(pred['logits'][eligible]).all(): raise ValueError('nonfinite active tensor')
    sq=(p-y[:,None]).square().sum(-1)
    energy = sq/(2*sigma*sigma) if family == 'gaussian' else (p-y[:,None]).norm(dim=-1)/sigma
    log_density=-(energy+math.log(2*math.pi*sigma*sigma))*valid[:,None]
    log_joint=log_density[eligible].sum((2,3))+pred['logits'][eligible].log_softmax(-1)
    return -torch.logsumexp(log_joint,dim=-1).sum()/n[eligible].sum()

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


@torch.no_grad()
def mode_diagnostics(pred,target,valid):
    """Per eligible scene, actual mode spread and Gaussian posterior responsibilities."""
    mask=valid[:,None,:,:,None]; y=torch.where(valid[...,None],target,0.)
    xy=torch.where(mask,pred['xy'],0.); n=valid.sum((1,2)); out=[]
    for b in range(len(n)):
        if not n[b]: continue
        err=(xy[b]-y[b,None]).square().sum((1,2,3))
        prior=pred['logits'][b].softmax(-1); posterior=(pred['logits'][b].log_softmax(-1)-err/2).softmax(-1)
        spread=[float((xy[b,i]-xy[b,j]).norm(dim=-1).sum()/n[b]) for i in range(len(prior)) for j in range(i)]
        out.append(dict(prior=prior.tolist(),posterior=posterior.tolist(),top=int(prior.argmax()),oracle=int(err.argmin()),pairwise_mean_m=sum(spread)/len(spread) if spread else 0.,valid_knots=int(n[b])))
    return out
