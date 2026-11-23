"""A66: explicit partial CARLA evidence inventory; never mints safety labels.

Missing trials stay MISSING. A steering trial cannot substitute for combined
brake+steering just because both use the same vehicle and speed.
"""
from __future__ import annotations
import hashlib
import json
from .a64_carla_smoke_evidence import audit_single_control_smoke
from .a65_carla_conformance import audit_brake_conformance
from .a66_carla_lateral_witness import audit_steering_lane_witness


def inventory_single_control_inputs(rows:dict[str,dict|None]) -> dict:
    expected={'brake','steer','combined'}
    if not isinstance(rows,dict) or set(rows)!=expected:
        raise ValueError('explicit brake, steer, combined keys required, None for missing')
    out={}
    for kind in ('brake','steer','combined'):
        raw=rows[kind]
        if raw is None:
            out[kind]={'status':'MISSING','raw_sha256':None,'descriptive_capture':False,
                       'physical_certified':False,'safe_training_labels_allowed':False}
            continue
        if not isinstance(raw,dict):
            out[kind]={'status':'REVIEW','reasons':['MALFORMED_INPUT'],
                       'physical_certified':False,'safe_training_labels_allowed':False}
            continue
        digest=hashlib.sha256(json.dumps(raw,sort_keys=True,ensure_ascii=False,
                              separators=(',',':'),allow_nan=False).encode()).hexdigest()
        trial=raw.get('trials')
        declared=trial[0].get('maneuver') if isinstance(trial,list) and len(trial)==1 and isinstance(trial[0],dict) else None
        review=audit_single_control_smoke(raw)
        if declared!=kind:
            reasons=['WRONG_CONTROL_KIND_FOR_INVENTORY_SLOT']
            status='REVIEW'
        else:
            reasons=list(review['reasons'])
            if kind=='brake':
                check=audit_brake_conformance(raw)
                reasons.extend(check['reasons'])
                status='DESCRIPTIVE_BRAKE_TRACE_RECORDED_MODEL_CONFORMANCE_REVIEW' if reasons else 'DESCRIPTIVE_BRAKE_CAPTURED_NOT_CERTIFIED'
            else:
                check=audit_steering_lane_witness(raw)
                reasons.extend(check['reasons'])
                status='DESCRIPTIVE_LATERAL_INTERPOLATION_WITNESS_NOT_CERTIFIED' if not reasons else 'REVIEW'
        out[kind]={'status':status,'reasons':sorted(set(reasons)),
                   'raw_content_digest_sha256':digest,
                   'descriptive_capture':review['status']=='DESCRIPTIVE_SINGLE_CONTROL_SMOKE_CAPTURED_NOT_CALIBRATED',
                   'physical_certified':False,'safe_training_labels_allowed':False}
    return {'schema':'rampd.a66.carla.control_evidence_inventory.v1',
            'status':'PARTIAL_NONCERTIFYING_EVIDENCE',
            'trials':out,'all_three_control_cases_present':all(v['status']!='MISSING' for v in out.values()),
            'continuous_lane_safety_certified':False,
            'effective_actuator_envelope_calibrated':False,
            'carla_sumo_joint_simulation_validated':False,
            'all_eight_supervision_sources_certified':False}
