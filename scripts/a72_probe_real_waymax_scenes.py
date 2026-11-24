#!/usr/bin/env python3
"""Read actual WOMD TFExample trajectories with Waymax: NO actor overwrite.

This is deliberately separate from probe_waymax_response.py, which uses an
actual shard only to obtain a state template then *overwrites* both actors.
One bounded shard/sample is for smoke and diagnosis; use Scenario protobuf
for full scenario ID, map-change and dynamic-map semantics downstream.
"""
from __future__ import annotations
import argparse,hashlib,json,sys,math,dataclasses
from pathlib import Path


def _digest(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda:f.read(2*1024*1024),b''):h.update(chunk)
    return h.hexdigest()


def summarize_arrays(valid, types, is_sdc, x,y,vx,vy):
    import numpy as np
    valid=np.asarray(valid,dtype=bool);types=np.asarray(types);sdc=np.asarray(is_sdc,dtype=bool)
    arrays=[np.asarray(v) for v in (x,y,vx,vy)]
    if valid.ndim!=2 or any(a.shape!=valid.shape for a in arrays):raise ValueError('trajectory shape mismatch')
    if sdc.ndim!=1 or types.ndim!=1 or not valid.shape[1] or len(sdc)!=len(types) or len(sdc)!=valid.shape[0] or int(sdc.sum())!=1:raise ValueError('invalid SDC metadata')
    if not np.all(np.isfinite(np.stack([a[valid] for a in arrays]))):raise ValueError('nonfinite observed trajectories')
    ego=int(np.flatnonzero(sdc)[0]);
    if not valid[ego].any():raise ValueError("no valid ego samples")
    active=valid.any(axis=1);dur=(valid.sum(axis=1)).tolist()
    return dict(objects_present_any_time=int(active.sum()),sdc_track_index=ego,
        sdc_valid_steps=int(valid[ego].sum()),trajectory_steps=int(valid.shape[1]),
        agent_types_count={str(v):int(sum((types==v)&active)) for v in np.unique(types)},
        agents_at_first_step=int(valid[:,0].sum()),agents_at_last_step=int(valid[:,-1].sum()),
        mean_valid_steps_per_active=float(sum(dur)/max(1,sum(active))),
        consecutive_valid_actor_pairs=int((valid[:,1:] & valid[:,:-1]).sum()),
        actual_logged_coordinates_not_synthetic=True)

def run(source:Path, limit:int):
    import numpy as np
    from waymax import config,dataloader
    if not source.is_file() or limit<1 or limit>50:raise ValueError('existing shard and bounded sample 1..50 required')
    cfg=dataclasses.replace(config.WOD_1_3_1_VALIDATION,path=str(source.resolve()),max_num_objects=128,
        repeat=1,num_shards=1,batch_dims=(),deterministic=True,shuffle_seed=None)
    gen=dataloader.simulator_state_generator(config=cfg)
    records=[];source_digest=_digest(source)
    for i in range(limit):
        try:state=next(gen)
        except StopIteration:break
        traj=state.log_trajectory
        r=summarize_arrays(np.asarray(traj.valid),np.asarray(state.object_metadata.object_types),
             np.asarray(state.object_metadata.is_sdc),np.asarray(traj.x),np.asarray(traj.y),
             np.asarray(traj.vel_x),np.asarray(traj.vel_y))
        r['source_index_in_shard']=i;r['loader_local_id']=source_digest+':'+str(i);r['official_scenario_id_verified']=False;r['map_points_present']=getattr(state,'roadgraph_points',None) is not None
        records.append(r)
    if not records:raise ValueError('source shard provided no state')
    return dict(schema='rampd.a72.waymax.real_womd_inventory.v1',
        status='DESCRIPTIVE_REAL_WOMD_SCENARIOS_SAMPLED',source_shard_sha256=source_digest,
        source_shard_name=source.name,real_records=records,
        physical_effectivity_and_message_receipt_observed=False,
        real_sdc_other_actor_factual_records_only=True,
        counterfactual_driver_response_proved=False,formal_safety_labels_allowed=False)

def main():
    p=argparse.ArgumentParser();p.add_argument('--tf-example-file',type=Path,required=True)
    p.add_argument('--max-scenarios',type=int,default=5);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args()
    if a.output.exists():raise SystemExit('REFUSE_OVERWRITE')
    try:r=run(a.tf_example_file,a.max_scenarios)
    except Exception as e:r=dict(status='REVIEW',reason=f'{type(e).__name__}:{e}',formal_safety_labels_allowed=False)
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(r,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
    print(r['status']);return 0 if r['status'].startswith('DESCRIPTIVE') else 4
if __name__=='__main__':raise SystemExit(main())
