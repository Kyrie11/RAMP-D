"""A59/1b-1 readiness checks for CARLA calibration, *not* road safety proofs.

Operate in the horizontal CARLA map plane; never infer driveability from the
nearest projected waypoint alone.  Grounding is a stationary-evidence heuristic,
not a contact or suspension-force measurement.  No output is a safety certificate.
"""
from __future__ import annotations
import math
from collections import deque


def ground_window(samples, *, minimum=5, max_vz=0.08, max_z_range=0.015,
                  max_xy_speed=0.20):
    """Check >=minimum consecutive fresh, stationary, non-falling frames.

    Each sample is (frame, time, x, y, z, vx, vy, vz). Returns (bool, reason).
    """
    if len(samples)<minimum:
        return False, 'INSUFFICIENT_SETTLING_FRAMES'
    tail=list(samples)[-minimum:]
    if any(len(r)!=8 or any(not math.isfinite(float(z)) for z in r) for r in tail):
        return False, 'NONFINITE_SETTLING_SIGNAL'
    if any(type(r[0]) is not int for r in tail):
        return False, 'INVALID_SETTLING_FRAME'
    if any(b[0]!=a[0]+1 or b[1]<=a[1] for a,b in zip(tail,tail[1:])):
        return False, 'NONCONTIGUOUS_SETTLING_FRAMES'
    if any(abs(r[7])>max_vz or math.hypot(r[5],r[6])>max_xy_speed for r in tail):
        return False, 'MOVING_OR_FALLING_AT_SETTLING_GATE'
    if max(r[4] for r in tail)-min(r[4] for r in tail)>max_z_range:
        return False, 'HEIGHT_NOT_STABLE'
    return True, 'DESCRIPTIVE_STATIONARY_HEIGHT_STABLE'


def projected_lane_footprint(x, y, yaw_deg, bbox_center_x, bbox_center_y,
                             bbox_half_length, bbox_half_width,
                             lane_x, lane_y, lane_yaw_deg, lane_width,
                             *, lane_margin=0.10, expected_lane=None, observed_lane=None):
    """Conservative *instantaneous* rectangle lateral extent inside one lane.

    All coordinates are CARLA left-handed map meters and angles are degrees;
    only absolute lateral geometry is used. This is not a swept-footprint proof.
    """
    args=(x,y,yaw_deg,bbox_center_x,bbox_center_y,bbox_half_length,bbox_half_width,
          lane_x,lane_y,lane_yaw_deg,lane_width,lane_margin)
    if any(not isinstance(z,(float,int)) or not math.isfinite(z) for z in args):
        return {'status':'REVIEW','reason':'INVALID_LANE_GEOMETRY'}
    if bbox_half_length<=0 or bbox_half_width<=0 or lane_width<=0 or lane_margin<0:
        return {'status':'REVIEW','reason':'INVALID_LANE_GEOMETRY'}
    if expected_lane is not None and observed_lane!=expected_lane:
        return {'status':'REVIEW','reason':'LANE_IDENTITY_CHANGED',
                'expected_lane':expected_lane,'observed_lane':observed_lane}
    yaw=math.radians(yaw_deg); lane_yaw=math.radians(lane_yaw_deg)
    cx=x+math.cos(yaw)*bbox_center_x-math.sin(yaw)*bbox_center_y
    cy=y+math.sin(yaw)*bbox_center_x+math.cos(yaw)*bbox_center_y
    lateral=-(cx-lane_x)*math.sin(lane_yaw)+(cy-lane_y)*math.cos(lane_yaw)
    delta=yaw-lane_yaw
    lateral_extent=abs(math.sin(delta))*bbox_half_length+abs(math.cos(delta))*bbox_half_width
    used=abs(lateral)+lateral_extent+lane_margin
    ok=used<=lane_width/2
    return {'status':'DESCRIPTIVE_RECTANGLE_WITHIN_LANE' if ok else 'REVIEW',
            'reason':'APPROX_INSTANTANEOUS_LANE_ENVELOPE' if ok else 'LANE_RECTANGLE_EXCEEDS_WIDTH',
            'lateral_offset_m':lateral,'projected_halfwidth_m':lateral_extent,
            'required_halfwidth_m':used,'available_halfwidth_m':lane_width/2,
            'safety_certified':False}


def inspect_readiness_log(doc):
    """Fail-closed offline diagnostic for read-only post-run review."""
    if not isinstance(doc,dict):
        return {'status':'REVIEW','reasons':['INVALID_JSON_ROOT'],'physical_certified':False}
    reasons=[]
    for trial in doc.get('trials',[]):
        if not isinstance(trial,dict):
            reasons.append('INVALID_TRIAL');continue
        s=trial.get('settling',{})
        if not isinstance(s,dict) or s.get('status')!='DESCRIPTIVE_STATIONARY_HEIGHT_STABLE':
            reasons.append('MISSING_STATIONARY_HEIGHT_GATE')
        elif s.get('ground_height_proxy',{}).get('status')!='DESCRIPTIVE_WHEEL_HEIGHT_NEAR_ROAD':
            reasons.append('MISSING_WHEEL_ROAD_HEIGHT_PROXY')
        if trial.get('status')=='CAPTURED':
            samples=trial.get('samples',[])
            if not samples or not any(z.get('planar_speed_mps',-1)>=0 for z in samples):
                reasons.append('MISSING_PLANAR_SPEED_CHANNEL')
            if any(x.get('lane_audit',{}).get('status')!='DESCRIPTIVE_RECTANGLE_WITHIN_LANE'
                   for x in samples):
                reasons.append('INCOMPLETE_INSTANTANEOUS_LANE_AUDIT')
            if trial.get('maneuver') in ('steer','combined'):
                if not any(abs(x.get('command_steer',0))>=0.025 and
                           x.get('wheel_steer_deg_front_left_raw') is not None and
                           x.get('wheel_steer_deg_front_right_raw') is not None
                           for x in samples):
                    reasons.append('NO_VALID_STEER_EXCITATION_WITH_WHEEL_FEEDBACK')
        elif trial.get('status')!='DESCRIPTIVE_PRETRIAL_READY_NOT_CALIBRATED':
            reasons.append('INCOMPLETE_TRIAL:'+str(trial.get('status')))
    if not doc.get('trials'):
        reasons.append('NO_TRIALS')
    if doc.get('capture_protocol_version')!='a62_grounding_lane_v1':
        reasons.append('UNVERIFIED_CAPTURE_PROTOCOL_VERSION')
    return {'status':'DESCRIPTIVE_PRETRIAL_EVIDENCE_COMPLETE_NOT_CERTIFIED' if not reasons else 'REVIEW',
            'reasons':sorted(set(reasons)),'trial_count':len(doc.get('trials',[])),
            'physical_certified':False,'actuator_calibrated':False,
            'scope':'Only per-frame sample and stable-height quality, not tire contact, continuous lane safety, or physical error bounds'}


def wheel_road_height_proxy(wheels, body_xyz, road_heights, *, tolerance_above=0.18,
                            tolerance_below=0.18):
    """Descriptive CARLA wheel-bottom vs local mapped road-height comparison.

    CARLA 0.9.16 evidence is *hypothesized* world coordinates in centimeters.
    We only use that convention if independent body/wheel XY proximity checks
    agree. It is not a tire contact-force or real-road-friction measurement.
    """
    if len(wheels)!=4 or len(road_heights)!=4:
        return {'status':'REVIEW','reason':'INCOMPLETE_WHEEL_OR_ROAD_HEIGHT'}
    clearances=[]
    for w,h in zip(wheels,road_heights):
        try:
            wx,wy,wz=(float(w.position.x)/100,float(w.position.y)/100,float(w.position.z)/100)
            radius=float(w.radius)/100
            height=float(h)
            if not all(map(math.isfinite,(wx,wy,wz,radius,height))) or not 0.2<=radius<=1:
                raise ValueError()
            if math.hypot(wx-body_xyz[0],wy-body_xyz[1])>6:
                return {'status':'REVIEW','reason':'WHEEL_COORDINATE_FRAME_UNVERIFIED'}
            clearances.append(wz-radius-height)
        except (AttributeError,ValueError,TypeError):
            return {'status':'REVIEW','reason':'INVALID_WHEEL_HEIGHT_SIGNAL'}
    ok=all(-tolerance_below<=c<=tolerance_above for c in clearances)
    return {'status':'DESCRIPTIVE_WHEEL_HEIGHT_NEAR_ROAD' if ok else 'REVIEW',
            'reason':'ROAD_HEIGHT_PROXY_CONSISTENT' if ok else 'WHEEL_HEIGHT_ABOVE_OR_BELOW_ROAD',
            'wheel_bottom_to_road_m':clearances,'physical_contact_certified':False}
