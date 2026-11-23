"""A59/1b-0J: strictly descriptive, independent single CARLA control-trial audit.

No log, even an accepted log, proves a robust physical error interval, a
worst-case actuator bound, or a safety certificate. All timestamps and commands
are data supplied by the producer rather than independently authenticated ACKs.
"""
from __future__ import annotations
from math import ceil, hypot, isfinite


def _num(x):
    return type(x) in (int,float) and isfinite(x)


def combined_brake_profile(trial, post):
    """Return (fraction, provenance) without creating a calibration claim.

    A60 now records explicit per-trial fractions. Older A67 fixtures predate
    this field; infer a *description* only if all 40 observed commands are
    finite, constant and within capture's permitted [0.05,0.80] domain.
    An invalid explicitly declared fraction must never be replaced by inference.
    """
    f=trial.get('combined_brake_fraction')
    if f is not None:
        return f,'DECLARED_INTERVENTION'
    if post and all(isinstance(s,dict) and _num(s.get('command_brake')) for s in post):
        f=post[0]['command_brake']
        if .05<=f<=.8 and all(abs(s['command_brake']-f)<=.025 for s in post):
            return f,'LEGACY_CONSTANT_COMMAND_INFERRED_DESCRIPTIVELY'
    return None,'MISSING_OR_NONCONSTANT_LEGACY_CONTROL'


def audit_single_control_smoke(doc):
    reasons=[]
    result={'schema':'rampd.a64.carla.single_smoke_review.v1', 'status':'REVIEW',
            'reasons':reasons, 'physical_certified':False,
            'actuator_calibrated':False,'safe_training_labels_allowed':False}
    if not isinstance(doc,dict):
        reasons.append('INVALID_DOCUMENT');return result
    if doc.get('schema')!='rampd.carla.a59_1.raw_trials.v1':reasons.append('RAW_SCHEMA_MISMATCH')
    if doc.get('experiment_scope')!='SINGLE_CONTROL_SMOKE':reasons.append('NOT_A_SINGLE_CONTROL_SMOKE')
    if doc.get('carla_server_version','').split('-',1)[0]!='0.9.16':reasons.append('CARLA_VERSION_UNVERIFIED')
    if doc.get('world_exclusive_confirmed') is not True:reasons.append('TICK_EXCLUSIVITY_NOT_DECLARED')
    if not isinstance(doc.get('map'),str) or not doc['map']:reasons.append('MISSING_MAP')
    if doc.get('actor_type')!='vehicle.tesla.model3':reasons.append('WRONG_BLUEPRINT')
    if doc.get('calibrated_vehicle_dynamics') is not False:reasons.append('FALSE_CALIBRATED_FLAG')
    if doc.get('status') != 'RAW_CARLA_TRIALS_CAPTURED_NOT_CERTIFIED':reasons.append('TOP_LEVEL_NOT_CAPTURED')
    projection=(doc.get('site_audit') or {}).get('chosen_start_projection_audit') or {}
    if projection.get('status')!='DESCRIPTIVE_LANE_IDENTITY_REPRODUCED':
        reasons.append('START_SITE_IDENTITY_UNVERIFIED')
    if (doc.get('start_lane_recheck') or {}).get('accepted') is not True:
        reasons.append('START_LANE_RECHECK_UNVERIFIED')
    physics=doc.get('physics') or {}
    if (not isinstance(physics,dict) or len(physics.get('wheels',[]))!=4
            or physics.get('actor_type')!='vehicle.tesla.model3'):
        reasons.append('ACTOR_PHYSICS_NOT_CAPTURED')
    step=doc.get('step_s')
    if not _num(step) or not 0<step<=0.05:
        reasons.append('INVALID_FIXED_STEP');step=0.05
    rows=doc.get('trials')
    if not isinstance(rows,list) or len(rows)!=1:
        reasons.append('EXPECTED_EXACTLY_ONE_TRIAL');return result
    t=rows[0]
    if not isinstance(t,dict):reasons.append('MALFORMED_TRIAL');return result
    result['trial_status']=t.get('status')
    if type(t.get('actor_id')) is not int or t.get('actor_id')!=doc.get('actor_id'):
        reasons.append('ACTOR_ID_NOT_BOUND_TO_TRIAL')
    if t.get('status')!='CAPTURED':reasons.append('CONTROL_TRIAL_NOT_COMPLETED')
    speed,kind=t.get('target_speed_mps'),t.get('maneuver')
    if speed not in (5,10,15) or kind not in ('brake','steer','combined'):
        reasons.append('INVALID_TARGET_OR_MANEUVER')
    stable=t.get('settling')
    if not isinstance(stable,dict) or stable.get('status')!='DESCRIPTIVE_STATIONARY_HEIGHT_STABLE':
        reasons.append('NO_GROUNDED_PRETRIAL_EVIDENCE')
    else:
        if stable.get('lane_audit',{}).get('status')!='DESCRIPTIVE_RECTANGLE_WITHIN_LANE':
            reasons.append('SETTLING_LANE_UNVERIFIED')
        if stable.get('ground_height_proxy',{}).get('status')!='DESCRIPTIVE_WHEEL_HEIGHT_NEAR_ROAD':
            reasons.append('SETTLING_GROUND_UNVERIFIED')
    samples=t.get('samples')
    if not isinstance(samples,list) or not samples:
        reasons.append('NO_FRAME_SAMPLES');return result
    trigger=t.get('trigger_frame')
    if type(trigger) is not int or trigger<0:
        reasons.append('NO_VALID_TRIGGER_FRAME')
        return result
    if not _num(t.get('trigger_speed_mps')) or not _num(speed) or abs(t['trigger_speed_mps']-speed)>0.5:
        reasons.append('TRIGGER_SPEED_NOT_AT_TARGET')
    before=[];after=[];lastframe=None;lasttime=None
    required=('frame','sim_time_s','planar_speed_mps','vertical_speed_mps',
              'speed_mps','command_throttle','command_brake','command_steer',
              'actual_throttle','actual_brake','actual_steer',
              'signed_longitudinal_accel_mps2','yaw_rate_radps_carla',
              'command_reference_sim_time_s','wheel_steer_deg_front_left_raw',
              'wheel_steer_deg_front_right_raw')
    for i,s in enumerate(samples):
        if not isinstance(s,dict) or any(k not in s or not _num(s[k]) for k in required):
            reasons.append('MISSING_OR_NONFINITE_CONTROL_SIGNAL');break
        if type(s['frame']) is not int:reasons.append('FRAME_NOT_INTEGER');break
        if lastframe is not None and s['frame']!=lastframe+1:
            reasons.append('NONCONTIGUOUS_CARLA_FRAMES');break
        if lasttime is not None and abs((s['sim_time_s']-lasttime)-step)>max(1e-4,step*0.05):
            reasons.append('IRREGULAR_SIM_TIME');break
        if s.get('command_issued_before_tick') is not True:
            reasons.append('COMMAND_BEFORE_TICK_NOT_RECORDED')
        if abs(s['speed_mps']-hypot(s['planar_speed_mps'],s['vertical_speed_mps']))>0.02:
            reasons.append('SPEED_COMPONENT_INCONSISTENCY')
        if s.get('lane_audit',{}).get('status')!='DESCRIPTIVE_RECTANGLE_WITHIN_LANE':
            reasons.append('LANE_ENVELOPE_UNVERIFIED')
        if s.get('wheel_steer_query_error') is not None:
            reasons.append('FRONT_WHEEL_ANGLE_QUERY_FAILED')
        if any(abs(s['command_'+k]-s['actual_'+k])>0.025
               for k in ('throttle','brake','steer')):
            reasons.append('APPLIED_CONTROL_DIFFERS_FROM_COMMAND')
        if s['frame']<=trigger:
            before.append(s)
        else:
            after.append(s)
        if lasttime is not None and abs(s['command_reference_sim_time_s']-lasttime)>max(1e-4,step*0.05):
            reasons.append('COMMAND_REFERENCE_TIME_MISMATCH')
        lastframe,lasttime=s['frame'],s['sim_time_s']
    result['pretrigger_samples']=len(before)
    result['posttrigger_samples']=len(after)
    if not before or before[-1].get('frame')!=trigger:
        reasons.append('TRIGGER_FRAME_NOT_OBSERVED')
    if len(after)!=int(2.0/step):
        reasons.append('INCOMPLETE_TWO_SECOND_POSTCONTROL_WINDOW')
    if after and after[0]['frame']!=trigger+1:
        reasons.append('COMMAND_TRANSITION_FRAME_MISSING')
    if any(abs(s['command_steer'])>0.001 or s['command_brake']>0.001 for s in before):
        reasons.append('PRETRIGGER_COMMAND_NOT_ACCELERATION')
    if after:
        if kind=='brake':
            has_excitation=any(s['command_brake']>=.3 and abs(s['command_steer'])<=.001 for s in after)
        elif kind=='steer':
            has_excitation=any(abs(s['command_steer'])>=.025 and s['command_brake']<.1 for s in after)
        else:
            # A60 permits combined brake profiles in [0.05, 0.80]. An old
            # hard-coded >=0.20 test falsely rejected valid 0.15 diagnostics.
            # Check the *declared* intervention, not a fixed legacy threshold.
            f,profile_source=combined_brake_profile(t,after)
            result['combined_brake_profile_source']=profile_source
            if not _num(f) or not .05<=f<=.8:
                reasons.append('INVALID_DECLARED_COMBINED_BRAKE_PROFILE')
                has_excitation=False
            else:
                has_excitation=any(abs(s['command_brake']-f)<=.025 and
                                   abs(s['command_steer'])>=.025 for s in after)
                if any(abs(s['command_brake']-f)>.025 for s in after):
                    reasons.append('POSTTRIGGER_BRAKE_NOT_DECLARED_PROFILE')
        if not has_excitation:reasons.append('CONTROL_EXCITATION_NOT_COMMANDED')
        if kind in ('steer','combined') and not any(
                max(abs(s['wheel_steer_deg_front_left_raw']),
                    abs(s['wheel_steer_deg_front_right_raw']))>0.01 for s in after):
            reasons.append('NO_MEASURABLE_FRONT_WHEEL_STEER_RESPONSE')
        result['descriptive_min_longitudinal_accel_mps2']=min(
            s['signed_longitudinal_accel_mps2'] for s in after)
        result['descriptive_max_abs_yaw_rate_radps']=max(
            abs(s['yaw_rate_radps_carla']) for s in after)
    result['reasons']=sorted(set(reasons))
    result['status']=('DESCRIPTIVE_SINGLE_CONTROL_SMOKE_CAPTURED_NOT_CALIBRATED'
                      if not reasons else 'REVIEW')
    return result
