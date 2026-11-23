"""A66: independent, descriptive CARLA lateral response / lane witness.

All interpolated swept checks here apply ONLY to a specified linear XY and
shortest-arc linear heading interpolation between sampled poses, against a
source-declared straight lane. They are NOT true between-tick trajectory
bounds, map polygon proofs, CARLA collision proofs, or safety supervision.
"""
from __future__ import annotations
import math
from .a64_carla_smoke_evidence import audit_single_control_smoke


def _number(x):
    return type(x) in (int, float) and math.isfinite(x)


def _max_abs_trig(lo: float, hi: float, fn: str) -> float:
    """Exact extrema of |sin| or |cos| over a finite angular interval."""
    if lo > hi:
        lo, hi = hi, lo
    if hi-lo >= math.pi:
        return 1.0
    f = math.sin if fn == 'sin' else math.cos
    values = [abs(f(lo)), abs(f(hi))]
    phase = math.pi / 2 if fn == 'sin' else 0.0
    for k in range(math.floor((lo-phase)/math.pi),math.ceil((hi-phase)/math.pi)+1):
        candidate = phase+k*math.pi
        if lo<=candidate<=hi:
            values.append(1.0)
    return max(values)


def _wrapped_diff(a: float, b: float) -> float:
    return (a-b+math.pi)%(2*math.pi)-math.pi


def audit_steering_lane_witness(document: object) -> dict:
    """Reject incomplete steering evidence; never emit safety/training labels."""
    reasons=[]
    result={
        'schema':'rampd.a66.carla.lateral_witness.v1',
        'status':'REVIEW','reasons':reasons,
        'lane_witness_scope':'SOURCE_DECLARED_STRAIGHT_LANE_AND_INTERPOLATED_POSES_ONLY',
        'interpolation_is_verified_physical_trajectory':False,
        'continuous_lane_safety_certified':False,
        'actuator_calibrated':False,
        'safe_training_labels_allowed':False,
        'physical_uncertainty_bound_validated':False,
    }
    base=audit_single_control_smoke(document)
    result['source_smoke_status']=base['status']
    if base['status']!='DESCRIPTIVE_SINGLE_CONTROL_SMOKE_CAPTURED_NOT_CALIBRATED':
        reasons.append('SOURCE_SMOKE_NOT_ACCEPTED')
    if not isinstance(document,dict):
        reasons.append('INVALID_DOCUMENT');return result
    trialrows=document.get('trials')
    if not isinstance(trialrows,list) or len(trialrows)!=1 or not isinstance(trialrows[0],dict):
        reasons.append('EXACTLY_ONE_CONTROL_TRIAL_REQUIRED');return result
    trial=trialrows[0]
    if trial.get('maneuver') not in ('steer','combined'):
        reasons.append('STEERING_OR_COMBINED_TRIAL_REQUIRED');return result
    samples=trial.get('samples')
    if not isinstance(samples,list) or len(samples)<3:
        reasons.append('INSUFFICIENT_POSE_SAMPLES');return result
    physics=document.get('physics')
    bb=physics.get('bounding_box') if isinstance(physics,dict) else None
    ext=bb.get('extent') if isinstance(bb,dict) else None
    local=bb.get('location_local') if isinstance(bb,dict) else None
    if not isinstance(ext,dict) or not isinstance(local,dict) or any(
        not _number(d.get(k)) for d in (ext,local) for k in ('x','y')):
        reasons.append('MISSING_BOUNDING_BOX_GEOMETRY');return result
    hx,hy=ext['x'],ext['y']
    if not (0<hx<20 and 0<hy<10):
        reasons.append('INVALID_BODY_HALF_EXTENTS');return result
    if not isinstance(bb.get('rotation_local'),dict) or not _number(bb['rotation_local'].get('yaw_deg')) or abs(bb['rotation_local']['yaw_deg'])>1e-5:
        reasons.append('UNSUPPORTED_ROTATED_LOCAL_BOUNDING_BOX');return result
    offset=math.hypot(local['x'],local['y'])
    lane=(document.get('site_audit') or {}).get('chosen_waypoint')
    if not isinstance(lane,dict) or any(not _number(lane.get(k)) for k in ('x_m','y_m','yaw_deg')):
        reasons.append('MISSING_SOURCE_LANE_AXIS');return result
    if (lane.get('road_id'),lane.get('section_id'),lane.get('lane_id')) != tuple(
        (document.get('expected_start_lane') or {}).get(k) for k in ('road_id','section_id','lane_id')):
        reasons.append('START_LANE_IDENTITY_DISAGREEMENT')
    if not isinstance((document.get('world_provenance') or {}).get('opendrive_sha256'),str) or len(document['world_provenance']['opendrive_sha256'])!=64:
        reasons.append('NO_OPENDRIVE_PROVENANCE')
    lane_yaw=math.radians(lane['yaw_deg']);nx=-math.sin(lane_yaw);ny=math.cos(lane_yaw)
    trigger=trial.get('trigger_frame')
    if type(trigger) is not int or trigger<0:
        reasons.append('INVALID_TRIGGER_FRAME');return result
    positive=[];raw_margin=[];independent_margins=[];interp=[];yaw_deltas=[];body_yaws=[];lane_halfwidths=[];yaw_rate_residuals=[]
    for i,s in enumerate(samples):
        required=('frame','x_m_carla','y_m_carla','yaw_deg_carla','sim_time_s','command_steer',
                  'wheel_steer_deg_front_left_raw','wheel_steer_deg_front_right_raw','yaw_rate_radps_carla')
        if not isinstance(s,dict) or any(not _number(s.get(k)) for k in required):
            reasons.append('MISSING_FINITE_POSE_OR_ACTUATOR_SAMPLE');return result
        la=s.get('lane_audit')
        if not isinstance(la,dict) or any(not _number(la.get(k)) for k in ('required_halfwidth_m','available_halfwidth_m')):
            reasons.append('MISSING_SOURCE_LANE_WIDTH_SAMPLE');return result
        if la.get('status')!='DESCRIPTIVE_RECTANGLE_WITHIN_LANE':
            reasons.append('SOURCE_SAMPLED_LANE_CHECK_FAILED')
        width=float(la['available_halfwidth_m']);lane_halfwidths.append(width)
        if not 0<width<20:reasons.append('INVALID_SOURCE_HALF_LANE_WIDTH')
        raw_margin.append(width-la['required_halfwidth_m'])
        yaw=math.radians(s['yaw_deg_carla']);body_yaws.append(yaw)
        phi=_wrapped_diff(yaw,lane_yaw)
        d=(s['x_m_carla']-lane['x_m'])*nx+(s['y_m_carla']-lane['y_m'])*ny
        # For body-center offsets, use a radius rather than assuming vehicle origin
        # coincides with bounding-box center.
        approx_margin=width-abs(d)-offset-hx*abs(math.sin(phi))-hy*abs(math.cos(phi))-0.10
        independent_margins.append(approx_margin)
        if approx_margin<-1e-5:
            reasons.append('INDEPENDENT_SOURCE_AXIS_SAMPLE_OUTSIDE_LANE')
        if la['required_halfwidth_m']>width+1e-6:
            reasons.append('SOURCE_SAMPLE_NEGATIVE_CLEARANCE')
        if s['frame']>trigger and abs(s['command_steer'])>=0.02:
            positive.append(s)
        if i:
            p=samples[i-1]
            if type(s['frame']) is not int or type(p['frame']) is not int or s['frame']!=p['frame']+1:
                reasons.append('NONCONTIGUOUS_POSE_FRAMES')
            dt=s['sim_time_s']-p['sim_time_s']
            if dt<=0:
                reasons.append('NONMONOTONE_POSE_TIMES')
            yaw_delta=_wrapped_diff(yaw,body_yaws[-2]);yaw_deltas.append(yaw_delta)
            if dt>0:
                mismatch=abs(yaw_delta/dt-s['yaw_rate_radps_carla'])
                yaw_rate_residuals.append(mismatch)
                # CARLA rates are endpoint samples and a 0.05s finite
                # difference is an average, so this is a coarse sanity check,
                # not a numerical identity or calibrated dynamics bound.
                if mismatch>0.12+0.25*abs(s['yaw_rate_radps_carla']):
                    reasons.append('YAW_RATE_AND_HEADING_INCREMENT_INCONSISTENT')
            if abs(yaw_delta)>math.radians(30):
                reasons.append('AMBIGUOUS_INTERSAMPLE_HEADING_ALIAS')
            prev_lateral=(p['x_m_carla']-lane['x_m'])*nx+(p['y_m_carla']-lane['y_m'])*ny
            # Assumes linear vehicle-reference XY and unwrapped yaw interpolation.
            max_abs_lat=max(abs(prev_lateral),abs(d))
            phi_prev=_wrapped_diff(body_yaws[-2],lane_yaw)
            # Unwrap this relative heading across the shortest rotation arc.
            phi_end=phi_prev+yaw_delta
            max_proj=(hx*_max_abs_trig(phi_prev,phi_end,'sin')+
                      hy*_max_abs_trig(phi_prev,phi_end,'cos'))
            interp_margin=min(width,lane_halfwidths[-2])-max_abs_lat-offset-max_proj-0.10
            interp.append({'start_frame':p['frame'],'end_frame':s['frame'],
                           'interpolated_pose_clearance_lower_m':interp_margin})
            if interp_margin<0:
                reasons.append('INTERPOLATED_LANE_WITNESS_HAS_NEGATIVE_MARGIN')
    if max(lane_halfwidths)-min(lane_halfwidths)>0.05:
        reasons.append('SOURCE_LANE_WIDTH_VARIES_ALONG_FIXED_STRAIGHT_AXIS')
    if not positive:reasons.append('NO_POSTTRIGGER_STEERING_EXCITATION')
    if positive and max(abs(s['wheel_steer_deg_front_left_raw']) for s in positive)<0.05:
        reasons.append('NO_ACTUAL_LEFT_FRONT_STEERING')
    if positive and max(abs(s['wheel_steer_deg_front_right_raw']) for s in positive)<0.05:
        reasons.append('NO_ACTUAL_RIGHT_FRONT_STEERING')
    post=[s for s in samples if s['frame']>trigger]
    if not post:
        reasons.append('NO_POSTTRIGGER_SAMPLES');return result
    max_yaw=max(abs(s['yaw_rate_radps_carla']) for s in post)
    yaw_change=abs(_wrapped_diff(body_yaws[-1],body_yaws[samples.index(next(s for s in samples if s['frame']==trigger))])) if any(s['frame']==trigger for s in samples) else 0
    result['max_abs_posttrigger_yaw_rate_radps']=max_yaw
    result['trigger_to_end_heading_change_deg']=math.degrees(yaw_change)
    result['max_abs_front_wheel_steer_deg']=max(max(abs(s['wheel_steer_deg_front_left_raw']),abs(s['wheel_steer_deg_front_right_raw'])) for s in post)
    result['source_sampled_lane_min_margin_m']=min(raw_margin)
    result['independent_source_axis_sampled_min_margin_m']=min(independent_margins)
    result['max_abs_heading_fd_yaw_rate_residual_radps']=max(yaw_rate_residuals) if yaw_rate_residuals else None
    result['interpolated_pose_lane_min_margin_lower_m']=min(x['interpolated_pose_clearance_lower_m'] for x in interp) if interp else None
    result['sample_count']=len(samples)
    result['pose_interval_count']=len(interp)
    if max_yaw<0.003:reasons.append('NO_MEASURABLE_YAW_RATE_RESPONSE')
    if yaw_change<math.radians(0.05):reasons.append('NO_MEASURABLE_NET_HEADING_CHANGE')
    # These positive checks remain descriptive, not certified in continuous time.
    result['reasons']=sorted(set(reasons))
    result['status']=('DESCRIPTIVE_STEER_SAMPLE_AND_INTERPOLATION_WITNESS_NOT_CERTIFIED'
                      if not reasons else 'REVIEW')
    return result
