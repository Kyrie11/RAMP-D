"""Model-domain-only supervised records derived from independently audited runs.
No import into factual cache or formal proof labels. Family-level split required.
The public view assumes all four declared centers are locally observable; the
controller's hidden command, ACK and next state never enter feature construction.
"""
from .shared_resource_scenario import audit,simulate,ROSTER
from .split_manifest import canonical_digest

HEADS=('event','occupancy','observation')
SIGNAL={None:0,'RED':0,'A':1,'B':2}

def release(run, *, split):
    if split not in ('training','validation'):raise ValueError('explicit split')
    checked=audit(run)
    if not checked['ok'] or not checked['completed'] or not checked['ego_completed'] or not all(checked['entries'].values()) or not all(checked['exits'].values()):raise ValueError('shared resource label gate')
    # Exact source reexecution is an additional integrity gate, not an
    # independent behavioral oracle. Prevent altered actions/command ages or
    # family renaming from becoming authorized labels by rehashing a ledger.
    if type(run['seed']) is not int or not 0<=run['seed']<=8 or run['family_id']!=f"shared-{run['seed']}":raise ValueError('spacing family identity')
    cfg={k:run[k] for k in ('seed','ego_wait_ticks','ack_delay_ticks','clearance_ticks','steps','green_ticks')}
    if 'release_delays' in run:cfg['release_delays']=run['release_delays']
    if simulate(**cfg)!=run:raise ValueError('source reexecution mismatch')
    rows=[];last_signal=None;age=0
    for f,g in zip(run['frames'],run['frames'][1:]):
        signal=f['public']['e']['signal'];age=age+1 if signal==last_signal else 1;last_signal=signal
        # No hidden controller age, version, ack, true phase or future actions.
        # Public history of signal and observed positions only.
        ids=list(ROSTER);x=[f['state'][i]/45 for i in ids]+[float(SIGNAL[signal]==j) for j in range(3)]+[min(age,40)/40]
        targets=dict(event=SIGNAL[g['controller']['command']['direction']],occupancy=[int(g['occupancy'][i]) for i in ids],observation=SIGNAL[g['public']['e']['signal']])
        row=dict(schema='rampd.shared_resource_labels.v1',domain='DECLARED_2D_AFFINE_MODEL_ONLY',family_id=run['family_id'],split=split,run_digest=run['digest'],tick=f['tick'],public_inputs=x,targets=targets,field_valid={h:True for h in HEADS},model_training_allowed=split=='training',formal_sc=False,real_world_training_allowed=False,formal_heads={h:False for h in ('event','joint','occupancy','observation','causal','viability','margin','deadline')})
        row['digest']=canonical_digest(row);rows.append(row)
    return rows


def transition_rows(run, *, split, horizon=8):
    """Full-window first-change labels, prefix-only inputs, model domain only.
    Class zero means no change in the requested horizon, NOT never occurs.
    Event targets command issuance, Observation targets public permit change.
    Occupancy targets geometric contact at k+h, not continuous swept occupancy.
    """
    from .shared_resource_scenario import _boxes,_occ
    if type(horizon) is not int or not 1<=horizon<=32:raise ValueError('horizon')
    legacy=release(run,split=split)
    if run['family_id']!=f"shared-{run['seed']}" or not 0<=run['seed']<=8:raise ValueError('spacing family identity')
    frames=run['frames']; rows=[]; ids=list(ROSTER)
    for k in range(len(frames)-horizon):
        f=frames[k]; prior=frames[k-1] if k else None
        positions=[f['state'][i] for i in ids]
        velocities=[f['state'][i]-prior['state'][i] if prior else 0 for i in ids]
        signal=SIGNAL[f['public']['e']['signal']]
        # Public-only queue gap and geometric distance to the contact boundary.
        gaps=[min([positions[j]-positions[i] for j in range(len(ids)) if ROSTER[ids[i]]==ROSTER[ids[j]] and positions[j]>positions[i]] or [60]) for i in range(len(ids))]
        base=legacy[k]['public_inputs']; context=base+[v for v in velocities]+[min(g,60)/60 for g in gaps]+[float(prior is not None)]
        # No current hidden command feature; target is first future issuance.
        event=next((h for h in range(1,horizon+1) if frames[k+h]['controller']['command']!=frames[k+h-1]['controller']['command']),0)
        obs=next((h for h in range(1,horizon+1) if SIGNAL[frames[k+h]['public']['e']['signal']]!=signal),0)
        occ=[[int(frames[k+h]['occupancy'][i]) for i in ids] for h in range(1,horizon+1)]
        # Geometry at a predicted CV position, using only prior observed movement.
        cv=[]
        for h in range(1,horizon+1):
            contact=_occ(_boxes({i:min(45,positions[j]+h*velocities[j]) for j,i in enumerate(ids)}))
            cv.append([int(contact[i]) for i in ids])
        row=dict(legacy[k]);row.pop('digest');row.update(schema='rampd.shared_resource_transition.v1',horizon=horizon,public_inputs=context,targets=dict(event=event,observation=obs,occupancy=occ),cv_geometry=cv,public_current_occupancy=[int(f['occupancy'][i]) for i in ids]);row['digest']=canonical_digest(row);rows.append(row)
    return rows



def public_relation_tokens(positions, velocities, *, history_valid, ego_signal, age, public_durations=None):
    """Pure prefix-only feature builder: no simulator ledger, receipt or future arguments."""
    ids=list(ROSTER)
    if len(positions)!=len(ids) or len(velocities)!=len(ids) or ego_signal not in (None,'A','B') or type(age) is not int or age<1:raise ValueError('public prefix')
    p=list(positions);v=list(velocities);signal=ego_signal;tokens=[];available=[]
    green,clear=public_durations if public_durations is not None else (0,0)
    for j,i in enumerate(ids):
        peers=[a for a in range(len(ids)) if ROSTER[ids[a]]==ROSTER[i] and p[a]>p[j]];lead=min(peers,key=lambda a:p[a]) if peers else None
        motion=[p[j]/45,v[j],float(history_valid),float(ROSTER[i]=='A'),float(i=='e'),float(p[j]>=45)]
        neighbor=[0.]*6 if lead is None else [(p[lead]-p[j]-4)/60,v[lead],v[lead]-v[j],float(history_valid),1.,0.]
        # Known resource geometry in this model only; closed contact for either direction.
        resource=[(-8-p[j])/45,(20-p[j])/45,float(-8<=p[j]<=20),sum(-8<=a<=20 for a in p)/4,sum(-8<=p[a]<=20 and ROSTER[ids[a]]!=ROSTER[i] for a in range(4))/4,0.]
        rule=[float(signal=='A'),float(signal=='B'),float(signal is None),min(age,160)/40,green/40,clear/8]
        info=[float(signal==ROSTER[i]),float(signal is None),float(signal is not None and signal!=ROSTER[i]),min(age,160)/40,0.,0.] if i=='e' else [0.]*6
        tokens.append([motion,neighbor,resource,rule,info]);available.append([True,lead is not None,True,True,i=='e'])
    return tokens,available


def relation_rows(run, *, split, horizon=8, public_protocol=True):
    """Independent typed-source dataset; only ego sees its own permit.
    Public protocol durations are a declared experiment assumption; hidden ACK,
    other actors' receipt and future state are never read by feature builder.
    Start = currently stationary non-ego actor moves during next H ticks,
    excluding actors already at terminal. Not identified human intent.
    """
    base=transition_rows(run,split=split,horizon=horizon)
    frames=run['frames'];ids=list(ROSTER);rows=[];age=0;old_signal=object()
    for k,r in enumerate(base):
        f=frames[k];prior=frames[k-1] if k else None
        p=[f['state'][i] for i in ids];v=[p[j]-prior['state'][i] if prior else 0 for j,i in enumerate(ids)]
        signal=f['public']['e']['signal'];age=age+1 if signal==old_signal else 1;old_signal=signal
        tokens,available=public_relation_tokens(p,v,history_valid=prior is not None,ego_signal=signal,age=age,public_durations=(run['green_ticks'],run['clearance_ticks']) if public_protocol else None)
        start=[];start_mask=[]
        for j,i in enumerate(ids):
            valid=i!='e' and prior is not None and v[j]==0 and p[j]<45
            start_mask.append(valid);start.append(int(valid and any(g['state'][i]>p[j] for g in frames[k+1:k+horizon+1])))
        row={key:r[key] for key in ('family_id','split','run_digest','tick','horizon','domain','model_training_allowed','real_world_training_allowed','formal_sc','formal_heads','cv_geometry','public_current_occupancy')}
        row.update(schema='rampd.shared_resource_relation.v1',tokens=tokens,available=available,public_protocol=public_protocol,targets=dict(r['targets'],start=start),start_mask=start_mask,field_valid=dict(r['field_valid'],start=any(start_mask)))
        row['digest']=canonical_digest(row);rows.append(row)
    return rows


def marked_transition_evidence(run, *, split, horizon=8):
    """Conditional next-state mark and permission time evidence, independent of
    the time-only pilot. No positive permission is a safety certificate.
    H+1 or no event is not permanent nonexistence; mark masked on no change.
    Actual permit is controller readback; observed permit is ego view.
    """
    base=transition_rows(run,split=split,horizon=horizon);frames=run['frames'];rows=[]
    for k,r in enumerate(base):
        t=r['targets'];e=t['event'];o=t['observation'];future=frames[k+1:k+horizon+1]
        row=dict(schema='rampd.shared_marked_evidence.v1',family_id=r['family_id'],run_digest=r['run_digest'],split=split,tick=k,horizon=horizon,domain=r['domain'],event_time=e,event_next_direction=None if not e else frames[k+e]['controller']['command']['direction'],observation_time=o,observation_next_permit=None if not o else frames[k+o]['public']['e']['signal'],mark_valid={'event':bool(e),'observation':bool(o)},future_confirmed_entry_permit={d:[g['controller']['permit']==d for g in future] for d in ('A','B')},future_ego_observed_permit=[g['public']['e']['signal']=='A' for g in future],scope='PERMISSION_NOT_COLLISION_FREE_OR_VIABILITY',training_allowed=False,formal_sc=False)
        row['digest']=canonical_digest(row);rows.append(row)
    return rows
