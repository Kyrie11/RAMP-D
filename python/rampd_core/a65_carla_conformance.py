"""A65: independent *descriptive* CARLA longitudinal conformance audit.

A captured/sampled maneuver is not a calibrated actuator.  Torque/radius/mass
is a deliberately simple *comparison model*, NOT a sound upper deceleration
bound for CARLA/real vehicles.  All statuses are fail-closed for training.
"""
from __future__ import annotations
from math import isfinite, hypot
from statistics import median
from .a64_carla_smoke_evidence import audit_single_control_smoke


def _num(x):
    return type(x) in (int, float) and isfinite(x)


def audit_brake_conformance(document, *, discrepancy_factor=3.0):
    if not _num(discrepancy_factor) or discrepancy_factor <= 1:
        raise ValueError('discrepancy_factor must exceed one')
    capture = audit_single_control_smoke(document)
    reasons = []
    result = dict(schema='rampd.a65.carla.brake_conformance.v1',
                  status='REVIEW', reasons=reasons,
                  source_capture_status=capture['status'],
                  physical_certified=False, actuator_calibrated=False,
                  safe_training_labels_allowed=False,
                  full_continuous_lane_safety_certified=False,
                  torque_only_comparison_is_certified_bound=False,
                  friction_coefficient_identified=False)
    if capture['status'] != 'DESCRIPTIVE_SINGLE_CONTROL_SMOKE_CAPTURED_NOT_CALIBRATED':
        reasons.append('SOURCE_SMOKE_CAPTURE_NOT_ACCEPTED')
    if not isinstance(document, dict):
        reasons.append('INVALID_SOURCE');return result
    trials = document.get('trials')
    if not isinstance(trials, list) or len(trials)!=1 or not isinstance(trials[0],dict):
        reasons.append('EXACTLY_ONE_TRIAL_REQUIRED');return result
    trial = trials[0]
    if trial.get('maneuver') != 'brake':
        reasons.append('BRAKE_TRIAL_REQUIRED');return result
    source = document.get('physics', {})
    mass = source.get('mass_kg_raw') if isinstance(source,dict) else None
    wheels = source.get('wheels') if isinstance(source,dict) else None
    if not _num(mass) or mass<=0 or not isinstance(wheels,list) or len(wheels)!=4:
        reasons.append('MISSING_MASS_OR_WHEEL_PHYSICS');return result
    wheel_forces=[]
    for wheel in wheels:
        if not isinstance(wheel,dict):
            reasons.append('MISSING_WHEEL_PHYSICS');return result
        torque=wheel.get('max_brake_torque_nm_raw')
        radius=wheel.get('radius_cm_raw')
        if not _num(torque) or torque<0 or not _num(radius) or not 10<=radius<=100:
            reasons.append('INVALID_TORQUE_OR_RADIUS_UNITS');return result
        wheel_forces.append(torque/(radius/100.0))
    torque_only = sum(wheel_forces)/mass
    result['torque_only_flat_road_decel_comparison_mps2']=torque_only
    result['source_simulation_friction_parameter']=[w.get('tire_friction_raw') for w in wheels]
    samples=trial.get('samples')
    trigger=trial.get('trigger_frame')
    if not isinstance(samples,list) or type(trigger) is not int or trigger<0:
        reasons.append('MISSING_TRIGGER_OR_SAMPLES');return result
    post=[]; diff_errors=[]; derived=[]; max_sensor_decel=0.; max_fd_decel=0.
    sampled_lane_margins=[]
    preceding=None
    for sample in samples:
        if not isinstance(sample,dict):
            reasons.append('INVALID_SAMPLE');return result
        fields=('frame','sim_time_s','planar_speed_mps','signed_longitudinal_accel_mps2',
                'command_brake','command_throttle','yaw_rate_radps_carla')
        if any(not _num(sample.get(k)) for k in fields) or type(sample.get('frame')) is not int:
            reasons.append('MISSING_FINITE_MEASUREMENT');return result
        if sample['frame']>trigger:
            post.append(sample)
            lane=sample.get('lane_audit',{})
            available=lane.get('available_halfwidth_m') if isinstance(lane,dict) else None
            required_width=lane.get('required_halfwidth_m') if isinstance(lane,dict) else None
            if not _num(available) or not _num(required_width):
                reasons.append('MISSING_NUMERIC_LANE_CLEARANCE_EVIDENCE')
            else:
                clearance=available-required_width
                sampled_lane_margins.append(clearance)
                if clearance<0:reasons.append('NEGATIVE_SAMPLED_LANE_CLEARANCE')
            # Near a complete stop speed magnitudes are non-differentiable
            # and not good evidence for a longitudinal derivative.
            if sample['planar_speed_mps']>0.5 and sample['command_brake']>=0.3:
                max_sensor_decel=max(max_sensor_decel,-sample['signed_longitudinal_accel_mps2'])
            if preceding is not None and min(sample['planar_speed_mps'],preceding['planar_speed_mps'])>0.5:
                dt=sample['sim_time_s']-preceding['sim_time_s']
                if dt<=0 or sample['frame']!=preceding['frame']+1:
                    reasons.append('NONCONTIGUOUS_SPEED_DERIVATIVE')
                else:
                    fd=(sample['planar_speed_mps']-preceding['planar_speed_mps'])/dt
                    if sample['command_brake']>=0.3:
                        max_fd_decel=max(max_fd_decel,-fd)
                        diff_errors.append(abs(fd-sample['signed_longitudinal_accel_mps2']))
                        derived.append({'frame':sample['frame'], 'dv_dt_mps2':fd,
                                        'reported_longitudinal_accel_mps2':sample['signed_longitudinal_accel_mps2']})
        preceding=sample
    result['postcontrol_frames']=len(post)
    result['min_postcontrol_sampled_lane_clearance_m']=(min(sampled_lane_margins)
                                                         if sampled_lane_margins else None)
    result['sampled_lane_check_is_continuous_time_proof']=False
    # Camera/road polygon/continuous swept hull evidence is not in this log.
    # These are only pointwise pose checks, even if every logged frame passed.
    if not post:
        reasons.append('NO_POSTCONTROL_FRAMES');return result
    if not diff_errors:
        reasons.append('NO_MOVING_BRAKE_DERIVATIVES')
    result['moving_brake_dv_dt_crosscheck']=derived
    result['max_reported_deceleration_mps2']=max_sensor_decel
    result['max_speed_difference_deceleration_mps2']=max_fd_decel
    result['median_abs_accel_dvdt_error_mps2']=median(diff_errors) if diff_errors else None
    result['max_abs_accel_dvdt_error_mps2']=max(diff_errors) if diff_errors else None
    result['reported_to_torque_only_ratio']=(max_sensor_decel/torque_only if torque_only>0 else None)
    result['speed_difference_to_torque_only_ratio']=(max_fd_decel/torque_only if torque_only>0 else None)
    if torque_only<=0:
        reasons.append('ZERO_BRAKE_TORQUE_COMPARISON')
    elif (max_sensor_decel>discrepancy_factor*torque_only and
          max_fd_decel>discrepancy_factor*torque_only):
        # Confirmed in two channels, NOT two independent physical sensors:
        # CARLA acceleration and its velocity are generated by the same physics engine.
        reasons.append('GROSS_TORQUE_ONLY_MODEL_DISCREPANCY')
    if diff_errors and median(diff_errors)>max(0.3,0.15*max_sensor_decel):
        reasons.append('VELOCITY_AND_ACCELERATION_INCONSISTENT')
    if diff_errors and max(diff_errors)>max(2.0,0.25*max(max_sensor_decel,max_fd_decel)):
        reasons.append('SINGLE_FRAME_ACCEL_VELOCITY_MISMATCH')
    # A zero-crossing of net longitudinal acceleration is NOT the actual
    # brake actuator latency (throttle release and drivetrain are confounders).
    release_time=post[0]['command_reference_sim_time_s'] if post and _num(post[0].get('command_reference_sim_time_s')) else None
    if release_time is not None:
        prior=None
        for s in post:
            if s['signed_longitudinal_accel_mps2']<0 and s['planar_speed_mps']>0.5:
                result['net_decel_sign_change_observed_after_command_s'] = s['sim_time_s']-release_time
                result['actuator_latency_estimated_from_this'] = False
                break
            prior=s
    if post:
        reference=next((s for s in samples if s['frame']==trigger),None)
        stopped=next((s for s in post if s['planar_speed_mps']<=0.15),None)
        if reference and stopped and all(_num(z.get(k)) for z in (reference,stopped)
                                          for k in ('x_m_carla','y_m_carla')):
            result['sampled_trigger_to_near_stop_displacement_m']=hypot(
                stopped['x_m_carla']-reference['x_m_carla'],
                stopped['y_m_carla']-reference['y_m_carla'])
            result['near_stop_threshold_mps']=0.15
    # A valid capture or absence of gross mismatch does NOT grant a bound.
    result['reasons']=sorted(set(reasons))
    result['status']=('DESCRIPTIVE_BRAKE_TRACE_RECORDED_MODEL_CONFORMANCE_REVIEW'
                      if result['reasons'] else
                      'DESCRIPTIVE_BRAKE_TRACE_RECORDED_NO_GROSS_MISMATCH_NOT_CALIBRATED')
    return result
