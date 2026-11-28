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


def fit_relation_head(train, evaluations, head, *, variant='gated', seed=7, epochs=15, frozen_weights=None):
    """Family-disjoint fixed-budget typed relation ablation. No formal labels."""
    from .relation_context import RelationPilot,SOURCES,WIDTH
    if head not in (*HEADS,'start') or not train or not evaluations:raise ValueError('head/evaluation')
    H=train[0]['horizon'];families={r['family_id'] for r in train}
    def tensors(rows,split):
        if not rows or (split!='training' and families & {r['family_id'] for r in rows}):raise ValueError('family overlap')
        seen=set()
        for r in rows:
            key=(r['run_digest'],r['tick'])
            if key in seen or r['digest']!=canonical_digest({k:v for k,v in r.items() if k!='digest'}) or r['schema']!='rampd.shared_resource_relation.v1' or r['domain']!='DECLARED_2D_AFFINE_MODEL_ONLY' or r['split']!=split or r['horizon']!=H or r['model_training_allowed'] is not (split=='training') or r['real_world_training_allowed'] is not False or r['formal_sc'] is not False or set(r['formal_heads'])!={'event','joint','occupancy','observation','causal','viability','margin','deadline'} or any(r['formal_heads'].values()):raise ValueError('relation label gate')
            seen.add(key)
            if head!='start' and r['field_valid'][head] is not True:raise ValueError('missing target')
            if head=='start' and r['field_valid'][head]!=any(r['start_mask']):raise ValueError('start validity')
        x=torch.tensor([r['tokens'] for r in rows],dtype=torch.float32);m=torch.tensor([r['available'] for r in rows],dtype=torch.bool);y=torch.tensor([r['targets'][head] for r in rows]);valid=torch.tensor([r['start_mask'] for r in rows],dtype=torch.bool) if head=='start' else torch.ones_like(y,dtype=torch.bool)
        if x.shape[1:]!=(4,len(SOURCES),WIDTH) or m.shape!=x.shape[:-1] or not torch.isfinite(x).all() or (m[:,1:,4]).any():raise ValueError('public input shape/private info')
        if head in ('event','observation'):
            if y.shape!=(len(rows),) or not ((y>=0)&(y<=H)).all():raise ValueError('time target')
        elif y.shape[1:]!=((H,4) if head=='occupancy' else (4,)) or not ((y==0)|(y==1)).all() or (head=='start' and valid[:,0].any()):raise ValueError('binary target')
        return x,m,y,valid
    x,m,y,valid=tensors(train,'training');ev={k:tensors(v,'validation') for k,v in evaluations.items()}
    torch.manual_seed(seed);model=RelationPilot(H,head,variant);opt=torch.optim.AdamW(model.parameters(),lr=.003);rng=torch.Generator().manual_seed(seed)
    temporal=head in ('event','observation')
    def loss(l,t,mask):return nn.functional.nll_loss(l,t.long()) if temporal else nn.functional.binary_cross_entropy_with_logits(l[mask],t[mask].float())
    def ap(s,t):
        s=s.flatten();t=t.flatten().bool();n=int(t.sum())
        if not n:return None
        order=s.argsort(descending=True);s=s[order];t=t[order];end=torch.cat((s[:-1]!=s[1:],torch.ones(1,dtype=torch.bool)));tp=t.cumsum(0)[end];count=torch.arange(1,len(s)+1)[end];return float(((tp-torch.cat((torch.zeros(1,dtype=tp.dtype),tp[:-1])))*tp/count).sum()/n)
    def evaluate(l,t,mask,rows):
        if temporal:
            p=l.exp();pos=t>0;return dict(loss=float(loss(l,t,mask)),change_AP=ap(1-p[:,0],pos),conditional_time_MAE_ticks=float((p[:,1:].argmax(-1)[pos]+1-t[pos]).abs().float().mean()) if pos.any() else None,change_count=int(pos.sum()),accuracy=float((l.argmax(-1)==t).float().mean()))
        p=l.sigmoid();r=dict(loss=float(loss(l,t,mask)),positive_AP=ap(p[mask],t[mask]),positives=int(t[mask].sum()),valid=int(mask.sum()),brier=float((p[mask]-t[mask]).square().mean()))
        if head=='occupancy':
            cur=torch.tensor([q['public_current_occupancy'] for q in rows]).bool()[:,None,:].expand_as(t);r['change_AP']=ap(torch.where(cur,1-p,p),t.bool()!=cur)
        return r
    def keys(a,conditional):
        q=a[:,0,3]; base=list(zip(q[:,:3].argmax(-1).tolist(),(q[:,3]*40).round().long().div(4,rounding_mode='floor').tolist()))
        return [(*k,int(round(float(g)*40)),int(round(float(c)*8))) for k,g,c in zip(base,q[:,4],q[:,5])] if conditional else base
    tables=[]
    if temporal:
        counts=torch.bincount(y,minlength=H+1).float()+1
        for conditional in (False,True):
            d={}
            for k,t in zip(keys(x,conditional),y):d.setdefault(k,torch.ones(H+1))[t]+=1
            tables.append(d)
    start_table={}
    def start_keys(a):
        # Per-actor public context only; bin distance and leader-gap, plus public permit age.
        mo=a[:,:,0];ne=a[:,:,1];ru=a[:,:,3];return list(zip((mo[:,:,0]*45).round().long().div(4,rounding_mode='floor').flatten().tolist(),mo[:,:,3].long().flatten().tolist(),ru[:,:,:3].argmax(-1).flatten().tolist(),(ru[:,:,3]*40).round().long().div(4,rounding_mode='floor').flatten().tolist(),(ne[:,:,0]*60).round().long().clamp(0,60).div(4,rounding_mode='floor').flatten().tolist(),ne[:,:,4].long().flatten().tolist()))
    if head=='start':
        for k,t,ok in zip(start_keys(x),y.flatten(),valid.flatten()):
            if ok:start_table.setdefault(k,torch.ones(2))[int(t)]+=1
    report=dict(head=head,variant=variant,seed=seed,epochs=epochs,training_rows=len(train),formal_sc=False,scope='DECLARED_RELATION_PILOT_ONLY',evaluations={})
    def check():
        result={}
        with torch.no_grad():
            for name,(a,b,t,mask) in ev.items():
                l,w=model(a,b);r=evaluate(l,t,mask,evaluations[name]);r['rows']=len(t)
                if w is not None:r['mean_source_weights']={s:float(w[:,:,i].mean()) for i,s in enumerate(SOURCES)}
                if temporal:
                    probs=[]
                    for conditional,d in zip((False,True),tables):
                        p=torch.stack([d.get(k,counts) if not conditional else d.get(k,tables[0].get(k[:2],counts)) for k in keys(a,conditional)]);probs.append(evaluate(p.log().log_softmax(-1),t,mask,evaluations[name]))
                    r['age_baseline'],r['protocol_age_baseline']=probs
                elif head=='occupancy':
                    cv=torch.tensor([q['cv_geometry'] for q in evaluations[name]]).float();r['cv_geometry_baseline']=evaluate((.02+.96*cv).logit(),t,mask,evaluations[name])
                else:
                    prior=y[valid].float().mean().clamp(.001,.999);r['constant_baseline']=evaluate(prior.logit().expand_as(t),t,mask,evaluations[name]);cue=a[:,:,1,1].clamp(0,1)*.45+.05;r['leader_motion_baseline']=evaluate(cue.logit(),t,mask,evaluations[name]);ep=torch.tensor([float(start_table[k][1]/start_table[k].sum()) if k in start_table else float(prior) for k in start_keys(a)]).reshape_as(t);r['public_context_baseline']=evaluate(ep.logit(),t,mask,evaluations[name])
                result[name]=r
        return result
    report['initial']=check();steps=0
    if frozen_weights is not None:
        if epochs!=0:raise ValueError('frozen replay requires zero epochs')
        model.load_state_dict(frozen_weights)
    for _ in range(epochs):
        for ix in torch.randperm(len(x),generator=rng).split(256):
            if not valid[ix].any():continue
            opt.zero_grad();l,_=model(x[ix],m[ix]);err=loss(l,y[ix],valid[ix]);err.backward();torch.nn.utils.clip_grad_norm_(model.parameters(),5,error_if_nonfinite=True);opt.step();steps+=1
    report['optimizer_steps']=steps;report['evaluations']=check();return model,report
