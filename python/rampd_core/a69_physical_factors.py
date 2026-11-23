"""A69 fail-closed one-factor CARLA brake sweep comparator (diagnostic only).

Only brake magnitude may change. Fixed map, actor physics, weather, time step,
steering pulse and initial speed are required; no inference of a physical bound.
"""
from __future__ import annotations
import hashlib,json,math
from collections import defaultdict
from .a67_carla_combined_diagnostics import audit_combined_dynamics

def _pairs(pairs):
    out={}
    for k,v in pairs:
        if k in out:raise ValueError('DUPLICATE_JSON_KEY')
        out[k]=v
    return out

def _parse(raw):
    if type(raw) is not bytes:raise TypeError('raw bytes required')
    return json.loads(raw.decode('utf8'),object_pairs_hook=_pairs,
             parse_constant=lambda x: (_ for _ in ()).throw(ValueError('NONFINITE_JSON')))

def audit_brake_sweep(raw_runs:dict[str,bytes], *, levels=(.15,.30,.45),
                      min_repeats_per_level=1)->dict:
    if not isinstance(raw_runs,dict):raise TypeError('run mapping required')
    if type(min_repeats_per_level) is not int or not 1<=min_repeats_per_level<=20:
        raise ValueError('invalid minimum repeats')
    if len(set(levels))!=len(levels) or any(type(x) not in (int,float) or not math.isfinite(x)
             or not .05<=x<=.8 for x in levels):raise ValueError('invalid levels')
    issues=[];rows=[];configs=set();raw_hashes=set();counters=defaultdict(int);trigger_speeds=[]
    for key,raw in sorted(raw_runs.items()):
        if not isinstance(key,str) or not key:issues.append('INVALID_RUN_ID');continue
        try:
            digest=hashlib.sha256(raw).hexdigest()
            if digest in raw_hashes:issues.append('DUPLICATE_RAW_SOURCE')
            raw_hashes.add(digest)
            d=_parse(raw)
            if type(d) is not dict or type(d.get('trials')) is not list or len(d['trials'])!=1:
                raise ValueError('EXACTLY_ONE_TRIAL_REQUIRED')
            t=d['trials'][0]
            if type(t) is not dict or t.get('maneuver')!='combined' or t.get('status')!='CAPTURED':
                raise ValueError('INVALID_MANEUVER_OR_STATUS')
            declared=t.get('combined_brake_fraction')
            if type(declared) not in (int,float) or not math.isfinite(declared):
                raise ValueError('NEW_SWEEP_NEEDS_EXPLICIT_BRAKE_DECLARATION')
            matched=[a for a in levels if abs(a-declared)<1e-5]
            if len(matched)!=1:raise ValueError('UNEXPECTED_BRAKE_LEVEL')
            level=matched[0]
            # First audit actual intervention, independently of the legacy
            # combined diagnostic; otherwise a specific command mismatch can
            # disappear behind a generic upstream REVIEW.
            samples=t.get('samples')
            if not isinstance(samples,list):raise ValueError('MISSING_SAMPLES')
            trigger_samples=[s for s in samples if type(s.get('frame')) is int and
                             s['frame']==t.get('trigger_frame')]
            if len(trigger_samples)!=1 or type(trigger_samples[0].get('planar_speed_mps')) not in (int,float):
                raise ValueError('MISSING_TRIGGER_SPEED')
            realized_speed=trigger_samples[0]['planar_speed_mps']
            if (not math.isfinite(realized_speed) or
                    abs(realized_speed-t.get('target_speed_mps',float('inf')))>0.5):
                raise ValueError('TRIGGER_SPEED_MISMATCH')
            trigger_speeds.append(realized_speed)
            post=[s for s in samples if type(s.get('frame')) is int and s['frame']>t.get('trigger_frame',-1)]
            if len(post)!=40 or any(abs(s['command_brake']-level)>1e-4 or
                    abs(s['actual_brake']-level)>1e-4 for s in post):
                raise ValueError('BRAKE_COMMAND_OR_ACTUAL_MISMATCH')
            if any(abs(s['actual_steer']-s['command_steer'])>1e-4 for s in post):
                raise ValueError('ACTUAL_STEER_MISMATCH')
            diag=audit_combined_dynamics(d)
            if not diag['diagnostic_repetition_allowed']:
                raise ValueError('SINGLE_CONTROL_DIAGNOSTIC_FAILED')
            if diag['combined_brake_profile_source']!='DECLARED_INTERVENTION':
                raise ValueError('BRAKE_PROFILE_NOT_EXPLICIT')
            if type(d.get('physics')) is not dict or type(d.get('world_provenance')) is not dict:
                raise ValueError('MISSING_EXPERIMENT_CONFIGURATION')
            # Remove only explicitly actor-instance-specific metadata. Unknown
            # physics fields stay in protocol comparison to avoid confounding.
            physics={k:v for k,v in d['physics'].items() if k not in ('actor_id','capture_frame')}
            cfg=dict(map=d.get('map'),carla_version=d.get('carla_server_version'),
                actor_type=d.get('actor_type'),physics=physics,world=d['world_provenance'],
                dt=d.get('step_s'),site=(d.get('site_audit') or {}).get('chosen_waypoint'),
                steer=t.get('steer_fraction'),pulse=t.get('steer_pulse_s'),
                speed=t.get('target_speed_mps'),control_maneuver=t.get('maneuver'))
            configs.add(hashlib.sha256(json.dumps(cfg,sort_keys=True,allow_nan=False).encode()).hexdigest())
            counters[level]+=1
            rows.append(dict(run_id=key,level=level,sha256=digest,
                realized_trigger_speed_mps=realized_speed,
                max_reported_decel_mps2=diag['reported_max_deceleration_mps2'],
                max_fd_decel_mps2=diag['max_speed_difference_deceleration_mps2'],
                max_yaw_radps=diag['peak_abs_yaw_rate_radps'],
                model_discrepancy='GROSS_TORQUE_ONLY_MODEL_DISCREPANCY' in diag['reasons']))
        except (TypeError,ValueError,KeyError,IndexError,OverflowError) as exc:
            issues.append('INVALID_ARM:'+key+':'+str(exc))
    if len(configs)!=1:issues.append('NONBRAKE_EXPERIMENT_FACTOR_CHANGED_OR_EMPTY')
    if trigger_speeds and max(trigger_speeds)-min(trigger_speeds)>0.3:
        issues.append('TRIGGER_SPEED_NOT_MATCHED_ACROSS_BRAKE_ARMS')
    for x in levels:
        if counters[x]<min_repeats_per_level:
            issues.append('MISSING_ARM_OR_REPEATS:'+str(x))
    if not rows:issues.append('NO_VALID_CONTROL_TRIALS')
    means={str(a):(sum(r['max_reported_decel_mps2'] for r in rows if r['level']==a)/counters[a]
                    if counters[a] else None) for a in levels}
    issues=sorted(set(issues))
    return dict(schema='rampd.a69.brake_sweep.v1',
        status='DESCRIPTIVE_ONE_FACTOR_SWEEP_COMPLETE_MODEL_REVIEW' if not issues else 'REVIEW',
        reasons=issues,number_of_runs=len(raw_runs),accepted_runs=len(rows),
        brake_levels=[float(x) for x in levels],runs_per_level={str(x):counters[x] for x in levels},
        mean_peak_reported_deceleration_by_level_mps2=means,rows=rows,
        only_brake_changed_in_declared_protocol=(len(configs)==1),
        physical_response_function_identified=False,
        actuator_delay_certified=False,physical_error_support_certified=False,
        safe_training_labels_allowed=False)
