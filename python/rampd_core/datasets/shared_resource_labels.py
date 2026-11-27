"""Model-domain-only supervised records derived from independently audited runs.
No import into factual cache or formal proof labels. Family-level split required.
The public view assumes all four declared centers are locally observable; the
controller's hidden command, ACK and next state never enter feature construction.
"""
from .shared_resource_scenario import audit,ROSTER
from .split_manifest import canonical_digest

HEADS=('event','occupancy','observation')
SIGNAL={None:0,'RED':0,'A':1,'B':2}

def release(run, *, split):
    if split not in ('training','validation'):raise ValueError('explicit split')
    checked=audit(run)
    if not checked['ok'] or not checked['completed'] or not checked['ego_completed'] or not all(checked['entries'].values()) or not all(checked['exits'].values()):raise ValueError('shared resource label gate')
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
