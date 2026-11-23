"""A67 repeated CARLA combined-control *diagnostics*, never statistical safety bounds.

Independent raw trace files and one fixed intervention protocol are mandatory.
Three identical physics runs do not establish an uncertainty set or domain shift.
"""
from __future__ import annotations
import hashlib,json,math
from .a67_carla_combined_diagnostics import audit_combined_dynamics


def review_combined_repeats(raw_runs:dict[str,bytes], *, required:int=3) -> dict:
    if type(required) is not int or not 2<=required<=20:
        raise ValueError('required run count must be 2..20')
    reasons=[];rows=[];signatures=[];summaries=[];hashes=[]
    if not isinstance(raw_runs,dict) or not raw_runs:
        reasons.append('EMPTY_REPEAT_CAMPAIGN');raw_runs={}
    for run_id,raw in raw_runs.items():
        if not isinstance(run_id,str) or not run_id or not isinstance(raw,bytes):
            reasons.append('MALFORMED_RUN_ID_OR_RAW_BYTES');continue
        digest=hashlib.sha256(raw).hexdigest()
        if digest in hashes:reasons.append('DUPLICATE_RAW_EVIDENCE_BYTES')
        hashes.append(digest)
        try:
            doc=json.loads(raw)
        except (ValueError,TypeError,UnicodeError):
            reasons.append('UNREADABLE_RAW_JSON:'+run_id);continue
        if not isinstance(doc,dict):
            reasons.append('NONOBJECT_RAW_JSON:'+run_id);continue
        try:
            review=audit_combined_dynamics(doc)
        except (ValueError,TypeError,KeyError,IndexError) as exc:
            reasons.append('MALFORMED_RUN_REVIEW:'+run_id+':'+type(exc).__name__);continue
        if not review['diagnostic_repetition_allowed']:
            reasons.append('RUN_NOT_CAPTURED_FOR_DIAGNOSTICS:'+run_id)
        if not isinstance(doc.get('trials'),list) or len(doc['trials'])!=1 or not isinstance(doc['trials'][0],dict):
            reasons.append('NOT_ONE_COMBINED_RUN:'+run_id);continue
        trial=doc['trials'][0];trigger=trial.get('trigger_frame')
        if type(trigger) is not int or not isinstance(trial.get('samples'),list) or any(not isinstance(s,dict) for s in trial['samples']):
            reasons.append('MALFORMED_RUN_FRAME_DATA:'+run_id);continue
        post=[s for s in trial['samples'] if type(s.get('frame')) is int and s['frame']>trigger]
        if not post:
            reasons.append('MISSING_POSTCONTROL_TRACE:'+run_id);continue
        if any(not all(type(s.get(k)) in (int,float) and math.isfinite(s[k]) for k in
                       ('command_brake','planar_speed_mps','yaw_rate_radps_carla','signed_longitudinal_accel_mps2')) for s in post):
            reasons.append('INVALID_POSTCONTROL_NUMERIC_DATA:'+run_id);continue
        brake=round(max(s['command_brake'] for s in post),5)
        protocol=(doc.get('carla_server_version'),doc.get('map'),
                  (doc.get('world_provenance') or {}).get('opendrive_sha256'),
                  json.dumps((doc.get('world_provenance') or {}).get('settings'),sort_keys=True),
                  json.dumps((doc.get('world_provenance') or {}).get('weather_raw'),sort_keys=True),
                  doc.get('actor_type'),doc.get('step_s'),trial.get('target_speed_mps'),
                  round(trial.get('steer_fraction',0),5),round(trial.get('steer_pulse_s',0),5),brake,
                  json.dumps([w.get('tire_friction_raw') for w in (doc.get('physics') or {}).get('wheels',[])],sort_keys=True))
        signatures.append(protocol)
        # Normalized physical response, deliberately excludes global frame,
        # actor id and world simulation time. Identical repeats cannot claim
        # a stochastic uncertainty bound or a robust error interval.
        response=tuple((round(s['planar_speed_mps'],5),
                        round(s['yaw_rate_radps_carla'],5),
                        round(s['signed_longitudinal_accel_mps2'],4)) for s in post)
        summaries.append(response)
        rows.append({'run_id':run_id,'raw_sha256':digest,'capture_status':review['capture_status'],
                     'diagnostic_repetition_allowed':review['diagnostic_repetition_allowed'],
                     'reported_max_deceleration_mps2':review.get('reported_max_deceleration_mps2'),
                     'peak_abs_yaw_rate_radps':review.get('peak_abs_yaw_rate_radps'),
                     'gross_torque_model_discrepancy':('GROSS_TORQUE_ONLY_MODEL_DISCREPANCY' in review['reasons'])})
    if len(rows)<required:reasons.append('INSUFFICIENT_VALID_REPEAT_ATTEMPTS')
    if len(set(signatures))>1:reasons.append('CHANGED_EXPERIMENT_PROTOCOL_ACROSS_REPEATS')
    if len(rows)!=len(raw_runs):reasons.append('UNREVIEWED_OR_INVALID_RUNS')
    degenerate=(len(summaries)>=required and len(set(summaries))==1)
    if degenerate:reasons.append('IDENTICAL_RESPONSES_DO_NOT_ESTABLISH_UNCERTAINTY_SUPPORT')
    reasons=sorted(set(reasons))
    complete=(len(rows)>=required and len(rows)==len(raw_runs) and
              not any(r for r in reasons if r!='IDENTICAL_RESPONSES_DO_NOT_ESTABLISH_UNCERTAINTY_SUPPORT'))
    return dict(schema='rampd.a67.combined_repeat_audit.v1',
                status=('DESCRIPTIVE_REPEAT_PROTOCOL_COMPLETE_UNCALIBRATED' if complete else 'REVIEW'),
                reasons=reasons,required_runs=required,received_runs=len(raw_runs),
                accepted_diagnostic_runs=sum(x['diagnostic_repetition_allowed'] for x in rows),
                uniform_protocol=len(set(signatures))==1 and bool(signatures),
                identical_normalized_responses=degenerate,rows=rows,
                empirical_variability_is_robust_bound=False,
                domain_shift_covered=False,real_vehicle_model_validated=False,
                safe_training_labels_allowed=False)
