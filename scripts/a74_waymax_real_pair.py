#!/usr/bin/env python3
"""Bounded real-log initialized IDM AA/AB smoke, not causal real-world truth.
Baseline and intervention follow the same logged geometric route (future route
privileged, offline model-only); all active vehicles respond via IDM, others
replay logs. Reject missing active controlled states rather than imputing.
"""
import argparse,dataclasses,hashlib,inspect,itertools,json,math
from pathlib import Path

def run(path,limit,steps):
    import numpy as np
    import jax.numpy as jnp
    from waymax import config,dataloader,datatypes,dynamics,agents
    cfg=dataclasses.replace(config.WOD_1_3_1_VALIDATION,path=str(path.resolve()),max_num_objects=128,repeat=1,num_shards=1,batch_dims=(),deterministic=True,shuffle_seed=None)
    results=[]
    for idx,state in enumerate(itertools.islice(dataloader.simulator_state_generator(config=cfg),limit)):
        try:
            log=state.log_trajectory;ego=int(np.flatnonzero(np.asarray(state.object_metadata.is_sdc))[0]);v=np.asarray(log.valid)
            if not v[ego,10:11+steps].all():raise ValueError('ego route missing')
            root=state.replace(sim_trajectory=datatypes.fill_invalid_trajectory(log),timestep=jnp.array(-1));root=datatypes.update_state_by_log(root,11)
            active=np.asarray(root.current_sim_trajectory.valid)[:,0];types=np.asarray(state.object_metadata.object_types);mask=active&(types==1)
            if not mask[ego] or mask.sum()<2:raise ValueError('no active vehicle response pair')
            controlled=jnp.asarray(mask);dyn=dynamics.StateDynamics()
            def rollout(intervene):
                policy=agents.IDMRoutePolicy(desired_vel=13.9,min_spacing=2.,safe_time_headway=1.5,max_accel=2.,max_decel=3.,additional_lookahead_points=30,additional_lookahead_distance=30.,invalidate_on_end=False)
                st=root;rows=[]
                def snapshot():
                    tr=st.current_sim_trajectory
                    if not np.asarray(tr.valid)[mask,0].all():raise ValueError('controlled actor disappeared')
                    a=np.stack([np.asarray(getattr(tr,k))[mask,0] for k in ('x','y','yaw','vel_x','vel_y')],axis=-1)
                    if not np.isfinite(a).all():raise ValueError('nonfinite rollout')
                    return a
                rows.append(snapshot())
                for k in range(steps):
                    u=policy.update_trajectory(st).as_action();valid=np.asarray(u.valid)[:,0]
                    if not valid[mask].all():raise ValueError('invalid IDM controlled action')
                    data=u.data
                    if intervene:
                        # Override ego with bounded constant-heading braking, NOT a real vehicle or route certificate.
                        tr=st.current_sim_trajectory;x,y,yaw,vx,vy=[float(np.asarray(getattr(tr,f))[ego,0]) for f in ('x','y','yaw','vel_x','vel_y')]
                        speed=math.hypot(vx,vy);n=max(0.,speed-.2);distance=(speed+n)*.05
                        data=data.at[ego].set(jnp.asarray([x+distance*math.cos(yaw),y+distance*math.sin(yaw),yaw,n*math.cos(yaw),n*math.sin(yaw)],dtype=data.dtype))
                    else:
                        data=data.at[ego].set(jnp.asarray([np.asarray(getattr(log,f))[ego,11+k] for f in ('x','y','yaw','vel_x','vel_y')],dtype=data.dtype))
                    action=datatypes.Action(data=data,valid=controlled[:,None]);tr=dyn.forward(action=action,trajectory=st.sim_trajectory,reference_trajectory=log,is_controlled=controlled,timestep=st.timestep,allow_object_injection=False);st=st.replace(sim_trajectory=tr,timestep=st.timestep+1);rows.append(snapshot())
                return np.stack(rows)
            A=rollout(False);AA=rollout(False);B=rollout(True);ei=list(np.flatnonzero(mask)).index(ego);other=np.arange(mask.sum())!=ei
            factual=np.stack([np.asarray(getattr(log,k))[mask,10:11+steps] for k in ('x','y')],axis=-1).transpose(1,0,2);valid=v[mask,10:11+steps].T
            error=np.linalg.norm(A[:,:,:2]-factual,axis=-1);row=dict(index=idx,status='MODEL_CONDITIONAL_PAIR',controlled_actors=int(mask.sum()),aa_max_abs=float(np.max(abs(A-AA))),ego_ab_max_displacement_m=float(np.max(np.linalg.norm(A[:,ei,:2]-B[:,ei,:2],axis=-1))),other_ab_max_displacement_m=float(np.max(np.linalg.norm(A[:,other,:2]-B[:,other,:2],axis=-1))),other_first_step_difference=float(np.max(abs(A[1,other]-B[1,other]))),factual_A_masked_ADE_m=float(error[:,other][valid[:,other]].mean()),factual_valid_samples=int(valid[:,other].sum()),controlled_indices=np.flatnonzero(mask).tolist(),A=A.tolist(),AA=AA.tolist(),B=B.tolist(),future_route_privileged=True,baseline_ego_logged_next_state=True)
            if row['aa_max_abs']>1e-5 or row['other_first_step_difference']>1e-5:row['status']='REVIEW_PAIR_CONSISTENCY'
            results.append(row)
        except Exception as e:results.append(dict(index=idx,status='REVIEW',reason=type(e).__name__+': '+str(e)))
    digest=hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda:f.read(1024*1024),b''):digest.update(chunk)
    return dict(source_sha256=digest.hexdigest(),status='DESCRIPTIVE_MODEL_PAIR_PROBE' if results and all(r['status']=='MODEL_CONDITIONAL_PAIR' for r in results) else 'REVIEW',records=results,idm_source_sha256=hashlib.sha256(inspect.getsource(agents.IDMRoutePolicy).encode()).hexdigest(),scope='OFFLINE_LOG_ROUTE_IDM_WITH_OTHER_TYPES_PLAYBACK',real_counterfactual_proved=False,formal_labels_authorized=False)

def main():
    p=argparse.ArgumentParser();p.add_argument('--tf-example-file',type=Path,required=True);p.add_argument('--max-scenarios',type=int,default=5);p.add_argument('--steps',type=int,default=10);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    if a.output.exists() or not 1<=a.max_scenarios<=50 or not 1<=a.steps<=30:raise SystemExit('bad arguments or existing output')
    try:r=run(a.tf_example_file,a.max_scenarios,a.steps)
    except Exception as e:r=dict(status='REVIEW',reason=type(e).__name__+': '+str(e),formal_labels_authorized=False)
    a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(r,indent=2,allow_nan=False)+'\n');print(r['status']);return 0 if r['status'].startswith('DESCRIPTIVE') else 4
if __name__=='__main__':raise SystemExit(main())
