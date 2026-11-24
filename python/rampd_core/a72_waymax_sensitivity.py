"""Re-evaluate lookahead ablations of an official IDM on synthetic actors.

Waymax's tf.Example path loads a *template* for this probe, not a WOMD factual
or interactive recording; different hyperparameter outputs are NOT real
WOMD counterfactual samples.
"""
from __future__ import annotations
import hashlib,json
from .a71_waymax_counterfactual_audit import audit_waymax_idm_pair


def audit_waymax_lookahead(records):
    reasons=[];rows=[];settings=[]
    if type(records) is not dict or len(records)<2:reasons.append('NEED_AT_LEAST_TWO_LOOKAHEAD_ARMS')
    for name,doc in sorted(records.items()):
        if type(doc) is not dict:
            reasons.append('BAD_REPORT:'+str(name));continue
        r=audit_waymax_idm_pair(doc)
        if r['reasons']:reasons.append('WAYMAX_OFFICIAL_IDM_AUDIT_FAILED:'+str(name))
        look=doc.get('lookahead_points')
        if type(look) is not int or not 1<=look<=300 or str(look)!=str(name):
            reasons.append('LOOKAHEAD_ARM_MISLABELED:'+str(name))
        settings.append(tuple((k,doc.get(k)) for k in ('steps','dt_s','scope','ego_length_m',
                            'follower_length_m','initial_center_offset_m','ego_control_profile',
                            'idm_source_sha256','waymax','real_scene_used')))
        rows.append(dict(lookahead_points=look,
           first_measured_idm_accel_mps2=doc.get('initial_measured_idm_accel_mps2'),
           min_sampled_bumper_gap_m=r['measurements'].get('minimum_sampled_bumper_gap_m'),
           follower_response_delta_mps=r['measurements'].get('follower_speed_intervention_difference_mps'),
           original_report_digest=hashlib.sha256(json.dumps(doc,sort_keys=True,allow_nan=False).encode()).hexdigest()))
    if len(set(settings))>1:reasons.append('CONFOUNDED_HYPERPARAMETER_ARMS')
    if len({r['lookahead_points'] for r in rows})!=len(rows):reasons.append('DUPLICATE_LOOKAHEAD_LEVEL')
    return dict(schema='rampd.a72.waymax.synthetic_idm_lookahead.v1',
       status='DESCRIPTIVE_SYNTHETIC_IDM_SENSITIVITY_ONLY' if not reasons else 'REVIEW',
       reasons=sorted(set(reasons)),rows=rows,
       tfe_file_used_as_template_not_factual_actor_response=True,
       sample_provenance_from_tfrecord_not_recorded=True,
       real_womd_scenario_behavior_validated=False,curved_route_response_verified=False,
       continuous_collision_free_verified=False,physical_hard_support_verified=False,
       safe_training_labels_allowed=False)
