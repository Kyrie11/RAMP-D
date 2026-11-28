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
