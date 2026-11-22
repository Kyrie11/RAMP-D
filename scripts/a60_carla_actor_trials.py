#!/usr/bin/env python3
"""CARLA 0.9.16 isolated-actor metadata and empirical response capture on the active map.

INVENTORY: read only; CAPTURE: spawn + read metadata (then destroy);
TRIALS: explicit exclusive world assertion, spawn our own actor, own ticks.
Never claims verified physical bounds. Never loads a map, drives an existing
actor, changes friction or resets someone else's CARLA session intentionally.
Use on a dedicated otherwise-empty server; there is no API-level exclusive
world ownership lock across arbitrary remote CARLA clients.
"""
from __future__ import annotations
import argparse,fcntl,hashlib,json,math,sys,traceback
from pathlib import Path


def vec(v):return {k:float(getattr(v,k)) for k in ('x','y','z')}
def rotation(r):return {k+'_deg':float(getattr(r,k)) for k in ('pitch','yaw','roll')}
def finite(x):return math.isfinite(float(x))

def actor_metadata(actor, world, client):
    p=actor.get_physics_control(); bb=actor.bounding_box
    wheel=[]
    for w in p.wheels:
        wheel.append({'position_raw':vec(w.position),'radius_cm_raw':float(w.radius),
                      'tire_friction_raw':float(w.tire_friction),
                      'max_steer_angle_deg_raw':float(w.max_steer_angle),
                      'max_brake_torque_nm_raw':getattr(w,'max_brake_torque',None),
                      'max_handbrake_torque_nm_raw':getattr(w,'max_handbrake_torque',None)})
    return {'actor_id':int(actor.id),'actor_type':actor.type_id,
            'map':world.get_map().name,'carla_server_version':client.get_server_version(),
            'body_transform':{'location':vec(actor.get_transform().location),
                              'rotation':rotation(actor.get_transform().rotation)},
            'bounding_box':{'location_local':vec(bb.location),'extent':vec(bb.extent),
                            'rotation_local':rotation(bb.rotation)},
            'center_of_mass_raw':vec(p.center_of_mass), 'mass_kg_raw':float(p.mass),
            'wheels':wheel,
            'steering_curve_raw':[{'x_raw':float(z.x),'y_raw':float(z.y)}
                                  for z in getattr(p,'steering_curve',[])],
            'drag_coefficient_raw':float(p.drag_coefficient),
            'units_warning':'Wheel position coordinate frame and effective steering / braking must be independently checked. Raw tire friction is not effective mu.',
            'calibrated_vehicle_dynamics':False}


def spot(world, carla):
    """A candidate long, nearly straight driving lane, not a proven safe track."""
    m=world.get_map()
    for pose in m.get_spawn_points():
        wp=m.get_waypoint(pose.location,project_to_road=False,lane_type=carla.LaneType.Driving)
        if wp is None or wp.is_junction:continue
        cur=wp;straight=True
        for _ in range(22):
            nxt=cur.next(5.0)
            if len(nxt)!=1 or nxt[0].is_junction:
                straight=False;break
            diff=(nxt[0].transform.rotation.yaw-wp.transform.rotation.yaw+180)%360-180
            if abs(diff)>5:straight=False;break
            cur=nxt[0]
        if straight:return pose
    raise RuntimeError('REVIEW_NO_STRAIGHT_DRIVING_LANE_FOR_CONTROLLED_TRIAL')


def observe(actor,world,snapshot,cmd,trigger):
    x=actor.get_transform();v=actor.get_velocity();a=actor.get_acceleration();w=actor.get_angular_velocity()
    ctrl=actor.get_control()
    sp=math.sqrt(v.x*v.x+v.y*v.y+v.z*v.z)
    try:
        import carla
        actual_fl_steer=float(actor.get_wheel_steer_angle(carla.VehicleWheelLocation.FL))
        actual_fr_steer=float(actor.get_wheel_steer_angle(carla.VehicleWheelLocation.FR))
    except (AttributeError,RuntimeError,TypeError):
        actual_fl_steer=actual_fr_steer=None
    out={'frame':int(snapshot.frame),'sim_time_s':float(snapshot.timestamp.elapsed_seconds),
         'speed_mps':sp, 'accel_mps2':math.sqrt(a.x*a.x+a.y*a.y+a.z*a.z),
         'yaw_rate_radps_carla':math.radians(float(w.z)),
         'yaw_rate_degps_raw':float(w.z),
         'signed_longitudinal_accel_mps2':float(a.x*math.cos(math.radians(x.rotation.yaw))+a.y*math.sin(math.radians(x.rotation.yaw))),
         'signed_lateral_accel_mps2':float(-a.x*math.sin(math.radians(x.rotation.yaw))+a.y*math.cos(math.radians(x.rotation.yaw))),
         'accel_xyz_carla':vec(a),
         'velocity_xyz_carla':vec(v),'x_m_carla':float(x.location.x),'y_m_carla':float(x.location.y),
         'z_m_carla':float(x.location.z),'yaw_deg_carla':float(x.rotation.yaw),
         'command_throttle':float(cmd.throttle),'command_brake':float(cmd.brake),
         'command_steer':float(cmd.steer),'command_issued_before_tick':True,
         'actual_throttle':float(ctrl.throttle),'actual_brake':float(ctrl.brake),
         'actual_steer':float(ctrl.steer),
         'wheel_steer_deg_front_left_raw':actual_fl_steer,
         'wheel_steer_deg_front_right_raw':actual_fr_steer,
         'command_reference_sim_time_s':trigger,
         'coordinate_warning':'CARLA coordinates are left-handed; convert heading/y for RAMP-D before fitting'}
    if not all(finite(out[k]) for k in ('speed_mps','accel_mps2','yaw_rate_radps_carla','sim_time_s')):
        raise RuntimeError('NONFINITE_CARLA_STATE')
    return out


def drive_trial(world,vehicle,carla,*,speed,kind,repeat,step_s, max_accel_s=22.0):
    samples=[];cmd=carla.VehicleControl(throttle=0.70,brake=0.0,steer=0.0,hand_brake=False)
    target_frame=None;target_speed=None;command_time=None
    n_accel=int(max_accel_s/step_s)
    for _ in range(n_accel):
        old=world.get_snapshot();vehicle.apply_control(cmd)
        f=world.tick()  # one and only owner
        snap=world.get_snapshot()
        if snap.frame!=f or snap.frame!=old.frame+1:
            raise RuntimeError('REVIEW_FOREIGN_TICK_OWNER_OR_MISSING_CARLA_FRAME')
        sample=observe(vehicle,world,snap,cmd,float(old.timestamp.elapsed_seconds))
        samples.append(sample)
        if sample['speed_mps']>=speed-0.25:
            target_frame=f;target_speed=sample['speed_mps'];command_time=float(snap.timestamp.elapsed_seconds)
            break
    if target_frame is None:
        return {'status':'REVIEW_TARGET_NOT_REACHED','target_speed_mps':speed,
                'maneuver':kind,'repeat':repeat,'samples':samples,'trigger_frame':-1,'trigger_speed_mps':-1}
    # The first sample at target is the trigger reference; only POST-trigger
    # samples contain the new command and are eligible for delay estimation.
    for i in range(int(2.0/step_s)):
        turn=0.08 if i*step_s<0.8 and kind in ('steer','combined') else 0.0
        if kind=='brake': new=carla.VehicleControl(throttle=0,brake=0.70,steer=0)
        elif kind=='combined': new=carla.VehicleControl(throttle=0,brake=0.45,steer=turn)
        else:new=carla.VehicleControl(throttle=0.17,brake=0,steer=turn)
        old=world.get_snapshot();vehicle.apply_control(new);f=world.tick();snap=world.get_snapshot()
        if snap.frame!=f or snap.frame!=old.frame+1:
            raise RuntimeError('REVIEW_FOREIGN_TICK_OWNER_OR_MISSING_CARLA_FRAME')
        samples.append(observe(vehicle,world,snap,new,float(old.timestamp.elapsed_seconds)))
        # This script is not an autonomous driving controller. Stop if the test
        # leaves the drivable lane or approaches a junction unexpectedly.
        w=world.get_map().get_waypoint(vehicle.get_location(),project_to_road=False,lane_type=carla.LaneType.Driving)
        if w is None or w.is_junction:
            return {'status':'REVIEW_OFF_DRIVABLE_LANE','target_speed_mps':speed,
                    'maneuver':kind,'repeat':repeat,'samples':samples,
                    'trigger_frame':target_frame,'trigger_speed_mps':target_speed}
    return {'status':'CAPTURED','target_speed_mps':speed,'maneuver':kind,'repeat':repeat,
            'samples':samples,'trigger_frame':target_frame,'trigger_speed_mps':target_speed,
            'command_start_sim_time_s':command_time,'command_issue_semantics':'applied prior to next synchronous world.tick'}


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--mode',choices=('inventory','capture','trials'),default='inventory')
    p.add_argument('--host',default='127.0.0.1');p.add_argument('--port',type=int,default=2000)
    p.add_argument('--blueprint',default='vehicle.tesla.model3')
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--confirm-isolated-world',action='store_true')
    p.add_argument('--confirm-exclusive-tick',action='store_true')
    p.add_argument('--repeats',type=int,default=3)
    p.add_argument('--fixed-delta',type=float,default=0.05)
    a=p.parse_args()
    if a.output.exists():raise FileExistsError('REFUSE_OVERWRITE_CARLA_EVIDENCE')
    if a.mode!='inventory' and not a.confirm_isolated_world:
        raise RuntimeError('SPAWN_REQUIRES_EXPLICIT_ISOLATED_WORLD_ACK')
    if a.mode=='trials' and not a.confirm_exclusive_tick:
        raise RuntimeError('TRIALS_REQUIRE_EXCLUSIVE_TICK_ACK')
    if not 0<a.fixed_delta<=0.05 or type(a.repeats) is not int or not 1<=a.repeats<=10:
        raise ValueError('invalid fixed step or repeats')
    import carla
    client=carla.Client(a.host,a.port);client.set_timeout(12.0)
    world=client.get_world();original=world.get_settings();spawned=None
    # Any CARLA map is allowed; only the supported server version is required.
    if not client.get_server_version().startswith('0.9.16'):
        raise RuntimeError('EXPECTED_CARLA_0_9_16')
    result={'status':'REVIEW','map':world.get_map().name,
            'carla_server_version':client.get_server_version(), 'actor_type':a.blueprint,
            'calibrated_vehicle_dynamics':False,'world_exclusive_confirmed':False}
    a.output.parent.mkdir(parents=True,exist_ok=True)
    lock=Path('/tmp/rampd_carla_a59_1_port_'+str(a.port)+'.lock')
    try:
        with lock.open('a+') as fd:
            fcntl.flock(fd.fileno(),fcntl.LOCK_EX | fcntl.LOCK_NB)
            dynamic=[x for x in world.get_actors() if x.type_id.startswith(('vehicle.','walker.','sensor.'))]
            result['existing_dynamic_actors']=[{'id':int(x.id),'type':x.type_id} for x in dynamic]
            if a.mode=='inventory':
                result['status']='READ_ONLY_ACTOR_INVENTORY'
                result['actor_metadata']=[actor_metadata(x,world,client) for x in dynamic if x.type_id.startswith('vehicle.')]
            else:
                if dynamic: raise RuntimeError('REVIEW_EXISTING_DYNAMIC_ACTORS_REFUSE_MUTATION')
                if original.synchronous_mode: raise RuntimeError('REVIEW_WORLD_ALREADY_SYNCHRONOUS_MAY_HAVE_TICK_OWNER')
                blueprint=world.get_blueprint_library().find(a.blueprint)
                if blueprint is None or not a.blueprint.startswith('vehicle.'):
                    raise RuntimeError('MISSING_VEHICLE_BLUEPRINT')
                if blueprint.has_attribute('role_name'):blueprint.set_attribute('role_name','rampd_calibration')
                pose=(world.get_map().get_spawn_points()[0] if a.mode=='capture' else spot(world,carla))
                if a.mode=='capture':
                    spawned=world.try_spawn_actor(blueprint,pose)
                    if spawned is None:raise RuntimeError('REVIEW_ACTOR_SPAWN_FAILED')
                    result.update(status='ACTOR_METADATA_CAPTURED_UNCALIBRATED',
                                  actor_id=int(spawned.id),physics=actor_metadata(spawned,world,client))
                else:
                    # Own ticks only on an explicitly isolated, originally async
                    # CARLA world. A separate remote client cannot be detected.
                    settings=world.get_settings();settings.synchronous_mode=True
                    settings.fixed_delta_seconds=a.fixed_delta
                    settings.substepping=True;settings.max_substep_delta_time=0.01
                    settings.max_substeps=max(6,math.ceil(a.fixed_delta/0.01))
                    world.apply_settings(settings)
                    result.update(schema='rampd.carla.a59_1.raw_trials.v1',
                                  world_exclusive_confirmed=True,step_s=a.fixed_delta,
                                  trial_maneuvers=['brake','steer','combined'],trials=[])
                    for v in (5,10,15):
                        for kind in ('brake','steer','combined'):
                            for k in range(a.repeats):
                                spawned=world.try_spawn_actor(blueprint,pose)
                                if spawned is None:raise RuntimeError('REVIEW_ACTOR_SPAWN_FAILED')
                                spawned.set_autopilot(False)
                                if not result.get('physics'):
                                    result['actor_id']=int(spawned.id)
                                    result['physics']=actor_metadata(spawned,world,client)
                                try:
                                    trial=drive_trial(world,spawned,carla,speed=v,kind=kind,repeat=k,
                                                      step_s=a.fixed_delta)
                                    trial['actor_id']=int(spawned.id)
                                    result['trials'].append(trial)
                                finally:
                                    spawned.destroy();spawned=None
                                    # tick the actor destruction before the
                                    # next attempt so the spawn point is free.
                                    world.tick()
                    result['status']='RAW_CARLA_TRIALS_CAPTURED_NOT_CERTIFIED'
    except Exception as exc:
        result.update(status='REVIEW',error=f'{type(exc).__name__}: {exc}',traceback=traceback.format_exc())
    finally:
        if spawned is not None:
            try:spawned.destroy()
            except Exception:pass
        # Restore old global settings only if we changed them for trials.
        if a.mode=='trials' and result.get('world_exclusive_confirmed'):
            try:world.apply_settings(original)
            except Exception as exc:
                result['restoration_error']=str(exc);result['status']='REVIEW'
        a.output.write_text(json.dumps(result,indent=2,ensure_ascii=False,allow_nan=False,default=str)+'\n')
    print(result['status']);return 0 if result['status']!='REVIEW' else 4

if __name__=='__main__':raise SystemExit(main())
