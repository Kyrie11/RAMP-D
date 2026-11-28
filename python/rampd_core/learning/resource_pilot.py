"""Independent head optimization only on the explicit declared affine domain."""
import torch
from torch import nn
from ..datasets.shared_resource_labels import HEADS
from ..datasets.split_manifest import canonical_digest

def fit_head(train,val,head,*,seed=7,epochs=50):
    if head not in HEADS or not train or not val or {x['family_id'] for x in train}&{x['family_id'] for x in val}:raise ValueError('head/family split')
    def tensors(rows,split):
        for r in rows:
            if r['digest']!=canonical_digest({k:v for k,v in r.items() if k!='digest'}) or r['domain']!='DECLARED_2D_AFFINE_MODEL_ONLY' or r['split']!=split or r['model_training_allowed']!=(split=='training') or r['real_world_training_allowed'] is not False or r['formal_sc'] is not False or any(r['formal_heads'].values()) or r['field_valid'][head] is not True:raise ValueError('label domain/permission')
        return torch.tensor([r['public_inputs'] for r in rows],dtype=torch.float32),torch.tensor([r['targets'][head] for r in rows])
    x,y=tensors(train,'training');v,z=tensors(val,'validation');binary=head=='occupancy';width=y.shape[1] if binary else 3
    torch.manual_seed(seed);model=nn.Sequential(nn.Linear(x.shape[1],32),nn.SiLU(),nn.Linear(32,width));opt=torch.optim.AdamW(model.parameters(),lr=.01)
    lossfn=nn.functional.binary_cross_entropy_with_logits if binary else nn.functional.cross_entropy
    if binary:y=y.float();z=z.float()
    def evaluate(logits,truth):
        pred=(logits>=0).long() if binary else logits.argmax(-1);t=truth.long();acc=float((pred==t).float().mean());classes=2 if binary else 3
        support=[int((t==i).sum()) for i in range(classes)]; recall=[float((pred[t==i]==i).float().mean()) if n else None for i,n in enumerate(support)]
        return dict(loss=float(lossfn(logits,truth)),accuracy=acc,class_support=support,class_recall=recall)
    if binary:prior=y.mean(0).clamp(.001,.999).logit().expand(len(z),width)
    else:prior=(torch.bincount(y,minlength=3).float()+1).log().expand(len(z),3)
    with torch.no_grad():
        initial=evaluate(model(v),z);base=evaluate(prior,z)
        # Public persistence baseline: current observed occupancy or permission.
        # For Event this uses public permission as a proxy, not hidden command.
        if binary:
            occ=(v[:,:4]*45>=-8-1e-5)&(v[:,:4]*45<=20+1e-5)
            persist=torch.where(occ,torch.full_like(z,4.,dtype=torch.float32),torch.full_like(z,-4.,dtype=torch.float32))
        else:persist=v[:,4:7]*4
        persistence=evaluate(persist,z)
    for _ in range(epochs):
        opt.zero_grad();loss=lossfn(model(x),y);loss.backward();opt.step()
    with torch.no_grad():
        logit=model(v);final=evaluate(logit,z);training=evaluate(model(x),y)
        fixed=(persist>=0).long() if binary else persist.argmax(-1);truth=z.long();guess=(logit>=0).long() if binary else logit.argmax(-1)
        miss=fixed!=truth;nonpersistent=dict(count=int(miss.sum()),model_accuracy=float((guess[miss]==truth[miss]).float().mean()) if miss.any() else None,scope='PUBLIC_PERSISTENCE_DISAGREEMENT_NOT_FORMAL_TRANSITION')
    return model,dict(head=head,scope='DECLARED_MODEL_ISOLATED_HEAD_NOT_FULL_REA',training_rows=len(train),validation_rows=len(val),initial=initial,constant_baseline=base,public_persistence_baseline=persistence,nonpersistent=nonpersistent,final=final,training=training,formal_sc=False)


def fit_transition_head(train,val,head,*,context=True,seed=7,epochs=100,frozen_model=None):
    """Independent finite-horizon first-change classification or occupancy.
    No formal or real-world authorization; fixed epochs, no validation tuning.
    Compare public persistence, training-only age-conditioned empirical hazard,
    and observed-motion geometric CV. Full-window targets only.
    """
    if head not in HEADS or not train or not val or {r['family_id'] for r in train}&{r['family_id'] for r in val}:raise ValueError('head/family split')
    H=train[0]['horizon']; binary=head=='occupancy'
    def tensors(rows,split):
        keys=set()
        for r in rows:
            key=(r['run_digest'],r['tick'])
            if key in keys:raise ValueError('duplicate row')
            keys.add(key)
            if r['digest']!=canonical_digest({k:v for k,v in r.items() if k!='digest'}) or r['schema']!='rampd.shared_resource_transition.v1' or r['domain']!='DECLARED_2D_AFFINE_MODEL_ONLY' or r['split']!=split or r['horizon']!=H or r['model_training_allowed']!=(split=='training') or r['real_world_training_allowed'] is not False or r['formal_sc'] is not False or set(r['formal_heads'])!={'event','joint','occupancy','observation','causal','viability','margin','deadline'} or any(r['formal_heads'].values()) or r['field_valid'][head] is not True:raise ValueError('label domain/permission')
        x=torch.tensor([r['public_inputs'] for r in rows],dtype=torch.float32);y=torch.tensor([r['targets'][head] for r in rows]);
        if not torch.isfinite(x).all() or x.shape[1]!=17 or (binary and (y.shape[1:]!=(H,4) or not ((y==0)|(y==1)).all())) or (not binary and not ((y>=0)&(y<=H)).all()):raise ValueError('shape/target')
        return x,y.float() if binary else y.long()
    x,y=tensors(train,'training');v,z=tensors(val,'validation');dim=17 if context else 8
    if frozen_model is not None:
        if epochs!=0:raise ValueError('frozen evaluation requires zero training epochs')
        model=frozen_model;opt=None
    else:
        torch.manual_seed(seed);model=nn.Sequential(nn.Linear(dim,64),nn.SiLU(),nn.Linear(64,64),nn.SiLU(),nn.Linear(64,H*4 if binary else H+1));opt=torch.optim.AdamW(model.parameters(),lr=.005)
    def logits(a):
        l=model(a[:,:dim]);return l.reshape(-1,H,4) if binary else l
    lossfn=nn.functional.binary_cross_entropy_with_logits if binary else nn.functional.cross_entropy
    def ap(score,truth):
        s=score.flatten();t=truth.flatten().bool();n=int(t.sum());
        if not n:return None
        # Group ties; AP integrates precision at each distinct score threshold.
        order=s.argsort(descending=True);s=s[order];t=t[order];end=torch.cat((s[:-1]!=s[1:],torch.ones(1,dtype=torch.bool)));tp=t.cumsum(0)[end];count=torch.arange(1,len(s)+1)[end];return float(((tp-torch.cat((torch.zeros(1,dtype=tp.dtype),tp[:-1])))*tp/count).sum()/n)
    def evaluate(l):
        if binary:
            p=l.sigmoid();pred=p>=.5;truth=z.bool();cur=torch.tensor([r['public_current_occupancy'] for r in val]).bool()[:,None,:].expand_as(truth);change=truth!=cur;change_score=torch.where(cur,1-p,p)
            return dict(loss=float(lossfn(l,z)),accuracy=float((pred==truth).float().mean()),positive_AP=ap(p,truth),change_AP=ap(change_score,change),change_count=int(change.sum()),change_recall=float((pred[change]==truth[change]).float().mean()) if change.any() else None,brier=float((p-z).square().mean()))
        p=l.softmax(-1);pred=p.argmax(-1);pos=z>0;change=1-p[:,0];pred_time=p[:,1:].argmax(-1)+1
        return dict(loss=float(lossfn(l,z)),accuracy=float((pred==z).float().mean()),change_AP=ap(change,pos),change_count=int(pos.sum()),change_recall=float((pred[pos]>0).float().mean()) if pos.any() else None,conditional_time_MAE_ticks=float((pred_time[pos]-z[pos]).abs().float().mean()) if pos.any() else None,brier=float((change-pos.float()).square().mean()))
    with torch.no_grad():
        initial=evaluate(logits(v))
        if binary:
            prior=y.mean(0).clamp(.001,.999).logit().expand_as(z)
            current=torch.tensor([r['public_current_occupancy'] for r in val]).float()[:,None,:].expand_as(z);cv=torch.tensor([r['cv_geometry'] for r in val]).float();persist=(current*.96+.02).logit();geom=(cv*.96+.02).logit();baselines=dict(constant=evaluate(prior),persistence=evaluate(persist),cv_geometry=evaluate(geom))
        else:
            counts=torch.bincount(y,minlength=H+1).float()+1;prior=counts.log().expand(len(z),-1);persist=torch.full_like(prior,-5.);persist[:,0]=0
            # Age bins and current permission from observed history, training only.
            def keys(a):return list(zip(a[:,4:7].argmax(-1).tolist(),(a[:,7]*40//4).long().tolist()))
            table={}
            for key,target in zip(keys(x),y):table.setdefault(key,torch.ones(H+1))[target]+=1
            hazard=torch.stack([table.get(key,counts).log() for key in keys(v)])
            baselines=dict(constant=evaluate(prior),persistence=evaluate(persist),empirical_public_age=evaluate(hazard))
    for _ in range(epochs):
        opt.zero_grad();loss=lossfn(logits(x),y);loss.backward();opt.step()
    with torch.no_grad():final=evaluate(logits(v))
    return model,dict(head=head,context=context,horizon=H,training_rows=len(train),validation_rows=len(val),initial=initial,baselines=baselines,final=final,formal_sc=False,scope='DECLARED_MODEL_FULL_WINDOW_TRANSITIONS_ONLY')
