"""A71 independently paired CARLA brake-only vs combined-maneuver comparison.

This is a *single-condition observational response comparison*, not calibrated
actuation, physics conformance, identification of interaction or causal proof.
All compared post-trigger samples must satisfy the same acquisition protocol;
actor IDs, run frame offsets and simulation epoch may differ. A nonzero steering
pulse is the only allowed deliberate intervention in the stated comparison.
"""
from __future__ import annotations
import hashlib, json, math


def _digest(d):
    return hashlib.sha256(json.dumps(d,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()


def _speed(s):
    x=s.get('planar_speed_mps')
    if type(x) not in (int,float) or not math.isfinite(x) or x<0:
        raise ValueError('invalid planar speed')
    return float(x)


def audit_brake_steer_pair(pure,combined,*,brake:float=0.15):
    """Strict descriptive paired comparison, never a causal label or tube."""
    reasons=[];pairs=[]
    if type(brake) not in (float,int) or not math.isfinite(brake) or not 0<brake<=1:
        raise ValueError('declared brake must be finite in (0,1]')
    for name,d,expected in (('pure',pure,'brake'),('combined',combined,'combined')):
        if not isinstance(d,dict) or d.get('status')!='RAW_CARLA_TRIALS_CAPTURED_NOT_CERTIFIED' or d.get('calibrated_vehicle_dynamics') is not False:
            reasons.append(name+':INVALID_TOP_LEVEL_SCOPE');continue
        ts=d.get('trials',[])
        if len(ts)!=1 or ts[0].get('status')!='CAPTURED' or ts[0].get('maneuver')!=expected:
            reasons.append(name+':NOT_ONE_CAPTURED_EXPECTED_MANEUVER');continue
        t=ts[0]; samples=t.get('samples',())
        if len(samples)<10 or type(t.get('trigger_frame')) is not int:
            reasons.append(name+':MISSING_COMPLETE_FRAME_SEQUENCE');continue
        try:
            j=next(i for i,s in enumerate(samples) if s.get('frame')==t['trigger_frame'])
            if j<1 or len(samples)-j<35:raise ValueError('incomplete pre/post')
            dt=float(d.get('step_s'))
            if abs(dt-.05)>1e-9:raise ValueError('unsupported tick')
            if any(samples[i+1]['frame']!=samples[i]['frame']+1 for i in range(len(samples)-1)):
                raise ValueError('frame sequence gap')
            if any(abs((samples[i+1]['sim_time_s']-samples[i]['sim_time_s'])-dt)>1e-5 for i in range(len(samples)-1)):
                raise ValueError('simulation time sequence gap')
            # trigger frame contains the final pre-control state; control begins at j+1
            post=samples[j+1:]
            if any(not isinstance(x.get('lane_audit'),dict) or x['lane_audit'].get('status')!='DESCRIPTIVE_RECTANGLE_WITHIN_LANE' for x in post):
                raise ValueError('off-lane/unknown sampled footprint')
            if any(abs(x['command_brake']-brake)>1e-5 or abs(x['actual_brake']-brake)>1e-5 for x in post):
                raise ValueError('declared and effective brake mismatch')
            # A71 accidentally compared brake but never checked throttle.
            # Nonzero simultaneous traction would confound the intervention.
            if any(abs(x.get('command_throttle',99))>1e-6 or abs(x.get('actual_throttle',99))>1e-6
                   for x in post):raise ValueError('nonzero or missing throttle confounds braking')
            if any(x.get('command_issued_before_tick') is not True for x in post):
                raise ValueError('missing pre-tick command causality')
            if expected=='brake':
                if any(abs(x['command_steer'])>1e-7 or abs(x['actual_steer'])>1e-7 for x in post):
                    raise ValueError('pure arm contains steering')
            else:
                if max(abs(x['command_steer']) for x in post)<0.005 or max(abs(x['actual_steer']) for x in post)<0.005:
                    raise ValueError('combined arm has no steering pulse')
            if any(x.get('wheel_steer_query_error') is not None for x in post):
                raise ValueError('wheel steering readback incomplete')
            pairs.append((name,d,t,j,post))
        except (ValueError,KeyError,TypeError,StopIteration,OverflowError) as e:
            reasons.append(name+':INVALID_SAMPLES:'+str(e))
    if len(pairs)==2:
        (n0,d0,t0,j0,a),(n1,d1,t1,j1,b)=pairs
        try:
            for field in ('map','actor_type','carla_server_version','step_s','capture_protocol_version','start_site_protocol_version','expected_start_lane'):
                if d0.get(field)!=d1.get(field):reasons.append('CROSS_ARM_'+field.upper()+'_DIFFERS')
            for field in ('opendrive_sha256','weather_raw','settings'):
                if d0.get('world_provenance',{}).get(field)!=d1.get('world_provenance',{}).get(field):reasons.append('WORLD_'+field.upper()+'_DIFFERS')
            def cleanphysics(d):
                o=dict(d.get('physics',{}));o.pop('actor_id',None);o.pop('body_transform',None);o.pop('capture_frame',None);o.pop('capture_state',None)
                return o
            if cleanphysics(d0)!=cleanphysics(d1):reasons.append('PHYSICS_CONTROL_DIFFERENT')
            if abs(float(t0['trigger_speed_mps'])-float(t1['trigger_speed_mps']))>0.02:reasons.append('TRIGGER_SPEED_DIFFERENT')
            if len(a)!=len(b):reasons.append('POST_CONTROL_FRAME_COUNTS_DIFFER')
            for name,post in (('pure',a),('combined',b)):
                if any(type(x['lane_audit'].get('available_halfwidth_m')) not in (int,float) or
                       type(x['lane_audit'].get('required_halfwidth_m')) not in (int,float) or
                       not math.isfinite(x['lane_audit']['available_halfwidth_m']) or
                       not math.isfinite(x['lane_audit']['required_halfwidth_m']) or
                       x['lane_audit']['available_halfwidth_m'] < x['lane_audit']['required_halfwidth_m']
                       for x in post):reasons.append('INVALID_NUMERIC_LANE_ENVELOPE:'+name)
            # Pure-brake steering settings are inert (all applied steer=0).
            # Comparing unused CLI defaults would falsely reject a legitimate
            # controlled steering intervention. The combined arm is validated
            # from actual per-frame commands above.
            if not reasons:
                va=[_speed(x) for x in a];vb=[_speed(x) for x in b]
                delta=[u-v for u,v in zip(vb,va)]
                moving_a=[x['signed_longitudinal_accel_mps2'] for x in a if _speed(x)>=1.]
                moving_b=[x['signed_longitudinal_accel_mps2'] for x in b if _speed(x)>=1.]
                if not moving_a or not moving_b:
                    reasons.append('NO_MOVING_REGIME_ABOVE_1_MPS')
                def path_length(pre,post):
                    points=[pre]+list(post)
                    return sum(math.hypot(u['x_m_carla']-v['x_m_carla'],
                                          u['y_m_carla']-v['y_m_carla']) for u,v in zip(points,points[1:]))
                result=dict(n_post_frames=len(delta),max_abs_speed_difference_mps=max(map(abs,delta)),
                  speed_difference_first_4_frames_mps=delta[:4],
                  min_sampled_lane_margin_pure_m=min(x['lane_audit']['available_halfwidth_m']-x['lane_audit']['required_halfwidth_m'] for x in a),
                  min_sampled_lane_margin_combined_m=min(x['lane_audit']['available_halfwidth_m']-x['lane_audit']['required_halfwidth_m'] for x in b),
                  max_abs_yaw_rate_pure_radps=max(abs(x['yaw_rate_radps_carla']) for x in a),
                  max_abs_yaw_rate_combined_radps=max(abs(x['yaw_rate_radps_carla']) for x in b),
                  peak_negative_acceleration_pure_mps2=min(x['signed_longitudinal_accel_mps2'] for x in a),
                  peak_negative_acceleration_combined_mps2=min(x['signed_longitudinal_accel_mps2'] for x in b),
                  moving_ge_1mps_min_longitudinal_accel_pure_mps2=min(moving_a) if moving_a else None,
                  moving_ge_1mps_min_longitudinal_accel_combined_mps2=min(moving_b) if moving_b else None,
                  pure_posttrigger_sampled_path_length_m=path_length(t0['samples'][j0],a),
                  combined_posttrigger_sampled_path_length_m=path_length(t1['samples'][j1],b),
                  low_speed_acceleration_spikes_must_not_be_braking_guarantees=True)
            else:result={}
        except (KeyError,TypeError,ValueError) as exc:
            reasons.append('BAD_PHYSICS_OR_FRAME_FIELDS:'+str(exc));result={}
    else:result={}
    reasons=sorted(set(reasons))
    return dict(schema='rampd.a71.carla.brake_steer_comparison.v1',
      status='DESCRIPTIVE_MATCHED_CAPTURE_REVIEW_MODEL_UNCALIBRATED' if not reasons else 'REVIEW',
      reasons=reasons,brake_fraction=brake,observations=result,
      two_arms_observed=len(pairs)==2,causal_identification_proved=False,
      physics_error_envelope_verified=False,actual_vehicle_validated=False,
      continuous_lane_safety_verified=False,safe_training_labels_allowed=False,
      canonical_json_sha256={'pure':_digest(pure),'combined':_digest(combined)})
