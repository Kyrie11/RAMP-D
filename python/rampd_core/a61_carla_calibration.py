"""A61/0: independent CARLA actor geometry and repeated-response *evidence* review.

All output is descriptive. In particular, it is NOT an identification of bounded
continuous disturbances, an actuator worst-case delay or any real-car guarantee.
Raw wheel positions in the uploaded CARLA 0.9.16 session appear to use world
centimetres. The scale hypothesis is checked against axle separation and actor
(or requested spawn) world pose, never silently assumed for another actor.
"""
from __future__ import annotations
from collections import Counter, defaultdict
from math import atan2, cos, hypot, isfinite, pi, radians, sin
from statistics import mean, median


def _number(value):
    return type(value) in (float,int) and isfinite(value)


def _xy(v):
    if not isinstance(v,dict) or not all(_number(v.get(k)) for k in ('x','y')):
        raise ValueError('NONFINITE_VECTOR')
    return (float(v['x']),float(v['y']))


def _meanxy(points):
    return tuple(mean(p[i] for p in points) for i in (0,1))


def _body_poses(document,physics):
    candidates=[]
    original=physics.get('body_transform') or {}
    if isinstance(original,dict):
        loc=original.get('location');rot=original.get('rotation') or {}
        if isinstance(loc,dict) and _number(rot.get('yaw_deg')):
            try:candidates.append(('observed_actor_transform',_xy(loc),float(rot['yaw_deg'])))
            except ValueError:pass
    site=document.get('site_audit') or {}
    chosen=site.get('chosen_waypoint') or {}
    if all(_number(chosen.get(k)) for k in ('x_m','y_m','yaw_deg')):
        candidates.append(('requested_spawn_waypoint',
                           (float(chosen['x_m']),float(chosen['y_m'])),float(chosen['yaw_deg'])))
    return candidates


def reconstruct_actor_geometry(document):
    """Validate wheel-position units and infer rear-axle geometry where grounded.

    Wheel order is determined from steer capability (two steering vs two rear),
    not the raw order in metadata. Returns REVIEW on ambiguous calibration.
    """
    p=document.get('physics',document) if isinstance(document,dict) else {}
    result={'status':'REVIEW','source':'RAW_CARLA_ACTOR_GEOMETRY',
            'certified_physical_geometry':False,'reasons':[]}
    errors=result['reasons']
    if not isinstance(p,dict) or p.get('actor_type')!='vehicle.tesla.model3':
        errors.append('UNSUPPORTED_OR_MISSING_ACTOR_TYPE');return result
    wheels=p.get('wheels')
    if not isinstance(wheels,list) or len(wheels)!=4:
        errors.append('INCOMPLETE_FOUR_WHEEL_METADATA');return result
    try:
        front=[_xy(w['position_raw']) for w in wheels if _number(w.get('max_steer_angle_deg_raw')) and float(w['max_steer_angle_deg_raw'])>1]
        back=[_xy(w['position_raw']) for w in wheels if _number(w.get('max_steer_angle_deg_raw')) and abs(float(w['max_steer_angle_deg_raw']))<=1]
        if len(front)!=2 or len(back)!=2:raise ValueError('STEER_AXLE_CLASSIFICATION_AMBIGUOUS')
    except (KeyError,ValueError,TypeError) as exc:
        errors.append('INVALID_WHEEL_POSITION_OR_STEER:'+str(exc));return result
    fc,bc=_meanxy(front),_meanxy(back)
    raw_sep=hypot(fc[0]-bc[0],fc[1]-bc[1]);raw_ft=hypot(front[0][0]-front[1][0],front[0][1]-front[1][1])
    raw_rt=hypot(back[0][0]-back[1][0],back[0][1]-back[1][1])
    options=[]
    for scale,label in ((1.0,'world_m'),(.01,'world_cm')):
        length=raw_sep*scale
        if 1.5<=length<=5.0 and .8<=raw_ft*scale<=3 and .8<=raw_rt*scale<=3:
            options.append((scale,label,length))
    if len(options)!=1:
        errors.append('WHEEL_POSITION_UNIT_HYPOTHESIS_UNRESOLVED');return result
    scale,label,length=options[0]
    result.update(wheel_position_unit_hypothesis=label,wheel_position_scale_to_m=scale,
                  wheelbase_from_axle_centroids_m=length,front_track_m=raw_ft*scale,
                  rear_track_m=raw_rt*scale)
    fc=tuple(x*scale for x in fc);bc=tuple(x*scale for x in bc)
    near=[]
    for name,pose,yaw in _body_poses(document,p):
        if hypot((fc[0]+bc[0])/2-pose[0],(fc[1]+bc[1])/2-pose[1])<=4:
            near.append((name,pose,yaw))
    if not near:
        errors.append('NO_VALID_ACTOR_OR_REQUESTED_SPAWN_POSE_FOR_AXLE_OFFSET')
        return result
    # Prefer a synchronized actor transform, but reject a pre-spawn (0,0,0)
    # pose uncorrelated with the actual wheel positions.
    name,pose,yaw=near[0]
    angle=radians(yaw);direction=(cos(angle),sin(angle))
    def local(pt):
        d=(pt[0]-pose[0],pt[1]-pose[1])
        return (d[0]*direction[0]+d[1]*direction[1],
               -d[0]*direction[1]+d[1]*direction[0])
    front_local=local(fc);back_local=local(bc)
    if front_local[0]-back_local[0] < 1.5 or max(abs(front_local[1]),abs(back_local[1]))>.4:
        errors.append('AXLE_ORIENTATION_OR_POSE_MISMATCH');return result
    box=p.get('bounding_box') or {}
    try:
        center=_xy(box['location_local']);extent=_xy(box['extent']);byaw=float(box['rotation_local']['yaw_deg'])
        if any(v<=0 for v in extent) or abs(byaw)>1e-3:raise ValueError('ROTATED_OR_ZERO_BBOX')
    except (TypeError,KeyError,ValueError) as exc:
        errors.append('UNRESOLVED_BOUNDING_BOX:'+str(exc));return result
    # An axis-aligned actor-local rectangle in CARLA's body frame.
    front_overhang=center[0]+extent[0]-front_local[0]
    rear_overhang=back_local[0]-(center[0]-extent[0])
    if min(front_overhang,rear_overhang)<0 or max(front_overhang,rear_overhang)>2.0:
        errors.append('NEGATIVE_OR_IMPLAUSIBLE_OVERHANG');return result
    result.update(status='DESCRIPTIVE_CARLA_ACTOR_GEOMETRY_RECONSTRUCTED',
                  pose_source=name,actor_yaw_deg=yaw,
                  bbox_length_m=extent[0]*2,bbox_width_m=extent[1]*2,
                  rear_axle_actor_local_x_m=back_local[0],
                  rear_axle_actor_local_y_m=back_local[1],
                  front_axle_actor_local_x_m=front_local[0],
                  front_axle_actor_local_y_m=front_local[1],
                  rear_axle_to_bbox_center_x_m=center[0]-back_local[0],
                  rear_axle_to_bbox_center_y_m=center[1]-back_local[1],
                  front_overhang_m=front_overhang,rear_overhang_m=rear_overhang,
                  nominal_only=True)
    return result


def _post_samples(trial):
    trigger=trial.get('trigger_frame')
    return [s for s in trial.get('samples',[]) if isinstance(s,dict)
            and type(s.get('frame')) is int and type(trigger) is int and s['frame']>trigger]


def _relative_signature(trial):
    """Use physical values at relative frame index, not actor ID/absolute clock."""
    records=_post_samples(trial)
    if not records:return ()
    first=records[0]
    return tuple((round(s['speed_mps'],5),round(s['signed_longitudinal_accel_mps2'],4),
                  round(s['yaw_rate_radps_carla'],5),
                  round(s['x_m_carla']-first['x_m_carla'],4),
                  round(s['y_m_carla']-first['y_m_carla'],4)) for s in records)


def describe_control_trials(document, *, expected_repeats=3):
    """Independent report, never upgrades CAPTURED to verified physics."""
    result={'schema':'rampd.a61.carla.descriptive.v1','status':'REVIEW',
            'physical_certified':False,'model_error_enclosure_certified':False,
            'guaranteed_braking_lower_bound_available':False,
            'actuator_delay_upper_bound_certified':False,'reasons':[]}
    if not isinstance(document,dict) or document.get('schema')!='rampd.carla.a59_1.raw_trials.v1':
        result['reasons'].append('WRONG_RAW_SCHEMA');return result
    rows=document.get('trials')
    if not isinstance(rows,list):result['reasons'].append('INVALID_TRIAL_ROWS');return result
    result['actor_geometry']=reconstruct_actor_geometry(document)
    buckets=defaultdict(list); groups=[]; reasons=[]
    for t in rows:
        if not isinstance(t,dict):reasons.append('INVALID_TRIAL');continue
        key=(t.get('target_speed_mps'),t.get('maneuver'))
        if key not in {(s,m) for s in (5,10,15) for m in ('brake','steer','combined')}:
            reasons.append('UNKNOWN_TRIAL_CATEGORY');continue
        buckets[key].append(t)
    for speed in (5,10,15):
        for maneuver in ('brake','steer','combined'):
            trialset=buckets[(speed,maneuver)]
            captured=sum(t.get('status')=='CAPTURED' for t in trialset)
            incomplete=sum(t.get('status')!='CAPTURED' for t in trialset)
            maxacc=[];minacc=[];peak_yaw=[];missing_steer=0
            for t in trialset:
                values=_post_samples(t)
                if values:
                    maxacc.append(max(abs(s['signed_longitudinal_accel_mps2']) for s in values))
                    minacc.append(min(s['signed_longitudinal_accel_mps2'] for s in values))
                    peak_yaw.append(max(abs(s['yaw_rate_radps_carla']) for s in values))
                    if all(s.get('wheel_steer_deg_front_left_raw') is None for s in values):
                        missing_steer+=1
            sigs=[_relative_signature(t) for t in trialset if t.get('status')=='CAPTURED']
            repeated=len(sigs)>1 and len(set(sigs))==1
            groups.append({'speed_mps':speed,'maneuver':maneuver,'attempts':len(trialset),
                           'captured':captured,'incomplete':incomplete,
                           'incomplete_statuses':dict(Counter(t.get('status','MISSING_STATUS') for t in trialset if t.get('status')!='CAPTURED')),
                           'peak_abs_signed_longitudinal_acceleration_mps2':max(maxacc,default=None),
                           'min_signed_longitudinal_acceleration_mps2':min(minacc,default=None),
                           'peak_abs_yaw_rate_radps':max(peak_yaw,default=None),
                           'runs_all_missing_front_wheel_angle':missing_steer,
                           'same_captured_response_to_5_digit_precision':repeated})
            if len(trialset)!=expected_repeats:reasons.append(f'REPEAT_COUNT_MISMATCH:{speed}:{maneuver}')
            if incomplete:reasons.append(f'INCOMPLETE_CONTROL_TRIALS:{speed}:{maneuver}')
            if repeated:reasons.append(f'REPLICATED_DETERMINISTIC_RESPONSE_NO_VARIABILITY_EVIDENCE:{speed}:{maneuver}')
            if missing_steer and maneuver in ('steer','combined'):
                reasons.append(f'MISSING_ACTUAL_WHEEL_STEER_SIGNAL:{speed}:{maneuver}')
    result['groups']=groups
    result['attempts']=sum(g['attempts'] for g in groups)
    result['captured']=sum(g['captured'] for g in groups)
    result['incomplete']=sum(g['incomplete'] for g in groups)
    result['peak_abs_signed_longitudinal_acceleration_mps2']=max((g['peak_abs_signed_longitudinal_acceleration_mps2'] for g in groups if g['peak_abs_signed_longitudinal_acceleration_mps2'] is not None),default=None)
    if result['peak_abs_signed_longitudinal_acceleration_mps2'] is not None and result['peak_abs_signed_longitudinal_acceleration_mps2']>1.5*9.81:
        reasons.append('HIGH_ACCELERATION_REQUIRES_FRICTION_AND_SENSOR_EXPLANATION_NOT_REAL_CAR_LIMIT')
    if result['actor_geometry']['status']=='REVIEW':reasons.extend(result['actor_geometry']['reasons'])
    result['reasons']=sorted(set(reasons))
    result['status']=('DESCRIPTIVE_FULL_GRID_CARLA_RESPONSE_CAPTURED_NOT_CERTIFIED'
                      if result['captured']==len(rows)==9*expected_repeats
                      else 'DESCRIPTIVE_PARTIAL_CARLA_RESPONSE_CAPTURED' if result['captured'] else 'REVIEW')
    return result
