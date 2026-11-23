"""A67 independent longitudinal+lateral diagnostic of a *single* CARLA smoke.

This is not a friction estimate, an actuator-delay measurement, a physics
certificate, or a source of formal safety supervision. It deliberately separates
capture quality, a coupled response observation, and torque-only discrepancy.
"""
from __future__ import annotations
from math import hypot, isfinite
from .a64_carla_smoke_evidence import audit_single_control_smoke,combined_brake_profile
from .a66_carla_lateral_witness import audit_steering_lane_witness


def _num(x):
    return type(x) in (int, float) and isfinite(x)


def audit_combined_dynamics(document: object, *, gross_ratio: float = 3.0) -> dict:
    if not _num(gross_ratio) or gross_ratio <= 1:
        raise ValueError('gross_ratio must exceed one')
    report = dict(schema='rampd.a67.carla.combined_diagnostic.v1', status='REVIEW',
                  reasons=[], scope='ONE_SIMULATOR_TRACE_WITHIN_DECLARED_CONFIG',
                  captured=False, sampled_lane_witness=False,
                  diagnostic_repetition_allowed=False,
                  torque_only_model_is_physical_bound=False,
                  torque_only_model_validated=False,
                  measured_real_tire_friction=False, calibrated_vehicle_dynamics=False,
                  verified_uncertainty_enclosure=False,
                  continuous_lane_safety_certified=False,
                  safety_training_labels_allowed=False)
    r = report['reasons']
    cap = audit_single_control_smoke(document)
    lat = audit_steering_lane_witness(document)
    report['capture_status'] = cap['status']
    report['lateral_status'] = lat['status']
    if cap['status'] != 'DESCRIPTIVE_SINGLE_CONTROL_SMOKE_CAPTURED_NOT_CALIBRATED':
        r.append('CONTROL_CAPTURE_UNACCEPTED')
    if lat['status'] != 'DESCRIPTIVE_STEER_SAMPLE_AND_INTERPOLATION_WITNESS_NOT_CERTIFIED':
        r.append('LATERAL_WITNESS_UNACCEPTED')
    if not isinstance(document, dict) or not isinstance(document.get('trials'), list) or len(document['trials']) != 1:
        r.append('EXACTLY_ONE_TRIAL_REQUIRED'); return report
    trial = document['trials'][0]
    if not isinstance(trial, dict) or trial.get('maneuver') != 'combined':
        r.append('COMBINED_MANEUVER_REQUIRED'); return report
    samples = trial.get('samples')
    if not isinstance(samples, list) or len(samples) < 4 or type(trial.get('trigger_frame')) is not int:
        r.append('INCOMPLETE_TRIAL'); return report
    trigger = trial['trigger_frame']
    post = [s for s in samples if isinstance(s, dict) and type(s.get('frame')) is int and s['frame'] > trigger]
    if not post or any(any(not _num(s.get(k)) for k in (
        'sim_time_s','planar_speed_mps','signed_longitudinal_accel_mps2','yaw_rate_radps_carla',
        'command_brake','command_steer','wheel_steer_deg_front_left_raw','wheel_steer_deg_front_right_raw',
        'x_m_carla','y_m_carla')) for s in post):
        r.append('INCOMPLETE_POSTCONTROL_SIGNALS'); return report
    # Source capture supports graded brake fractions down to 0.05. Never
    # assume that 0.45 (or the former >=0.2) is the only valid intervention.
    declared_fraction,profile_source=combined_brake_profile(trial,post)
    report['combined_brake_profile_source']=profile_source
    if not _num(declared_fraction) or not .05<=declared_fraction<=.8:
        r.append('INVALID_DECLARED_COMBINED_BRAKE_PROFILE')
        return report
    report['declared_brake_fraction']=declared_fraction
    if any(abs(s['command_brake']-declared_fraction)>.025 for s in post):
        r.append('POSTTRIGGER_BRAKE_NOT_DECLARED_PROFILE')
    simultaneous = [s for s in post if abs(s['command_brake']-declared_fraction)<=.025
                    and abs(s['command_steer']) >= .025]
    report['simultaneous_command_frames'] = len(simultaneous)
    report['simultaneous_brake_steer_yaw_response_frames'] = sum(
        1 for s in simultaneous if abs(s['wheel_steer_deg_front_left_raw']) >= .05
        and abs(s['wheel_steer_deg_front_right_raw']) >= .05
        and abs(s['yaw_rate_radps_carla']) >= .003)
    report['peak_abs_front_wheel_deg'] = max(max(abs(s['wheel_steer_deg_front_left_raw']),
                                                 abs(s['wheel_steer_deg_front_right_raw'])) for s in post)
    report['peak_abs_yaw_rate_radps'] = max(abs(s['yaw_rate_radps_carla']) for s in post)
    report['reported_max_deceleration_mps2'] = max(0.,-min(s['signed_longitudinal_accel_mps2'] for s in post))
    report['max_brake_command'] = max(s['command_brake'] for s in post)
    if not simultaneous or report['simultaneous_brake_steer_yaw_response_frames'] < 1:
        r.append('NO_MEASURABLE_SIMULTANEOUS_CONTROL_RESPONSE')
    recorded = []
    by_frame = {s.get('frame'):s for s in samples if isinstance(s,dict)}
    for s in post:
        p = by_frame.get(s['frame']-1)
        if not p or not _num(p.get('planar_speed_mps')) or not _num(p.get('sim_time_s')):
            r.append('MISSING_PREVIOUS_FRAME_FOR_SPEED_DIFFERENCE'); continue
        dt = s['sim_time_s']-p['sim_time_s']
        if not 0 < dt <= 0.051:
            r.append('INVALID_DIFFERENCE_TIME');continue
        # Strictly moving pairs; this magnitude difference is not longitudinal
        # acceleration through a reversal or as the vehicle reaches zero speed.
        if min(s['planar_speed_mps'],p['planar_speed_mps']) > .5:
            fd = (s['planar_speed_mps']-p['planar_speed_mps'])/dt
            recorded.append((s['frame'],fd,s['signed_longitudinal_accel_mps2']))
    report['moving_velocity_difference_pairs'] = len(recorded)
    report['max_speed_difference_deceleration_mps2'] = (max(0.,-min(x[1] for x in recorded)) if recorded else None)
    report['max_abs_speed_difference_accel_disagreement_mps2'] = (
        max(abs(x[1]-x[2]) for x in recorded) if recorded else None)
    if not recorded:r.append('NO_MOVING_VELOCITY_DIFFERENCES')
    physics = document.get('physics')
    wheels = physics.get('wheels') if isinstance(physics,dict) else None
    mass = physics.get('mass_kg_raw') if isinstance(physics,dict) else None
    if not _num(mass) or mass<=0 or not isinstance(wheels,list) or len(wheels)!=4:
        r.append('NO_ACTOR_MASS_AND_FOUR_WHEEL_PARAMETERS');return report
    terms=[]
    for wheel in wheels:
        if not isinstance(wheel,dict) or not _num(wheel.get('max_brake_torque_nm_raw')) or not _num(wheel.get('radius_cm_raw')) or not 10 <= wheel['radius_cm_raw'] <= 100 or wheel['max_brake_torque_nm_raw'] < 0:
            r.append('INVALID_TORQUE_RADIUS_UNITS');return report
        terms.append(wheel['max_brake_torque_nm_raw']/(wheel['radius_cm_raw']/100.0))
    torque_only=sum(terms)/mass
    report['full_command_torque_only_comparison_mps2'] = torque_only
    report['brake_scaled_torque_only_comparison_mps2'] = torque_only*report['max_brake_command']
    # This simplified comparison is NOT asserted to be a bound for CARLA's
    # nonlinear wheel/engine/tire simulation; a disagreement requests review.
    report['reported_to_full_command_torque_ratio'] = (
        report['reported_max_deceleration_mps2']/torque_only if torque_only>0 else None)
    report['reported_to_brake_scaled_torque_ratio'] = (
        report['reported_max_deceleration_mps2']/(torque_only*report['max_brake_command'])
        if torque_only>0 and report['max_brake_command']>0 else None)
    if torque_only <= 0:r.append('ZERO_TORQUE_COMPARISON')
    elif (report['reported_max_deceleration_mps2']>gross_ratio*torque_only and
          recorded and report['max_speed_difference_deceleration_mps2']>gross_ratio*torque_only):
        r.append('GROSS_TORQUE_ONLY_MODEL_DISCREPANCY')
    # Capture is acceptable for *diagnostic* repeats even when the assumed
    # torque-only model is contradicted: reproducibility is precisely what
    # a repeated experiment investigates, not proof of model validity.
    report['captured']=(cap['status']=='DESCRIPTIVE_SINGLE_CONTROL_SMOKE_CAPTURED_NOT_CALIBRATED')
    report['sampled_lane_witness']=(lat['status']=='DESCRIPTIVE_STEER_SAMPLE_AND_INTERPOLATION_WITNESS_NOT_CERTIFIED')
    report['diagnostic_repetition_allowed']=(report['captured'] and report['sampled_lane_witness'] and
                                            'NO_MEASURABLE_SIMULTANEOUS_CONTROL_RESPONSE' not in r and
                                            'POSTTRIGGER_BRAKE_NOT_DECLARED_PROFILE' not in r)
    report['reasons'] = sorted(set(r))
    report['status'] = ('DIAGNOSTIC_REPEAT_ELIGIBLE_MODEL_REVIEW_NOT_CALIBRATED'
                        if report['diagnostic_repetition_allowed'] else 'REVIEW')
    return report
