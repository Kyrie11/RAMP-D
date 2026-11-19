#!/usr/bin/env python3
"""Paired, synthetic straight-route test of installed Waymax IDMRoutePolicy.
Uses WOMD state as shape/template only; overwrites trajectories with two known
vehicles. Not factual data, real response truth, or production labels.
"""
import argparse,json,math,hashlib,inspect
from pathlib import Path
from importlib.metadata import version
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"python"))


def run(path,steps,profile="constant"):
    from rampd_core.a55_motion import forward_arc
    from rampd_core.a56_motion import smooth_stop_profile,idm_net_gap
    smooth=smooth_stop_profile(steps) if profile=="smooth-stop" else None
    import dataclasses
    import numpy as np
    import jax.numpy as jnp
    from waymax import config,dataloader,datatypes,dynamics,agents
    cfg=dataclasses.replace(config.WOD_1_3_1_VALIDATION,path=str(path.resolve()),max_num_objects=128,repeat=1,num_shards=1,batch_dims=(),deterministic=True,shuffle_seed=None)
    template=next(dataloader.simulator_state_generator(config=cfg))
    # Preserve shapes and metadata (SDC identity); replace all motion and validity.
    sdc=np.flatnonzero(np.asarray(template.object_metadata.is_sdc));
    if len(sdc)!=1:raise ValueError('expected unique SDC')
    ego=int(sdc[0]); follower=next(i for i in range(128) if i!=ego)
    traj=template.log_trajectory
    if traj.shape!=(128,91):raise ValueError('unexpected trajectory shape')
    valid=np.zeros((128,91),bool);valid[[ego,follower],:]=True
    # Initial t=10: ego center =25 m; follower=10 m, both 10 m/s.
    fields={}
    for name in ('x','y','z','yaw','vel_x','vel_y','length','width','height'):
        arr=np.full((128,91),-1.,np.float32)
        for idx,offset in ((ego,15.),(follower,0.)):
            arr[idx,:]=offset+np.arange(91) if name=='x' else {'y':0.,'z':0.,'yaw':0.,'vel_x':10.,'vel_y':0.,'length':4.5,'width':1.8,'height':1.5}[name]
        fields[name]=jnp.asarray(arr)
    ts=np.full((128,91),-1,np.int32);ts[[ego,follower],:]=np.arange(91,dtype=np.int32)*100000
    log=traj.replace(**fields,valid=jnp.asarray(valid),timestamp_micros=jnp.asarray(ts))
    # Synthetic identities/types, never retain unrelated factual actor metadata.
    active=jnp.asarray(valid[:,0]); ids=jnp.full((128,),-1,jnp.int32).at[ego].set(1).at[follower].set(2)
    metadata=template.object_metadata.replace(ids=ids,object_types=jnp.where(active,1,0).astype(jnp.int32),is_valid=active,is_modeled=active,objects_of_interest=active,is_controlled=active)
    sim=datatypes.fill_invalid_trajectory(log)
    root=template.replace(log_trajectory=log,sim_trajectory=sim,object_metadata=metadata,timestep=jnp.array(-1),roadgraph_points=None,sdc_paths=None);root=datatypes.update_state_by_log(root,11)
    if int(root.timestep)!=10:raise ValueError('bad initial timestep')
    policy=agents.IDMRoutePolicy(desired_vel=13.9,min_spacing=2.,safe_time_headway=1.5,max_accel=2.,max_decel=3.,additional_lookahead_points=30,additional_lookahead_distance=30.,invalidate_on_end=False)
    dyn=dynamics.StateDynamics()
    mask=jnp.asarray(np.arange(128)==ego)|jnp.asarray(np.arange(128)==follower)
    def rollout(acc):
        state=root;rows=[]
        def snapshot():
            tr=state.current_sim_trajectory
            if not bool(np.asarray(tr.valid)[[ego,follower],0].all()):raise ValueError('active synthetic actor disappeared')
            v=np.asarray(tr.valid)[:,0]
            if int(v.sum())!=2:raise ValueError('unexpected valid actor injection')
            a=np.array([[float(np.asarray(getattr(tr,k))[idx,0]) for k in ('x','y','yaw','vel_x','vel_y')] for idx in (ego,follower)])
            if not np.isfinite(a).all():raise ValueError('nonfinite state')
            return a
        rows.append(snapshot().tolist())
        for k in range(steps):
            old=snapshot();x,y,psi,vx,vy=old[0]
            if smooth is not None and acc<0:
                target_x,target_v,_=smooth[k+1];ego_next=(25.+float(target_x),0.,0.,float(target_v),0.)
            else:ego_next=forward_arc(x,y,psi,math.hypot(vx,vy),acc,0.,.1)
            # Both decisions use the same pre-step state. No updated ego leakage.
            u=policy.update_trajectory(state).as_action()
            if not bool(np.asarray(u.valid)[follower,0]):raise ValueError('invalid IDM response')
            action=datatypes.Action(data=u.data.at[ego].set(jnp.asarray(ego_next,dtype=jnp.float32)),valid=mask[:,None])
            tr=dyn.forward(action=action,trajectory=state.sim_trajectory,reference_trajectory=state.log_trajectory,is_controlled=mask,timestep=state.timestep,allow_object_injection=False)
            state=state.replace(sim_trajectory=tr,timestep=state.timestep+1)
            new=snapshot()
            if int(state.timestep)!=11+k or (new[:,0]<old[:,0]-1e-5).any() or (new[:,3]<-1e-5).any() or abs(new[:,1]).max()>1e-4:raise ValueError('straight forward fixture violated')
            rows.append(new.tolist())
        return np.asarray(rows)
    a=rollout(0.);aa=rollout(0.);b=rollout(-3.)
    diff=float(np.max(np.abs(a-aa))); ego_diff=float(np.max(np.abs(a[:,0,0]-b[:,0,0]))); follower_diff=float(np.max(np.abs(a[:,1,3]-b[:,1,3])))
    # Check direction of causal response, consecutive state integration, and collisions as separate outcomes.
    min_gap=min(float(np.min(r[:,0,0]-r[:,1,0]-4.5)) for r in (a,b))
    max_residual=max(float(np.max(np.abs(np.diff(r[:,:,0],axis=0)-.05*(r[1:,:,3]+r[:-1,:,3])))) for r in (a,b))
    # Trapezoid is exact for constant acceleration, not nonzero jerk. Compare
    # the smooth ego path against its exact reference and keep follower separate.
    ego_smooth_error=None
    if smooth is not None:
        expect=np.array([[25.+float(x),float(v)] for x,v,_ in smooth]);ego_smooth_error=float(np.max(np.abs(b[:,0,:][:,[0,3]]-expect)))
    follower_residual=max(float(np.max(np.abs(np.diff(r[:,1,0])-.05*(r[1:,1,3]+r[:-1,1,3])))) for r in (a,b))
    initial_gap=10.5; initial_ref=idm_net_gap(10.,10.,initial_gap)
    initial_measured=float((a[1,1,3]-a[0,1,3])/.1)
    first_step_equal=bool(np.allclose(a[1,1],b[1,1],atol=1e-5,rtol=0))
    good=diff<=1e-5 and ego_diff>0.1 and follower_diff>0.05 and b[-1,1,3]<a[-1,1,3] and first_step_equal and min_gap>0 and max_residual<.02 and (ego_smooth_error is None or ego_smooth_error<2e-5)
    return dict(status='SYNTHETIC_IDM_RESPONSE_PASS' if good else 'REVIEW_REQUIRED',scope='SYNTHETIC_TWO_VEHICLE_STRAIGHT_ROUTE_ONLY',waymax=version('waymo-waymax'),idm_source_sha256=hashlib.sha256(inspect.getsource(agents.IDMRoutePolicy).encode()).hexdigest(),dt_s=.1,steps=steps,ego_control_profile=profile,initial_geometric_gap_m=initial_gap,initial_net_gap_idm_accel_mps2=initial_ref,initial_measured_idm_accel_mps2=initial_measured,smooth_ego_reference_max_abs_error=ego_smooth_error,follower_trapezoid_residual_m=follower_residual,continuous_jerk_certificate=False,aa_max_state_difference=diff,ab_max_ego_position_difference_m=ego_diff,ab_max_follower_speed_difference_mps=follower_diff,first_step_follower_equal=first_step_equal,min_signed_bumper_gap_m=min_gap,max_trapezoid_position_residual_m=max_residual,actor_order=['ego','follower'],state_order=['x','y','yaw','vx','vy'],rollouts={'A':a.tolist(),'AA':aa.tolist(),'B':b.tolist()},counterfactual_training_labels_generated=False,real_scene_used=False,safety_certified=False)


def main():
    p=argparse.ArgumentParser();p.add_argument('--tf-example-file',type=Path,required=True);p.add_argument('--steps',type=int,default=25);p.add_argument('--profile',choices=('constant','smooth-stop'),default='constant');p.add_argument('--output',type=Path,required=True);p.add_argument('--plot',type=Path);a=p.parse_args()
    try:
        if (a.profile=='constant' and not 10<=a.steps<=30) or (a.profile=='smooth-stop' and not 50<=a.steps<=70):raise ValueError('constant fixture requires 10..30 steps; smooth-stop 50..70')
        out=run(a.tf_example_file,a.steps,a.profile)
        if a.plot:
            import matplotlib;matplotlib.use('Agg')
            import matplotlib.pyplot as plt
            for key in ('A','B'):
                r=out['rollouts'][key];t=[i*.1 for i in range(len(r))]
                plt.plot(t,[x[0][3] for x in r],label=f'{key} ego');plt.plot(t,[x[1][3] for x in r],label=f'{key} follower')
            plt.xlabel('time (s)');plt.ylabel('speed (m/s)');plt.title('Synthetic Waymax IDM response');plt.legend();plt.tight_layout();a.plot.parent.mkdir(parents=True,exist_ok=True);plt.savefig(a.plot,dpi=150);plt.close()
    except Exception as e:
        import traceback
        out=dict(status='ERROR',reason=f'{type(e).__name__}: {e}',traceback=traceback.format_exc(),counterfactual_training_labels_generated=False)
    a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(out,indent=2,allow_nan=False)+'\n');return 0 if out['status']=='SYNTHETIC_IDM_RESPONSE_PASS' else 4
if __name__=='__main__':raise SystemExit(main())
