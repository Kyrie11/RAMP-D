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
