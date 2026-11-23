"""A68 independent CARLA *diagnostic* repetition audit.

Forbids duplicate JSON keys / NaN, mixed actor physics and changed commands,
requires fresh world times and actor identities in one persistent server session.
This is deliberately NOT an uncertainty-support estimate or physical proof.
"""
from __future__ import annotations
import hashlib,json,math
from .a67_repeat_campaign import review_combined_repeats
from .a67_carla_combined_diagnostics import audit_combined_dynamics


def _unique(pairs):
    out={}
    for k,v in pairs:
        if k in out:raise ValueError('DUPLICATE_JSON_KEY:'+k)
        out[k]=v
    return out


def _parse(raw:bytes):
    if type(raw) is not bytes:raise TypeError('raw bytes required')
    return json.loads(raw.decode('utf8'),object_pairs_hook=_unique,
                      parse_constant=lambda s: (_ for _ in ()).throw(ValueError('INVALID_CONSTANT')))


def audit_physical_repeat_campaign(raw_runs:dict[str,bytes]) -> dict:
    if not isinstance(raw_runs,dict):raise TypeError('run ID -> byte stream required')
    base=review_combined_repeats(raw_runs)
    reasons=[];records=[];source_hashes={}
    for run_id,raw in sorted(raw_runs.items()):
        try:
            obj=_parse(raw)
            if type(obj) is not dict or type(obj.get('trials')) is not list or len(obj['trials'])!=1:
                raise ValueError('EXACTLY_ONE_TRIAL_REQUIRED')
            trial=obj['trials'][0]
            if type(trial) is not dict or trial.get('maneuver')!='combined':
                raise ValueError('WRONG_MANEUVER')
            actor=obj.get('actor_id');tid=trial.get('actor_id')
            if type(actor) is not int or actor<=0 or actor!=tid:
                raise ValueError('ACTOR_IDENTITY_MISMATCH')
            samples=trial.get('samples');trigger=trial.get('trigger_frame')
            if type(samples) is not list or len(samples)!=66 or type(trigger) is not int:
                raise ValueError('INVALID_66_FRAME_CAPTURE')
            frames=[s.get('frame') for s in samples]
            times=[s.get('sim_time_s') for s in samples]
            if any(type(f) is not int for f in frames) or any(b-a!=1 for a,b in zip(frames,frames[1:])):
                raise ValueError('FRAME_GAP_OR_DUPLICATE')
            if any(type(t) not in (int,float) or not math.isfinite(t) for t in times):
                raise ValueError('INVALID_TIME')
            dt=obj.get('step_s')
            if type(dt) not in (int,float) or not 0<dt<1 or any(
                    abs(b-a-dt)>1e-4 for a,b in zip(times,times[1:])):
                raise ValueError('MISSING_OR_WRONG_SIM_TIME_STEP')
            if trigger!=frames[25] or len([s for s in samples if s['frame']>trigger])!=40:
                raise ValueError('TRIGGER_POSITION_NOT_26_PLUS_40')
            post=samples[26:]
            steered=[s for s in post if float(s['command_steer'])>0.025]
            if len(steered)!=3 or [s['frame'] for s in steered]!=list(range(trigger+1,trigger+4)):
                raise ValueError('STEER_NOT_3_FRAME_PULSE')
            if any(not math.isclose(float(s['command_brake']),.45,abs_tol=1e-4) or
                    not math.isclose(float(s['actual_brake']),.45,abs_tol=1e-4) or
                    abs(float(s['actual_steer'])-float(s['command_steer']))>1e-4
                    for s in post):
                raise ValueError('COMMAND_AND_EXECUTED_CONTROL_MISMATCH')
            if not math.isclose(float(trial.get('combined_brake_fraction',-1)),.45,abs_tol=1e-4):
                raise ValueError('BRAKE_PROTOCOL_MISMATCH')
            physics=obj.get('physics')
            if type(physics) is not dict:raise ValueError('MISSING_ACTUAL_ACTOR_PHYSICS')
            stable_physics={k:v for k,v in physics.items() if k not in ('actor_id','capture_frame')}
            cfg=json.dumps(dict(world=obj.get('world_provenance'),physics=stable_physics,
                actor_type=obj.get('actor_type'),step_s=dt,steer_fraction=trial.get('steer_fraction'),
                steer_pulse=trial.get('steer_pulse_s'),brake=trial.get('combined_brake_fraction')),
                sort_keys=True,allow_nan=False)
            diagnostic=audit_combined_dynamics(obj)
            if not diagnostic['diagnostic_repetition_allowed']:
                raise ValueError('COMBINED_DIAGNOSTIC_NOT_ADMITTED')
            records.append(dict(run_id=run_id,actor_id=actor,frame_start=frames[0],frame_end=frames[-1],
                         time_start=times[0],time_end=times[-1],
                         protocol_sha256=hashlib.sha256(cfg.encode()).hexdigest(),
                         peak_reported_deceleration_mps2=diagnostic['reported_max_deceleration_mps2'],
                         peak_yaw_rate_radps=diagnostic['peak_abs_yaw_rate_radps'],
                         torque_only_discrepancy=('GROSS_TORQUE_ONLY_MODEL_DISCREPANCY' in diagnostic['reasons'])))
            source_hashes[run_id]=hashlib.sha256(raw).hexdigest()
        except (TypeError,ValueError,KeyError,IndexError,OverflowError) as ex:
            reasons.append('INVALID_RUN:'+str(run_id)+':'+str(ex))
    if len(records)!=3:reasons.append('REQUIRES_EXACTLY_THREE_VALID_RUNS')
    if len({r['protocol_sha256'] for r in records})!=1:reasons.append('NONUNIFORM_ACTUAL_PHYSICS_OR_PROTOCOL')
    if len({r['actor_id'] for r in records})!=len(records):
        reasons.append('DUPLICATED_ACTOR_IDENTITY_ACROSS_PERSISTENT_SESSION')
    ordered=sorted(records,key=lambda r:r['time_start'])
    if any(a['time_end']>=b['time_start'] or a['frame_end']>=b['frame_start']
           for a,b in zip(ordered,ordered[1:])):
        reasons.append('OVERLAPPING_OR_RESET_SIMULATOR_CLOCKS')
    if base['status']!='DESCRIPTIVE_REPEAT_PROTOCOL_COMPLETE_UNCALIBRATED':
        reasons.append('A67_REPEAT_GATE_NOT_COMPLETE')
    reasons=sorted(set(reasons))
    return dict(schema='rampd.a68.physical_repeat_campaign.v1',
                status=('DESCRIPTIVE_THREE_REPEAT_PROTOCOL_REPRODUCED_MODEL_REVIEW' if not reasons else 'REVIEW'),
                reasons=reasons,runs=records,source_sha256=source_hashes,
                deterministic_response_repeated=base['identical_normalized_responses'],
                all_three_show_torque_only_discrepancy=bool(records) and all(r['torque_only_discrepancy'] for r in records),
                initial_physical_model_conformance_certified=False,
                random_disturbance_support_identified=False,
                safe_vehicle_dynamic_enclosure_available=False,
                carla_sumo_synchronized=False,
                safety_training_labels_allowed=False)
