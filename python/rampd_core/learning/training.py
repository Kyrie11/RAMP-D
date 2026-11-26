"""Small pilot training, fixed seeds and one active loss. No Native dependency."""
import math, random
import torch
from ..datasets.collate import collate
from .joint_decoder import FactualJointModel
from .masked_losses import joint_nll,metric_sums

def _batches(rows,batch_size,order=None):
    order=list(range(len(rows))) if order is None else order
    for i in range(0,len(order),batch_size): yield collate([rows[j] for j in order[i:i+batch_size]])

def to_device(batch,device):
    return {k:({a:b.to(device) for a,b in v.items()} if isinstance(v,dict) else v.to(device)) for k,v in batch.items()}

@torch.no_grad()
def evaluate(model,rows,batch_size=2,device='cpu'):
    model.eval(); totals={}; nll=0.
    for b in _batches(rows,batch_size):
        b=to_device(b,device); p=model(b['inputs'],b['candidate']); l=joint_nll(p,b['target'],b['valid']); s=metric_sums(p,b['target'],b['valid'],b['cv'])
        if l is None: continue
        nll+=float(l)*s['knots']
        for k,v in s.items(): totals[k]=totals.get(k,0)+v
    n=totals.get('knots',0); a=totals.get('actors',0)
    if not n or not a: raise ValueError('evaluation has no valid labels')
    return dict(valid_knots=n,valid_actors=a,scenes=totals['scenes'],joint_nll_per_knot=nll/n,top1_ADE_m=totals['top1_sum']/n,joint_minADE_m=totals['joint_min_sum']/n,cv_ADE_m=totals['cv_sum']/n,top1_last_valid_FDE_m=totals['top1_fde_sum']/a)

def fit(train,val,*,epochs=10,batch_size=2,seed=7,d=64,modes=3,neighbors=16,lr=.001,device='cpu',freeze_encoder=False,diagnostic_overfit=False,residual_init="cv"):
    if not train or not val or epochs<1 or batch_size<1 or not math.isfinite(lr) or lr<=0: raise ValueError('training configuration')
    if any(r['split']!='training' or r.get('training_allowed') is not True for r in train) or any(r['split']!='validation' or r.get('training_allowed') is not False for r in val): raise ValueError('split/authorization')
    if {r['scenario_id'] for r in train}&{r['scenario_id'] for r in val} or {r['source_digest'] for r in train}&{r['source_digest'] for r in val}: raise ValueError('train/validation overlap')
    if diagnostic_overfit: train=train[:1]
    torch.manual_seed(seed); rng=random.Random(seed); model=FactualJointModel(d,modes,neighbors).to(device)
    if residual_init not in ("cv","legacy"): raise ValueError("residual initialization")
    if residual_init=="cv":
        torch.nn.init.zeros_(model.decode[-1].weight); torch.nn.init.zeros_(model.decode[-1].bias)
    if freeze_encoder:
        for p in model.encoder.parameters(): p.requires_grad_(False)
    optimizer=torch.optim.AdamW((p for p in model.parameters() if p.requires_grad),lr=lr)
    history=[dict(epoch=0,train=evaluate(model,train,batch_size,device),validation=evaluate(model,val,batch_size,device))]
    best=history[0]['train' if diagnostic_overfit else 'validation']['joint_nll_per_knot']
    best_state={k:v.detach().cpu().clone() for k,v in model.state_dict().items()}; best_epoch=0
    for epoch in range(1,epochs+1):
        model.train(); order=list(range(len(train)));rng.shuffle(order); grad=[]
        for b in _batches(train,batch_size,order):
            b=to_device(b,device); optimizer.zero_grad(set_to_none=True); pred=model(b['inputs'],b['candidate']); loss=joint_nll(pred,b['target'],b['valid'])
            if loss is None: continue
            if not torch.isfinite(loss): raise ValueError('nonfinite loss')
            loss.backward(); norm=torch.nn.utils.clip_grad_norm_(model.parameters(),5.,error_if_nonfinite=True); grad.append(float(norm)); optimizer.step()
        if not grad: raise ValueError('no active training loss')
        tm=evaluate(model,train,batch_size,device); vm=evaluate(model,val,batch_size,device)
        history.append(dict(epoch=epoch,train=tm,validation=vm,grad_norm_max=max(grad)))
        criterion=tm['joint_nll_per_knot'] if diagnostic_overfit else vm['joint_nll_per_knot']
        if criterion<best:
            best=criterion; best_epoch=epoch; best_state={k:v.detach().cpu().clone() for k,v in model.state_dict().items()}
    model.load_state_dict(best_state)
    checkpoint_train=evaluate(model,train,batch_size,device)
    overfit_pass=None
    if diagnostic_overfit:
        initial=history[0]['train']; floor=math.log(2*math.pi)
        excess0=max(initial['joint_nll_per_knot']-floor,0.); excess1=max(checkpoint_train['joint_nll_per_knot']-floor,0.)
        overfit_pass=bool((excess0>1e-6 and excess1<=.8*excess0) or (checkpoint_train['top1_ADE_m']<=.8*initial['top1_ADE_m']) or (initial['top1_ADE_m']<=.05 and checkpoint_train['top1_ADE_m']<=.05))
    return model,dict(checkpoint_training=checkpoint_train,overfit_diagnostic_pass=overfit_pass,active_heads=['joint'],inactive_heads=['event','occupancy','observation','viability','margin','deadline','causal'],seed=seed,settings=dict(d=d,modes=modes,neighbors=neighbors,epochs=epochs,batch_size=batch_size,lr=lr,freeze_encoder=freeze_encoder,diagnostic_overfit=diagnostic_overfit,device=device,residual_init=residual_init),best_epoch=best_epoch,history=history,checkpoint_validation=evaluate(model,val,batch_size,device),scope='PILOT_FACTUAL_NOT_COUNTERFACTUAL_NOT_SC')
