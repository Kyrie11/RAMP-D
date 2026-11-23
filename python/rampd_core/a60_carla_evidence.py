"""Review CARLA 0.9.16 actor/command-response logs; never issue a certificate.

This is data quality control, not calibration of a *guaranteed* braking,
steering or disturbance bound. Finite repeated trials establish observations
only. Proven bounds need explicit assumptions, uncertainty and held-out tests.
"""
from __future__ import annotations
from collections import Counter
from math import isfinite

SPEEDS = (5, 10, 15)
MANEUVERS = ('brake','steer','combined')
REQUIRED = ('frame','sim_time_s','speed_mps','accel_mps2',
            'yaw_rate_radps_carla','signed_longitudinal_accel_mps2','command_throttle','command_brake',
            'command_steer','x_m_carla','y_m_carla','yaw_deg_carla')


def inspect_trials(document, *, required_repeats=3):
    reasons=[]
    if not isinstance(document,dict) or document.get('schema')!='rampd.carla.a59_1.raw_trials.v1':
        return {'status':'REVIEW','reasons':['WRONG_SCHEMA'],'physical_certified':False}
    if document.get('carla_server_version','').split('-',1)[0]!='0.9.16':
        reasons.append('SERVER_VERSION_NOT_CONFIRMED_0_9_16')
    # CARLA 0.9.16 evidence may come from any map; retain map provenance.
    if not isinstance(document.get('map'),str) or not document['map'].strip():
        reasons.append('MISSING_CARLA_MAP')
    if document.get('actor_type')!='vehicle.tesla.model3' or type(document.get('actor_id')) is not int:
        reasons.append('UNVERIFIED_ACTOR_BLUEPRINT_ID')
    if document.get('world_exclusive_confirmed') is not True:
        reasons.append('EXCLUSIVE_TICK_OWNERSHIP_UNVERIFIED')
    meta=document.get('physics',{})
    if not isinstance(meta,dict) or len(meta.get('wheels',[]))!=4 or not meta.get('bounding_box'):
        reasons.append('MISSING_ACTOR_PHYSICS_OR_GEOMETRY')
    step=document.get('step_s',0.05)
    if type(step) not in (int,float) or not isfinite(step) or not 0<step<=0.05:
        reasons.append('UNVERIFIED_PHYSICS_STEP');step=0.05
    rows=document.get('trials',[])
    if not isinstance(rows,list): rows=[];reasons.append('INVALID_TRIAL_RECORDS')
    buckets=Counter(); observed=[]
    for trial in rows:
        if not isinstance(trial,dict): reasons.append('INVALID_TRIAL'); continue
        key=(trial.get('target_speed_mps'),trial.get('maneuver'))
        if key not in {(v,m) for v in SPEEDS for m in MANEUVERS}:
            reasons.append('UNKNOWN_SPEED_OR_MANEUVER');continue
        buckets[key]+=1
        measurements=trial.get('samples',[])
        if not isinstance(measurements,list) or len(measurements)<12:
            reasons.append('TOO_FEW_SAMPLES:'+str(key));continue
        if trial.get('status')!='CAPTURED' or type(trial.get('trigger_frame')) is not int or type(trial.get('actor_id')) is not int:
            reasons.append('TRIAL_INCOMPLETE:'+str(key))
        prev_frame=None;prev_time=None;captured_trigger=False;post_commands=[]
        for sample in measurements:
            if not isinstance(sample,dict) or any(name not in sample for name in REQUIRED):
                reasons.append('MISSING_SIGNAL:'+str(key));break
            if any(type(sample[name]) not in (int,float) or not isfinite(sample[name]) for name in REQUIRED):
                reasons.append('NONFINITE_OR_INVALID_SIGNAL:'+str(key));break
            frame,time=sample['frame'],sample['sim_time_s']
            if type(frame) is not int or (prev_frame is not None and frame!=prev_frame+1):
                reasons.append('NONCONTIGUOUS_FRAME:'+str(key));break
            if prev_time is not None and abs((time-prev_time)-step) > max(0.0001,step*0.05):
                reasons.append('IRREGULAR_PHYSICS_TIMESTEP:'+str(key));break
            if not 0<=sample['command_throttle']<=1 or not 0<=sample['command_brake']<=1 or not -1<=sample['command_steer']<=1:
                reasons.append('INVALID_APPLIED_COMMAND:'+str(key));break
            captured_trigger |= frame==trial.get('trigger_frame')
            if frame>trial.get('trigger_frame',10**12):post_commands.append(sample)
            prev_frame,prev_time=frame,time
        if not captured_trigger:
            reasons.append('MISSING_TRIGGER_FRAME:'+str(key))
        # Logging a nominal trial name is not evidence a control step was applied.
        if not post_commands or not any(
            (s['command_brake'] >= 0.3 if key[1]=='brake' else
             abs(s['command_steer']) >= .025 and s['command_brake']<.1 if key[1]=='steer' else
             s['command_brake'] >= .2 and abs(s['command_steer']) >= .025)
            for s in post_commands if all(t in s for t in ('command_brake','command_steer'))):
            reasons.append('MISSING_ACTUAL_COMMANDED_EXCITATION:'+str(key))
        if abs(float(trial.get('trigger_speed_mps',-999))-key[0])>1.0:
            reasons.append('TRIGGER_SPEED_NOT_NEAR_TARGET:'+str(key))
        observed.append({'target_speed_mps':key[0],'maneuver':key[1],
                         'samples':len(measurements),'trigger_speed_mps':trial.get('trigger_speed_mps')})
    if document.get('capture_protocol_version') is not None:
        from .a62_carla_readiness import inspect_readiness_log
        gate=inspect_readiness_log(document)
        if gate['status']=='REVIEW':
            reasons.extend('A62_READINESS:'+r for r in gate['reasons'])
    if type(required_repeats) is not int or required_repeats < 1:
        raise ValueError('invalid repeat count')
    for speed in SPEEDS:
        for maneuver in MANEUVERS:
            if buckets[(speed,maneuver)]<required_repeats:
                reasons.append(f'INSUFFICIENT_REPEATS:{speed}:{maneuver}')
    return {'schema':'rampd.carla.a59_1.review.v1',
            'status':'SAMPLED_ACTOR_RESPONSE_LOGS_CAPTURED_UNCALIBRATED' if not reasons else 'REVIEW',
            'reasons':sorted(set(reasons)), 'trial_count':len(rows),
            'expected_trials':len(SPEEDS)*len(MANEUVERS)*required_repeats,
            'observed':observed,
            'physical_certified':False,'guaranteed_braking_lower_bound_available':False,
            'actuator_delay_upper_bound_certified':False,
            'model_error_enclosure_certified':False,
            'note':'Descriptive simulation samples only; no validated continuous-time physics bounds or real vehicle certificate.'}
