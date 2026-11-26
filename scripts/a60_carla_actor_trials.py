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
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"python"))
from rampd_core.a62_carla_readiness import ground_window, projected_lane_footprint, wheel_road_height_proxy
from rampd_core.a63_carla_site_contract import audit_start_waypoint, wp_identity


def vec(v):return {k:float(getattr(v,k)) for k in ('x','y','z')}
def rotation(r):return {k+'_deg':float(getattr(r,k)) for k in ('pitch','yaw','roll')}
def finite(x):return math.isfinite(float(x))


def world_provenance(world):
    """Capture simulation settings/weather and map hash without changing state."""
    settings=world.get_settings()
    fields=('synchronous_mode','fixed_delta_seconds','substepping',
            'max_substep_delta_time','max_substeps','no_rendering_mode')
    out={'settings':{k:getattr(settings,k,None) for k in fields}}
    try:
        w=world.get_weather()
        out['weather_raw']={k:getattr(w,k,None) for k in
             ('cloudiness','precipitation','precipitation_deposits','wetness',
              'wind_intensity','fog_density','sun_altitude_angle')}
    except (AttributeError,RuntimeError,TypeError) as exc:
        out['weather_capture_error']=type(exc).__name__+': '+str(exc)
    try:
        out['opendrive_sha256']=hashlib.sha256(world.get_map().to_opendrive().encode('utf-8')).hexdigest()
    except (AttributeError,RuntimeError,TypeError) as exc:
        out['opendrive_sha256']=None
        out['opendrive_capture_error']=type(exc).__name__+': '+str(exc)
    return out


def await_async_actor_pose(world, actor, requested_pose, *, max_frames=5):
    """Read-only wait for a nonstale pose after asynchronous actor spawn.

    Never manually tick an existing asynchronous world. A successful response
    is an observed location near our requested spawn, not an assumed frame.
    """
    for _ in range(max_frames):
        snapshot=world.wait_for_tick(5.0)
        actual=actor.get_transform().location
        expected=requested_pose.location
        if math.hypot(actual.x-expected.x, actual.y-expected.y)<=5.0:
            return int(snapshot.frame)
    raise RuntimeError('REVIEW_STALE_ASYNC_ACTOR_TRANSFORM_AFTER_SPAWN')


def actor_metadata(actor, world, client):
    p=actor.get_physics_control(); bb=actor.bounding_box
    wheel=[]
    for w in p.wheels:
        wheel.append({'position_raw':vec(w.position),'radius_cm_raw':float(w.radius),
                      'tire_friction_raw':float(w.tire_friction),
                      'max_steer_angle_deg_raw':float(w.max_steer_angle),
                      'max_brake_torque_nm_raw':getattr(w,'max_brake_torque',None),
                      'max_handbrake_torque_nm_raw':getattr(w,'max_handbrake_torque',None),
                      'damping_rate_raw':getattr(w,'damping_rate',None),
                      'long_stiff_value_raw':getattr(w,'long_stiff_value',None),
                      'lat_stiff_value_raw':getattr(w,'lat_stiff_value',None),
                      'lat_stiff_max_load_raw':getattr(w,'lat_stiff_max_load',None)})
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
            'engine_gear_metadata_raw':{k:getattr(p,k,None) for k in ('max_rpm','moi','damping_rate_full_throttle','damping_rate_zero_throttle_clutch_engaged','damping_rate_zero_throttle_clutch_disengaged','use_gear_autobox','gear_switch_time','clutch_strength','final_ratio','use_sweep_wheel_collision')},
            'engine_torque_curve_raw': [{'x':float(v.x),'y':float(v.y)} for v in getattr(p,'torque_curve',[])],
            'forward_gears_raw': [{k:getattr(g,k,None) for k in ('ratio','down_ratio','up_ratio')} for g in getattr(p,'forward_gears',[])],
            'units_warning':'Wheel position coordinate frame and effective steering / braking must be independently checked. Raw tire friction is not effective mu.',
            'calibrated_vehicle_dynamics':False}


SITE_STEP_M = 5.0
SITE_REQUIRED_STEPS = 22
SITE_EXTENDED_STEPS = 60  # diagnostics: probe up to 300m, never relax the 110m gate
SITE_MAX_HEADING_DELTA_DEG = 5.0


def _site_trace(wp, carla, *, max_steps=SITE_REQUIRED_STEPS):
    """Audit the original 22 x 5 m / 5-degree eligibility test.

    Returns (verified distance, first rejection reason).  This intentionally
    uses the *same* next(5.0) and unique-successor conditions as the original
    `spot` implementation; it does not certify vehicle travel or road clearance.
    """
    if wp is None:
        return 0.0, 'NO_DRIVING_WAYPOINT'
    if wp.is_junction:
        return 0.0, 'START_IN_JUNCTION'
    if wp.lane_type != carla.LaneType.Driving:
        return 0.0, 'NOT_DRIVING_LANE'
    cur = wp
    initial_yaw = float(wp.transform.rotation.yaw)
    for i in range(max_steps):
        following = cur.next(SITE_STEP_M)
        if len(following) == 0:
            return i * SITE_STEP_M, 'NO_NEXT_WAYPOINT'
        if len(following) > 1:
            return i * SITE_STEP_M, 'MULTIPLE_NEXT_WAYPOINTS'
        successor = following[0]
        if successor.is_junction:
            return i * SITE_STEP_M, 'JUNCTION_IN_WINDOW'
        if successor.lane_type != carla.LaneType.Driving:
            return i * SITE_STEP_M, 'NON_DRIVING_IN_WINDOW'
        heading_delta = (float(successor.transform.rotation.yaw) - initial_yaw + 180) % 360 - 180
        if abs(heading_delta) > SITE_MAX_HEADING_DELTA_DEG:
            return i * SITE_STEP_M, 'HEADING_DELTA_OVER_5_DEG'
        cur = successor
    return SITE_STEP_M * max_steps, 'ELIGIBLE'


def _site_label(source, index, wp):
    t = wp.transform
    return {
        'source': source,
        'index': index,
        'road_id': int(wp.road_id),
        'section_id': int(wp.section_id),
        'lane_id': int(wp.lane_id),
        'x_m': float(t.location.x),
        'y_m': float(t.location.y),
        'z_m': float(t.location.z),
        'yaw_deg': float(t.rotation.yaw),
    }


def survey_sites(world, carla, *, spacing_m=2.0, exhaustive=True,
                 prefer_longest=False, top_k=10, require_start_identity=False):
    """Read-only map search; return an eligible actor pose and a site report.

    Exhaustive mode is intended for --mode site-audit. In normal trials the
    search stops at the first eligible pose, preserving spawn-point precedence.
    The report is descriptive, not a proof about the entire continuous map.
    """
    from collections import Counter
    m = world.get_map()
    spawns = m.get_spawn_points()
    causes = Counter()
    causes_by_source = {'spawn': Counter(), 'sampled_lane': Counter()}
    candidates = []
    selected_pose = None
    selected_metadata = None
    selected_extra_m = -1.0
    measured = 0
    number_eligible = 0
    usable_count = 0
    rejected_start = Counter()
    rejected_examples = []
    selected_start_audit = None
    counts_above = {str(n): 0 for n in (40, 60, 80, 100, 110)}

    def scan(wp, source, index, pose):
        nonlocal selected_pose, selected_metadata, selected_extra_m, measured, number_eligible, usable_count, selected_start_audit
        distance, reason = _site_trace(wp, carla)
        extra_distance = distance
        if reason == 'ELIGIBLE':
            extra_distance, _ = _site_trace(wp, carla, max_steps=SITE_EXTENDED_STEPS)
        measured += 1
        causes[reason] += 1
        causes_by_source[source][reason] += 1
        for threshold in (40, 60, 80, 100, 110):
            if distance >= threshold:
                counts_above[str(threshold)] += 1
        if reason == 'ELIGIBLE':
            number_eligible += 1
            start_audit=(audit_start_waypoint(m, carla, wp, pose)
                         if require_start_identity else None)
            if start_audit is not None and start_audit['status']!='DESCRIPTIVE_LANE_IDENTITY_REPRODUCED':
                rejected_start[start_audit['reason']]+=1
                if len(rejected_examples)<8:
                    rejected_examples.append({'candidate':_site_label(source,index,wp),
                                              'projection':start_audit})
            else:
                usable_count += 1
                if selected_pose is None or (prefer_longest and extra_distance > selected_extra_m):
                    selected_pose = pose
                    selected_metadata = _site_label(source, index, wp)
                    selected_extra_m = extra_distance
                    selected_start_audit = start_audit
        if wp is not None:
            data = _site_label(source, index, wp)
            data.update({'verified_step_distance_m': distance,
                         'extended_straight_probe_m': extra_distance,
                         'first_rejection_reason': reason})
            candidates.append(data)

    for index, pose in enumerate(spawns):
        wp = m.get_waypoint(pose.location, project_to_road=True,
                            lane_type=carla.LaneType.Driving)
        scan(wp, 'spawn', index, pose)
        if selected_pose is not None and not exhaustive:
            break

    waypoint_count = 0
    if selected_pose is None or exhaustive:
        waypoints = m.generate_waypoints(spacing_m)
        waypoint_count = len(waypoints)
        for index, wp in enumerate(waypoints):
            t = wp.transform
            pose = carla.Transform(
                carla.Location(x=t.location.x, y=t.location.y,
                               z=t.location.z + 0.5), t.rotation)
            scan(wp, 'sampled_lane', index, pose)
            if selected_pose is not None and not exhaustive:
                break

    ranked = sorted(candidates, key=lambda x: (
        -x['extended_straight_probe_m'],
        x['source'] != 'spawn', x['index']))
    report = {
        'map': m.name,
        'method': 'original_22_steps_of_5m_unique_successor_5deg_nonjunction',
        'required_straight_m': SITE_STEP_M * SITE_REQUIRED_STEPS,
        'max_heading_delta_deg': SITE_MAX_HEADING_DELTA_DEG,
        'extended_probe_limit_m': SITE_STEP_M * SITE_EXTENDED_STEPS,
        'sample_spacing_m': spacing_m,
        'spawn_points_total': len(spawns),
        'sampled_lane_waypoints_total': waypoint_count,
        'candidates_checked': measured,
        'eligible_candidates_checked': number_eligible,
        'projected_start_usable_candidates': usable_count if require_start_identity else None,
        'projected_start_rejections': dict(sorted(rejected_start.items())),
        'projected_start_rejection_examples': rejected_examples,
        'chosen_start_projection_audit': selected_start_audit,
        'required_projected_start_identity': require_start_identity,
        'rejection_counts': dict(sorted(causes.items())),
        'rejection_counts_by_source': {
            source: dict(sorted(counter.items()))
            for source, counter in causes_by_source.items()},
        'verified_step_distance_counts_ge_m': counts_above,
        'best_verified_step_distance_m': (ranked[0]['verified_step_distance_m']
                                          if ranked else 0.0),
        'best_extended_straight_probe_m': (ranked[0]['extended_straight_probe_m']
                                           if ranked else 0.0),
        'top_candidate_waypoints': ranked[:top_k],
        'chosen_waypoint': selected_metadata,
        'chosen_extended_straight_probe_m': selected_extra_m if selected_pose is not None else None,
        'prefer_longest': prefer_longest,
        'exhaustive': exhaustive,
        'interpretation_warning': (
            'Counts describe sampled waypoints under the original 5m test. '
            'They do not prove that the entire map lacks a site, that an actor '
            'will successfully spawn, or that 110m suffices for acceleration and maneuver.'),
    }
    return selected_pose, report


def spot(world, carla, *, spacing_m=2.0, prefer_longest=False, report=None,
         require_start_identity=False):
    """Find a site without relaxing the original 110m / 5-degree conditions."""
    pose, data = survey_sites(world, carla, spacing_m=spacing_m,
                              exhaustive=prefer_longest, prefer_longest=prefer_longest,
                              require_start_identity=require_start_identity)
    if report is not None:
        report.update(data)
    if pose is not None:
        return pose
    reasons = ','.join(f'{k}:{v}' for k, v in data['rejection_counts'].items())
    raise RuntimeError(
        'REVIEW_NO_STRAIGHT_DRIVING_LANE_FOR_CONTROLLED_TRIAL'
        f' map={data["map"]} spawn_points={data["spawn_points_total"]}'
        f' sampled_lane_waypoints={data["sampled_lane_waypoints_total"]}'
        f' best_verified_step_distance_m={data["best_verified_step_distance_m"]}'
        f' required_straight_m={data["required_straight_m"]}'
        f' max_heading_delta_deg={data["max_heading_delta_deg"]}'
        f' failures={reasons}'
        f' projected_start_rejections={data.get("projected_start_rejections", {})}')


def capture_solver_telemetry(actor):
    """Optional 0.9.16 RPC; raw values only. Explicitly preserve unavailable fields."""
    try:
        t=actor.get_telemetry_data()
        def fields(obj,names):
            out={}
            for name in names:
                v=getattr(obj,name,None)
                out[name]=float(v) if isinstance(v,(int,float)) and math.isfinite(v) else None
            return out
        wheels=getattr(t,'wheels',None)
        return {'status':'RAW_TELEMETRY' if wheels is not None else 'REVIEW_NO_WHEEL_TELEMETRY',
                'vehicle':fields(t,('speed','steer','throttle','brake','engine_rpm','gear','drag')),
                'wheels':[fields(w,('omega','torque','long_slip','lat_slip','tire_load','long_force','lat_force','tire_friction')) for w in wheels] if wheels is not None else [],
                'units_and_frame_not_independently_verified':True}
    except (AttributeError,RuntimeError,TypeError,ValueError) as e:
        return {'status':'UNAVAILABLE','reason':type(e).__name__+': '+str(e)}


def observe(actor,world,snapshot,cmd,trigger):
    x=actor.get_transform();v=actor.get_velocity();a=actor.get_acceleration();w=actor.get_angular_velocity()
    ctrl=actor.get_control()
    sp=math.sqrt(v.x*v.x+v.y*v.y+v.z*v.z)
    # CARLA 0.9.16 enum members are FL_Wheel/FR_Wheel, not FL/FR.
    # Preserve sensor failure instead of silently treating missing angles as 0.
    actual_fl_steer=actual_fr_steer=None
    wheel_steer_query_error=None
    try:
        import carla
        wheel_enum=carla.VehicleWheelLocation
        actual_fl_steer=float(actor.get_wheel_steer_angle(wheel_enum.FL_Wheel))
        actual_fr_steer=float(actor.get_wheel_steer_angle(wheel_enum.FR_Wheel))
        if not finite(actual_fl_steer) or not finite(actual_fr_steer):
            raise ValueError('NONFINITE_WHEEL_STEER_ANGLE')
    except (AttributeError,RuntimeError,TypeError,ValueError) as exc:
        wheel_steer_query_error=type(exc).__name__+': '+str(exc)
        actual_fl_steer=actual_fr_steer=None
    out={'frame':int(snapshot.frame),'sim_time_s':float(snapshot.timestamp.elapsed_seconds),
         'speed_mps':sp, 'planar_speed_mps':math.hypot(v.x,v.y),
         'vertical_speed_mps':float(v.z), 'accel_mps2':math.sqrt(a.x*a.x+a.y*a.y+a.z*a.z),
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
         'actual_gear':getattr(ctrl,'gear',None),'actual_hand_brake':getattr(ctrl,'hand_brake',None),
         'actual_reverse':getattr(ctrl,'reverse',None),'actual_manual_gear_shift':getattr(ctrl,'manual_gear_shift',None),
         'command_gear':getattr(cmd,'gear',None),'command_hand_brake':getattr(cmd,'hand_brake',None),
         'command_reverse':getattr(cmd,'reverse',None),'command_manual_gear_shift':getattr(cmd,'manual_gear_shift',None),
         'pitch_deg_carla':getattr(x.rotation,'pitch',None),'roll_deg_carla':getattr(x.rotation,'roll',None),
         'wheel_steer_deg_front_left_raw':actual_fl_steer,
         'wheel_steer_deg_front_right_raw':actual_fr_steer,
         'wheel_steer_query_error':wheel_steer_query_error,
         'command_reference_sim_time_s':trigger,
         'coordinate_warning':'CARLA coordinates are left-handed; convert heading/y for RAMP-D before fitting'}
    import os
    if os.environ.get('RAMPD_CARLA_TELEMETRY')=='1':out['solver_telemetry_raw']=capture_solver_telemetry(actor)
    if not all(finite(out[k]) for k in ('speed_mps','accel_mps2','yaw_rate_radps_carla','sim_time_s')):
        raise RuntimeError('NONFINITE_CARLA_STATE')
    return out



def lane_audit(world, actor, carla, *, expected_lane=None, margin=0.10):
    """Explicit 2-D projected lane check with the full vehicle rectangle.

    Nearest waypoint alone is never accepted as road containment. Road IDs and
    lateral width must also agree. Never a continuous/swept road safety proof.
    """
    m=world.get_map(); t=actor.get_transform(); loc=t.location
    wp=m.get_waypoint(loc,project_to_road=True,lane_type=carla.LaneType.Driving)
    if wp is None or wp.is_junction:
        return {'status':'REVIEW','reason':'NO_NONJUNCTION_DRIVING_WAYPOINT'}
    bb=actor.bounding_box
    got=(int(wp.road_id),int(wp.section_id),int(wp.lane_id))
    return projected_lane_footprint(loc.x,loc.y,t.rotation.yaw,
        bb.location.x,bb.location.y,bb.extent.x,bb.extent.y,
        wp.transform.location.x,wp.transform.location.y,
        wp.transform.rotation.yaw,wp.lane_width,lane_margin=margin,
        expected_lane=expected_lane,observed_lane=got)


def road_height_proxy(world, actor, carla):
    """Check CARLA 0.9.16 wheel heights against map, fail on unknown units."""
    t=actor.get_transform();wheels=actor.get_physics_control().wheels
    try:
        heights=[]
        m=world.get_map()
        for w in wheels:
            # The wheel-coordinate scale must match the body position before
            # any road elevation comparison is treated as useful evidence.
            loc=carla.Location(x=float(w.position.x)/100,
                               y=float(w.position.y)/100,
                               z=float(w.position.z)/100)
            wp=m.get_waypoint(loc,project_to_road=True,
                              lane_type=carla.LaneType.Driving)
            if wp is None:
                return {'status':'REVIEW','reason':'NO_ROAD_SURFACE_UNDER_WHEEL'}
            heights.append(float(wp.transform.location.z))
        return wheel_road_height_proxy(wheels,(t.location.x,t.location.y,t.location.z),heights)
    except (AttributeError,RuntimeError,TypeError,ValueError,OverflowError) as exc:
        return {'status':'REVIEW','reason':'UNAVAILABLE_WHEEL_ROAD_HEIGHT_PROXY',
                'error':type(exc).__name__+': '+str(exc)}


def settle_vehicle(world,actor,carla,*,step_s,max_settle_s=4.0,
                   min_consecutive=5,expected_lane=None):
    """Quiescent physical settling before acceleration or metadata fitting.

    Reject floating/falling, horizontally moving and off-center vehicles;
    preserve diagnostic frames. No contact sensor is inferred from z stability.
    """
    samples=[]
    cmd=carla.VehicleControl(throttle=0,brake=0,steer=0,hand_brake=True)
    for _ in range(int(max_settle_s/step_s)):
        before=world.get_snapshot().frame
        actor.apply_control(cmd)
        f=world.tick();snap=world.get_snapshot()
        if f!=before+1 or snap.frame!=f:
            raise RuntimeError('REVIEW_FOREIGN_TICK_DURING_SETTLING')
        t=actor.get_transform().location;v=actor.get_velocity()
        samples.append((int(f),float(snap.timestamp.elapsed_seconds),
                        float(t.x),float(t.y),float(t.z),
                        float(v.x),float(v.y),float(v.z)))
        if len(samples)>=min_consecutive:
            stable,why=ground_window(samples,minimum=min_consecutive)
            if stable:
                lane=lane_audit(world,actor,carla,expected_lane=expected_lane)
                if lane['status']!='DESCRIPTIVE_RECTANGLE_WITHIN_LANE':
                    return {'status':'REVIEW_SETTLED_BUT_NOT_IN_LANE',
                            'reason':lane['reason'],'lane_audit':lane,
                            'frames':len(samples),'samples':samples[-min_consecutive:]}
                ground=road_height_proxy(world,actor,carla)
                if ground['status']!='DESCRIPTIVE_WHEEL_HEIGHT_NEAR_ROAD':
                    # Height stationary alone can also mean a physics-disabled,
                    # suspended or badly placed actor; this is not sufficient.
                    return {'status':'REVIEW_GROUND_HEIGHT_PROXY_UNVERIFIED',
                            'reason':ground['reason'],'ground_height_proxy':ground,
                            'frames':len(samples),'samples':samples[-min_consecutive:]}
                # Remove the handbrake before the first throttle command.
                actor.apply_control(carla.VehicleControl(throttle=0,brake=0,steer=0,hand_brake=False))
                return {'status':'DESCRIPTIVE_STATIONARY_HEIGHT_STABLE',
                        'reason':why,'frames':len(samples),
                        'lane_audit':lane,'ground_height_proxy':ground,
                        'samples':samples[-min_consecutive:]}
    stable,why=ground_window(samples,minimum=min_consecutive)
    return {'status':'REVIEW_NO_STABLE_GROUNDING_EVIDENCE','reason':why,
            'frames':len(samples),'samples':samples[-min_consecutive:]}


def drive_trial(world,vehicle,carla,*,speed,kind,repeat,step_s,
                steer_fraction=0.08,steer_pulse_s=0.8, combined_brake_fraction=0.45,
                brake_only_fraction=0.70, max_accel_s=22.0,
                expected_lane=None,on_settled=None):
    settle=settle_vehicle(world,vehicle,carla,step_s=step_s,
                          expected_lane=expected_lane)
    if settle['status']!='DESCRIPTIVE_STATIONARY_HEIGHT_STABLE':
        return {'status':'REVIEW_PRETRIAL_GROUNDING_FAILED',
                'target_speed_mps':speed,'maneuver':kind,'repeat':repeat,
                'settling':settle,'samples':[],'trigger_frame':-1,
                'trigger_speed_mps':-1}
    if on_settled is not None:
        on_settled(vehicle)
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
        sample['lane_audit']=lane_audit(world,vehicle,carla,
                                      expected_lane=expected_lane)
        samples.append(sample)
        # A centerline-only 110m site check is not a proof that the vehicle
        # stayed on the road during the acceleration phase.
        if sample['lane_audit']['status']!='DESCRIPTIVE_RECTANGLE_WITHIN_LANE':
            return {'status':'REVIEW_APPROACH_OFF_DRIVABLE_LANE',
                    'target_speed_mps':speed,'maneuver':kind,'repeat':repeat,
                    'samples':samples,'settling':settle,'trigger_frame':-1,'trigger_speed_mps':-1}
        if sample['planar_speed_mps']>=speed-0.25:
            target_frame=f;target_speed=sample['planar_speed_mps'];command_time=float(snap.timestamp.elapsed_seconds)
            break
    if target_frame is None:
        return {'status':'REVIEW_TARGET_NOT_REACHED','target_speed_mps':speed,
                'maneuver':kind,'repeat':repeat,'samples':samples,'settling':settle,'trigger_frame':-1,'trigger_speed_mps':-1}
    # The first sample at target is the trigger reference; only POST-trigger
    # samples contain the new command and are eligible for delay estimation.
    for i in range(int(2.0/step_s)):
        turn=steer_fraction if i*step_s<steer_pulse_s and kind in ('steer','combined') else 0.0
        if kind=='brake': new=carla.VehicleControl(throttle=0,brake=brake_only_fraction,steer=0)
        elif kind=='combined': new=carla.VehicleControl(throttle=0,brake=combined_brake_fraction,steer=turn)
        else:new=carla.VehicleControl(throttle=0.17,brake=0,steer=turn)
        old=world.get_snapshot();vehicle.apply_control(new);f=world.tick();snap=world.get_snapshot()
        if snap.frame!=f or snap.frame!=old.frame+1:
            raise RuntimeError('REVIEW_FOREIGN_TICK_OWNER_OR_MISSING_CARLA_FRAME')
        post=observe(vehicle,world,snap,new,float(old.timestamp.elapsed_seconds))
        post['lane_audit']=lane_audit(world,vehicle,carla,expected_lane=expected_lane)
        samples.append(post)
        # This script is not an autonomous driving controller. Stop if the test
        # leaves the drivable lane or approaches a junction unexpectedly.
        if post['lane_audit']['status']!='DESCRIPTIVE_RECTANGLE_WITHIN_LANE':
            return {'status':'REVIEW_OFF_DRIVABLE_LANE','target_speed_mps':speed,
                    'maneuver':kind,'repeat':repeat,'samples':samples,'settling':settle,
                    'trigger_frame':target_frame,'trigger_speed_mps':target_speed}
    return {'status':'CAPTURED','target_speed_mps':speed,'maneuver':kind,'repeat':repeat,
            'samples':samples,'settling':settle,'trigger_frame':target_frame,'trigger_speed_mps':target_speed,
            'command_start_sim_time_s':command_time,'command_issue_semantics':'applied prior to next synchronous world.tick',
            'steer_fraction':steer_fraction,'steer_pulse_s':steer_pulse_s,
            'combined_brake_fraction':combined_brake_fraction,
            'brake_only_fraction':brake_only_fraction}



def controlled_trial_matrix(mode, repeats, smoke_speed, smoke_maneuver):
    """Pure deterministic experiment roster; no CARLA access or actor mutation."""
    if mode=='smoke':
        if smoke_speed not in (5,10,15) or smoke_maneuver not in ('brake','steer','combined'):
            raise ValueError('invalid single trial control profile')
        return ((smoke_speed, smoke_maneuver, 0),)
    if mode=='trials' and type(repeats) is int and 1<=repeats<=10:
        return tuple((v,k,r) for v in (5,10,15)
                     for k in ('brake','steer','combined') for r in range(repeats))
    raise ValueError('explicit trials/smoke mode and valid repeats required')


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--mode',choices=('inventory','site-audit','capture','readiness','smoke','trials'),default='inventory')
    p.add_argument('--host',default='127.0.0.1');p.add_argument('--port',type=int,default=2000)
    p.add_argument('--blueprint',default='vehicle.tesla.model3')
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--confirm-isolated-world',action='store_true')
    p.add_argument('--confirm-exclusive-tick',action='store_true')
    p.add_argument('--repeats',type=int,default=3)
    p.add_argument('--smoke-speed',type=int,choices=(5,10,15),default=5,
                   help='Only for --mode smoke; one 5/10/15 m/s controlled attempt')
    p.add_argument('--smoke-maneuver',choices=('brake','steer','combined'),default='brake',
                   help='Only for --mode smoke; does not imply calibration')
    p.add_argument('--fixed-delta',type=float,default=0.05)
    p.add_argument('--max-substep-delta',type=float,default=0.01,help='Physics integration setting; change independently from fixed-delta')
    p.add_argument('--max-substeps',type=int,default=None,help='Explicit physics substep budget; defaults to at least six')
    p.add_argument('--steer-fraction',type=float,default=0.08,
                   help='CARLA normalized steer input, NOT a radian angle (default original 0.08)')
    p.add_argument('--combined-brake-fraction',type=float,default=0.45,
                   help='Combined-only normalized brake fraction; original protocol 0.45')
    p.add_argument('--brake-only-fraction',type=float,default=0.70,
                   help='Brake-only control fraction, separately declared; original 0.70')
    p.add_argument('--steer-pulse-s',type=float,default=0.8,
                   help='Positive steer pulse duration; changes trial protocol, default original 0.8s')
    p.add_argument('--site-prefer-longest', action='store_true',
                   help='Among 110m-eligible sites select longest 5-degree straight section (up to 300m)')
    p.add_argument('--site-spacing',type=float,default=2.0,
                   help='Waypoint sampling interval in meters for read-only site search (default: 2)')
    a=p.parse_args()
    if a.output.exists():raise FileExistsError('REFUSE_OVERWRITE_CARLA_EVIDENCE')
    if a.mode in ('capture','readiness','smoke','trials') and not a.confirm_isolated_world:
        raise RuntimeError('SPAWN_REQUIRES_EXPLICIT_ISOLATED_WORLD_ACK')
    if a.mode in ('readiness','smoke','trials') and not a.confirm_exclusive_tick:
        raise RuntimeError('TRIALS_REQUIRE_EXCLUSIVE_TICK_ACK')
    if not math.isfinite(a.site_spacing) or not 0.5<=a.site_spacing<=10.0:
        raise ValueError('site-spacing must be between 0.5 and 10 m')
    if not 0<a.fixed_delta<=0.05 or type(a.repeats) is not int or not 1<=a.repeats<=10:
        raise ValueError('invalid fixed step or repeats')
    if not math.isfinite(a.max_substep_delta) or not 0.001<=a.max_substep_delta<=0.02:
        raise ValueError('invalid max substep delta')
    substeps=a.max_substeps if a.max_substeps is not None else max(6,math.ceil(a.fixed_delta/a.max_substep_delta))
    if not 1<=substeps<=100 or a.fixed_delta>substeps*a.max_substep_delta+1e-12:
        raise ValueError('fixed delta exceeds substep budget')
    if (not math.isfinite(a.steer_fraction) or not 0.025<=a.steer_fraction<=0.5 or
        not math.isfinite(a.steer_pulse_s) or not a.fixed_delta<=a.steer_pulse_s<=1.0 or
        not math.isfinite(a.combined_brake_fraction) or not 0.05<=a.combined_brake_fraction<=0.8 or
        not math.isfinite(a.brake_only_fraction) or not 0.05<=a.brake_only_fraction<=0.8):
        raise ValueError('invalid declared steering excitation profile')
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
            elif a.mode=='site-audit':
                _, result['site_audit'] = survey_sites(
                    world, carla, spacing_m=a.site_spacing, exhaustive=True, prefer_longest=True,
                    require_start_identity=True)
                result['status']='READ_ONLY_SITE_AUDIT'
            else:
                if dynamic: raise RuntimeError('REVIEW_EXISTING_DYNAMIC_ACTORS_REFUSE_MUTATION')
                if original.synchronous_mode: raise RuntimeError('REVIEW_WORLD_ALREADY_SYNCHRONOUS_MAY_HAVE_TICK_OWNER')
                blueprint=world.get_blueprint_library().find(a.blueprint)
                if blueprint is None or not a.blueprint.startswith('vehicle.'):
                    raise RuntimeError('MISSING_VEHICLE_BLUEPRINT')
                if blueprint.has_attribute('role_name'):blueprint.set_attribute('role_name','rampd_calibration')
                pose=(world.get_map().get_spawn_points()[0] if a.mode=='capture' else spot(
                    world,carla,spacing_m=a.site_spacing,prefer_longest=a.site_prefer_longest,
                    report=result.setdefault('site_audit',{}),
                    require_start_identity=True))
                if a.mode=='capture':
                    spawned=world.try_spawn_actor(blueprint,pose)
                    if spawned is None:raise RuntimeError('REVIEW_ACTOR_SPAWN_FAILED')
                    # In async mode we must wait for CARLA to publish the new
                    # actor pose before comparing body frame with wheel world positions.
                    frame=await_async_actor_pose(world,spawned,pose)
                    result.update(status='ACTOR_METADATA_CAPTURED_UNCALIBRATED',
                                  actor_id=int(spawned.id),physics=actor_metadata(spawned,world,client))
                    result['physics']['capture_frame']=frame
                    result['physics']['spawn_requested_transform']={
                        'location':vec(pose.location), 'rotation':rotation(pose.rotation)}
                else:
                    # Own ticks only on an explicitly isolated, originally async
                    # CARLA world. A separate remote client cannot be detected.
                    settings=world.get_settings();settings.synchronous_mode=True
                    settings.fixed_delta_seconds=a.fixed_delta
                    settings.substepping=True;settings.max_substep_delta_time=a.max_substep_delta
                    settings.max_substeps=substeps
                    world.apply_settings(settings)
                    result['world_provenance']=world_provenance(world)
                    result.update(schema='rampd.carla.a59_1.raw_trials.v1',
                                  capture_protocol_version='a62_grounding_lane_v1',
                                  start_site_protocol_version='a63_projected_lane_identity_v1',
                                  world_exclusive_confirmed=True,step_s=a.fixed_delta,
                                  trial_maneuvers=['brake','steer','combined'],trials=[],
                                  steer_fraction=a.steer_fraction,steer_pulse_s=a.steer_pulse_s,
                                  combined_brake_fraction=a.combined_brake_fraction,
                                  brake_only_fraction=a.brake_only_fraction)
                    # The site selection has already checked the same map
                    # projection used here. Recheck after changing world
                    # settings; if the map query changed, stop with evidence.
                    selected_wp=world.get_map().get_waypoint(
                        pose.location,project_to_road=True,lane_type=carla.LaneType.Driving)
                    site_id=result.get('site_audit',{}).get('chosen_waypoint') or {}
                    expected_lane=(site_id.get('road_id'),site_id.get('section_id'),site_id.get('lane_id'))
                    reread_id=wp_identity(selected_wp)
                    result['start_lane_recheck']={
                        'expected_identity':expected_lane,'projected_identity':reread_id,
                        'projected_is_junction':(bool(selected_wp.is_junction) if selected_wp is not None else None),
                        'accepted':bool(selected_wp is not None and not selected_wp.is_junction and reread_id==expected_lane),
                        'certified':False}
                    if not result['start_lane_recheck']['accepted']:
                        raise RuntimeError('REVIEW_START_LANE_PROJECTION_CHANGED_OR_AMBIGUOUS')
                    result['expected_start_lane']={'road_id':expected_lane[0],
                        'section_id':expected_lane[1],'lane_id':expected_lane[2]}
                    if a.mode=='readiness':
                        spawned=world.try_spawn_actor(blueprint,pose)
                        if spawned is None:raise RuntimeError('REVIEW_ACTOR_SPAWN_FAILED')
                        spawned.set_autopilot(False)
                        settle=settle_vehicle(world,spawned,carla,step_s=a.fixed_delta,
                                             expected_lane=expected_lane)
                        result['trials'].append({'status':
                            'DESCRIPTIVE_PRETRIAL_READY_NOT_CALIBRATED' if
                             settle['status']=='DESCRIPTIVE_STATIONARY_HEIGHT_STABLE' else
                            'REVIEW_PRETRIAL_GROUNDING_FAILED',
                            'settling':settle,'actor_id':int(spawned.id)})
                        result['physics']=dict(actor_metadata(spawned,world,client),
                            capture_frame=int(world.get_snapshot().frame),
                            capture_state='AFTER_SETTLING_PRETRIAL_READINESS')
                        result['status']=('DESCRIPTIVE_PRETRIAL_READY_NOT_CALIBRATED' if
                            settle['status']=='DESCRIPTIVE_STATIONARY_HEIGHT_STABLE' else 'REVIEW')
                        spawned.destroy();spawned=None
                    else:
                        # One small evidence-producing controlled attempt before
                        # the nine-combination / 27-trial campaign. Never rewrite
                        # the full campaign or silently relax the lane/physics gates.
                        matrix = controlled_trial_matrix(
                            a.mode,a.repeats,a.smoke_speed,a.smoke_maneuver)
                        for v,kind,k in matrix:
                            spawned=world.try_spawn_actor(blueprint,pose)
                            if spawned is None:raise RuntimeError('REVIEW_ACTOR_SPAWN_FAILED')
                            spawned.set_autopilot(False)
                            try:
                                trial=drive_trial(world,spawned,carla,speed=v,kind=kind,repeat=k,
                                                          step_s=a.fixed_delta,
                                                          steer_fraction=a.steer_fraction,
                                                          steer_pulse_s=a.steer_pulse_s,
                                                          combined_brake_fraction=a.combined_brake_fraction,
                                                          brake_only_fraction=a.brake_only_fraction,
                                                          expected_lane=expected_lane,
                                                          on_settled=(lambda v: result.update(
                                                              actor_id=int(v.id),
                                                              physics=dict(actor_metadata(v,world,client),
                                                              capture_frame=int(world.get_snapshot().frame),
                                                              capture_state='AFTER_STABLE_HEIGHT_BEFORE_ACTUATION')))
                                                              if not result.get('physics') else None)
                                trial['actor_id']=int(spawned.id)
                                result['trials'].append(trial)
                            finally:
                                spawned.destroy();spawned=None
                                # Tick the destruction before the next spawn.
                                world.tick()
                    counts={}
                    for t in result['trials']:
                        st=t.get('status','MISSING_STATUS')
                        counts[st]=counts.get(st,0)+1
                    result['trial_status_counts']=counts
                    result['trial_captured_count']=counts.get('CAPTURED',0)
                    result['trial_attempt_count']=len(result['trials'])
                    if a.mode in ('trials','smoke'):
                        required=(1 if a.mode=='smoke' else 9*a.repeats)
                        result['experiment_scope']=('SINGLE_CONTROL_SMOKE' if a.mode=='smoke' else 'FULL_CONTROL_MATRIX')
                        result['status']=('RAW_CARLA_TRIALS_CAPTURED_NOT_CERTIFIED'
                            if result['trial_captured_count']==required
                            else 'RAW_PARTIAL_CARLA_TRIALS_CAPTURED_NOT_CERTIFIED')
    except Exception as exc:
        result.update(status='REVIEW',error=f'{type(exc).__name__}: {exc}',traceback=traceback.format_exc())
    finally:
        if spawned is not None:
            try:spawned.destroy()
            except Exception:pass
        # Restore old global settings only if we changed them for trials.
        if a.mode in ('readiness','smoke','trials') and result.get('world_exclusive_confirmed'):
            try:world.apply_settings(original)
            except Exception as exc:
                result['restoration_error']=str(exc);result['status']='REVIEW'
        a.output.write_text(json.dumps(result,indent=2,ensure_ascii=False,allow_nan=False,default=str)+'\n')
    print(result['status'])
    return 0 if result['status'] not in ('REVIEW',
                'RAW_PARTIAL_CARLA_TRIALS_CAPTURED_NOT_CERTIFIED') else 4

if __name__=='__main__':raise SystemExit(main())
