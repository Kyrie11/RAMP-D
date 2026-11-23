"""A67 test: real user combined trace + corruption and false-certificate attacks."""
from __future__ import annotations
import copy,hashlib,json
from fractions import Fraction as Q
from pathlib import Path
from rampd_core.a67_carla_combined_diagnostics import audit_combined_dynamics
from rampd_core.a67_artifact_bytes_binding import audit_payload_bytes
from rampd_core.a61_hybrid_partition import AtomicClockSlab,HybridClockGate
from rampd_core.a62_hybrid_obligation_ledger import WorldSlabEvidence
from rampd_core.a64_hybrid_handoff import SlabHandoff
from rampd_core.a66_hybrid_contract_binding import WorldSlabBinding

_FIX=Path(__file__).parent/'fixtures'/'a67_town06_combined_raw.json'
def source():return json.loads(_FIX.read_text())

def test_real_combined_is_valid_diagnostic_but_not_calibrated():
    r=audit_combined_dynamics(source())
    assert r['status']=='DIAGNOSTIC_REPEAT_ELIGIBLE_MODEL_REVIEW_NOT_CALIBRATED'
    assert r['captured'] and r['sampled_lane_witness']
    assert r['simultaneous_command_frames']==3
    assert 26<r['reported_max_deceleration_mps2']<28
    assert 6<r['reported_to_full_command_torque_ratio']<7
    assert 14<r['reported_to_brake_scaled_torque_ratio']<15
    assert 'GROSS_TORQUE_ONLY_MODEL_DISCREPANCY' in r['reasons']
    assert not r['verified_uncertainty_enclosure']
    assert not r['safety_training_labels_allowed']

def test_no_combined_substitution_by_steering():
    x=source();x['trials'][0]['maneuver']='steer'
    assert 'COMBINED_MANEUVER_REQUIRED' in audit_combined_dynamics(x)['reasons']

def test_steering_without_brake_rejected():
    x=source()
    for s in x['trials'][0]['samples']:
        if s['frame']>x['trials'][0]['trigger_frame']:
            s['command_brake']=0;s['actual_brake']=0
    r=audit_combined_dynamics(x)
    assert not r['diagnostic_repetition_allowed']

def test_brake_without_wheel_steering_rejected():
    x=source()
    for s in x['trials'][0]['samples']:
        s['wheel_steer_deg_front_left_raw']=0
        s['wheel_steer_deg_front_right_raw']=0
    assert not audit_combined_dynamics(x)['diagnostic_repetition_allowed']

def test_fake_physics_mass_rejected():
    x=source();x['physics']['mass_kg_raw']=-5
    assert 'NO_ACTOR_MASS_AND_FOUR_WHEEL_PARAMETERS' in audit_combined_dynamics(x)['reasons']

def test_lateral_escape_cannot_be_explained_by_good_capture_count():
    x=source();x['trials'][0]['samples'][34]['y_m_carla']-=4
    assert not audit_combined_dynamics(x)['diagnostic_repetition_allowed']

def test_missing_sample_or_infinite_signal_not_promoted():
    x=source();x['trials'][0]['samples'][31]['signed_longitudinal_accel_mps2']=float('nan')
    assert 'INCOMPLETE_POSTCONTROL_SIGNALS' in audit_combined_dynamics(x)['reasons']

def _context():
    a,b=Q(0),Q(1)
    ids=('hidden1','hidden2')
    gate=HybridClockGate('CONDITIONAL_EXACT_MODEL_HYBRID_PARTITION_READY',(),
         (AtomicClockSlab(a,b,(),()),), (((),ids),), ((a,b,(((),ids),)),),False)
    protocol=json.dumps(dict(schema='rampd.a67.protocol_contract.v1',contract_id='v0'),sort_keys=True).encode()
    pd=hashlib.sha256(protocol).hexdigest()
    rolebytes={};led=[];hnd=[];bnd=[]
    for w in ids:
        dig=[]
        for role in ('native_tube','guard','resource','observation'):
            raw=json.dumps(dict(schema='rampd.a67.context_artifact.v1',
                world_id=w,start=str(a),end=str(b),public_control_id='u',role=role,
                body={'declare_only':True}),sort_keys=True).encode()
            rolebytes[(w,a,b,role)]=raw
            dig.append(hashlib.sha256(raw).hexdigest())
        led.append(WorldSlabEvidence(w,a,b,'u',*dig))
        hnd.append(SlabHandoff(w,a,b,((a,b),),((a,b),),dig[0]))
        bnd.append(WorldSlabBinding(w,a,b,'u',pd,*dig))
    return gate,tuple(led),tuple(hnd),tuple(bnd),protocol,rolebytes

def test_payload_bytes_verify_but_never_proof():
    gate,led,hnd,bnd,protocol,data=_context()
    r=audit_payload_bytes(gate,led,hnd,bnd,protocol_bytes=protocol,role_bytes=data)
    assert r['status']=='CONDITIONAL_CONTEXT_BYTES_BOUND_NOT_REPLAYED'
    assert r['verified_role_artifacts']==8 and r['all_declared_artifact_hashes_verified']
    assert not r['native_picard_replayed'] and not r['sc_certified']

def test_payload_bytes_rejects_same_digest_string_but_missing_file_bytes():
    gate,led,hnd,bnd,protocol,data=_context()
    data.pop(next(iter(data)))
    assert audit_payload_bytes(gate,led,hnd,bnd,protocol_bytes=protocol,role_bytes=data)['status']=='UNKNOWN'

def test_payload_bytes_rejects_context_swapped_even_if_hash_rewritten():
    gate,led,hnd,bnd,protocol,data=_context()
    key=next(iter(data))
    old=data[key];p=json.loads(old);p['world_id']='different'
    data[key]=json.dumps(p,sort_keys=True).encode()
    assert 'ROLE_WORLD_TIME_CONTROL_CONTEXT_MISMATCH' in ' '.join(
        audit_payload_bytes(gate,led,hnd,bnd,protocol_bytes=protocol,role_bytes=data)['reasons'])

def test_payload_bytes_rejects_digest_mismatch():
    gate,led,hnd,bnd,protocol,data=_context()
    key=next(iter(data));data[key]=data[key]+b' '
    assert 'DECLARED_SHA256_NOT_ACTUAL_BYTES_SHA256' in ' '.join(audit_payload_bytes(
        gate,led,hnd,bnd,protocol_bytes=protocol,role_bytes=data)['reasons'])

def test_payload_bytes_rejects_duplicate_json_key():
    gate,led,hnd,bnd,protocol,data=_context()
    key=next(iter(data));data[key]=data[key][:-1]+b',"role":"native_tube"}'
    assert 'DUPLICATE_JSON_KEY' in ' '.join(audit_payload_bytes(
        gate,led,hnd,bnd,protocol_bytes=protocol,role_bytes=data)['reasons'])

def test_payload_bytes_rejects_missing_protocol_content():
    gate,led,hnd,bnd,protocol,data=_context()
    assert 'MISSING_PROTOCOL_BYTES' in audit_payload_bytes(
        gate,led,hnd,bnd,protocol_bytes=None,role_bytes=data)['reasons']

def test_payload_bytes_rejects_nonexact_clock_serialization():
    gate,led,hnd,bnd,protocol,data=_context()
    key=next(iter(data));p=json.loads(data[key]);p['end']='1.0'
    data[key]=json.dumps(p,sort_keys=True).encode()
    assert 'ROLE_WORLD_TIME_CONTROL_CONTEXT_MISMATCH' in ' '.join(audit_payload_bytes(
        gate,led,hnd,bnd,protocol_bytes=protocol,role_bytes=data)['reasons'])

def test_repeat_single_run_insufficient():
    from rampd_core.a67_repeat_campaign import review_combined_repeats
    r=review_combined_repeats({'first':_FIX.read_bytes()})
    assert 'INSUFFICIENT_VALID_REPEAT_ATTEMPTS' in r['reasons']
    assert not r['safe_training_labels_allowed']

def test_repeat_identical_raw_files_rejected():
    from rampd_core.a67_repeat_campaign import review_combined_repeats
    raw=_FIX.read_bytes()
    r=review_combined_repeats({'one':raw,'two':raw,'three':raw})
    assert 'DUPLICATE_RAW_EVIDENCE_BYTES' in r['reasons']
    assert r['status']=='REVIEW'

def test_repeat_distinct_frame_ids_but_identical_response_not_uncertainty():
    from rampd_core.a67_repeat_campaign import review_combined_repeats
    base=source();runs={}
    for k in range(3):
        d=copy.deepcopy(base)
        d['actor_id']+=10*k;d['trials'][0]['actor_id']+=10*k
        for s in d['trials'][0]['samples']:
            s['frame']+=100*k;s['sim_time_s']+=500*k
            s['command_reference_sim_time_s']+=500*k
        d['trials'][0]['trigger_frame']+=100*k
        runs[str(k)]=json.dumps(d).encode()
    r=review_combined_repeats(runs)
    assert r['status']=='DESCRIPTIVE_REPEAT_PROTOCOL_COMPLETE_UNCALIBRATED'
    assert r['identical_normalized_responses']
    assert not r['empirical_variability_is_robust_bound']

def test_repeat_changed_braking_profile_not_pooled():
    from rampd_core.a67_repeat_campaign import review_combined_repeats
    base=source();runs={}
    for k in range(3):
        d=copy.deepcopy(base)
        d['actor_id']+=10*k;d['trials'][0]['actor_id']+=10*k
        for s in d['trials'][0]['samples']:
            s['frame']+=100*k;s['sim_time_s']+=500*k
            s['command_reference_sim_time_s']+=500*k
            if k==2 and s['frame']>d['trials'][0]['trigger_frame']+100*k:
                s['command_brake']=.2;s['actual_brake']=.2
        d['trials'][0]['trigger_frame']+=100*k
        runs[str(k)]=json.dumps(d).encode()
    r=review_combined_repeats(runs)
    assert 'CHANGED_EXPERIMENT_PROTOCOL_ACROSS_REPEATS' in r['reasons']
    assert r['status']=='REVIEW'
