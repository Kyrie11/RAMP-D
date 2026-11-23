"""Independent A66 coverage: genuine steer evidence + mutation-based rejection."""
import copy
import hashlib
import json
from fractions import Fraction as Q
from pathlib import Path
import pytest
from rampd_core.a66_carla_lateral_witness import audit_steering_lane_witness, _max_abs_trig
from rampd_core.a66_hybrid_contract_binding import WorldSlabBinding, audit_hybrid_artifact_binding
from rampd_core.a61_hybrid_partition import AtomicClockSlab,HybridClockGate
from rampd_core.a62_hybrid_obligation_ledger import WorldSlabEvidence
from rampd_core.a64_hybrid_handoff import SlabHandoff

_FIX=Path(__file__).parent/'fixtures'/'a66_town06_steer_raw.json'

def source():return json.loads(_FIX.read_text())

def test_real_steer_descriptive_positive_without_certificate():
    r=audit_steering_lane_witness(source())
    assert r['status']=='DESCRIPTIVE_STEER_SAMPLE_AND_INTERPOLATION_WITNESS_NOT_CERTIFIED'
    assert r['sample_count']==66 and r['pose_interval_count']==65
    assert .40<r['interpolated_pose_lane_min_margin_lower_m']<.45
    assert .45<r['source_sampled_lane_min_margin_m']<.46
    assert r['max_abs_front_wheel_steer_deg']>1.5
    assert r['trigger_to_end_heading_change_deg']>.5
    assert r['safe_training_labels_allowed'] is False
    assert r['continuous_lane_safety_certified'] is False

def test_both_front_wheels_must_respond():
    d=source()
    for s in d['trials'][0]['samples']:
        s['wheel_steer_deg_front_right_raw']=0.0
    assert 'NO_ACTUAL_RIGHT_FRONT_STEERING' in audit_steering_lane_witness(d)['reasons']

def test_yaw_signal_absence_rejected_even_if_steer_command_and_wheels_exist():
    d=source()
    for s in d['trials'][0]['samples']:
        s['yaw_rate_radps_carla']=0.0
        s['yaw_deg_carla']=d['site_audit']['chosen_waypoint']['yaw_deg']
    r=audit_steering_lane_witness(d)
    assert 'NO_MEASURABLE_YAW_RATE_RESPONSE' in r['reasons']
    assert 'NO_MEASURABLE_NET_HEADING_CHANGE' in r['reasons']

def test_steering_with_vehicle_outside_straight_lane_rejected():
    d=source();s=d['trials'][0]['samples'][33]
    s['y_m_carla']-=2.0
    assert audit_steering_lane_witness(d)['status']=='REVIEW'

def test_unclear_frame_identity_or_missing_geometry_rejected():
    d=source();d['trials'][0]['samples'][20]['frame']+=4
    assert 'SOURCE_SMOKE_NOT_ACCEPTED' in audit_steering_lane_witness(d)['reasons']
    d=source();d['physics']['bounding_box']['extent'].pop('x')
    assert 'MISSING_BOUNDING_BOX_GEOMETRY' in audit_steering_lane_witness(d)['reasons']

def test_source_opendrive_and_lane_identity_required():
    d=source();d['world_provenance']['opendrive_sha256']='bad'
    assert 'NO_OPENDRIVE_PROVENANCE' in audit_steering_lane_witness(d)['reasons']
    d=source();d['expected_start_lane']['lane_id']+=1
    assert 'START_LANE_IDENTITY_DISAGREEMENT' in audit_steering_lane_witness(d)['reasons']

def test_no_brake_or_combined_false_substitution():
    d=source();d['trials'][0]['maneuver']='brake'
    assert 'STEERING_OR_COMBINED_TRIAL_REQUIRED' in audit_steering_lane_witness(d)['reasons']

def test_extrema_trig_include_interior_critical_points():
    import math
    assert _max_abs_trig(0,math.pi,'sin')==1
    assert _max_abs_trig(-math.pi/2,math.pi/2,'cos')==1
    assert _max_abs_trig(0,0,'sin')==0
    assert _max_abs_trig(0,0,'cos')==1


def _evidence():
    key='a'*64;ids=['w_hidden','w_public'];lo=Q(0);hi=Q(1)
    gate=HybridClockGate('CONDITIONAL_EXACT_MODEL_HYBRID_PARTITION_READY',(),
          (AtomicClockSlab(lo,hi,(),()),),
          (((),tuple(ids)),),((lo,hi,(((),tuple(ids)),)),),False)
    led=[];hando=[];bind=[]
    for w in ids:
        led.append(WorldSlabEvidence(w,lo,hi,'same_control',
            native_tube_ref='b'*64,guard_snapshot_ref='c'*64,
            resource_audit_ref='d'*64,observation_update_ref='e'*64))
        hando.append(SlabHandoff(w,lo,hi,((Q(0),Q(1)),),((Q(0),Q(1)),),'b'*64))
        bind.append(WorldSlabBinding(w,lo,hi,'same_control',key,'b'*64,'c'*64,'d'*64,'e'*64))
    return gate,tuple(led),tuple(hando),tuple(bind)

def test_hybrid_contract_aligned_but_never_certified():
    r=audit_hybrid_artifact_binding(*_evidence())
    assert r['status']=='CONDITIONAL_ARTIFACT_IDENTITY_ALIGNED_NOT_CERTIFIED'
    assert r['safety_certified'] is False and r['real_native_picard_replayed'] is False
    assert len(r['unclosed_independent_replay_obligations'])>0

def test_hybrid_join_rejects_cross_world_artifact_substitution():
    gate,led,hand,bnd=_evidence()
    tampered=list(bnd)
    tampered[0]=WorldSlabBinding('w_hidden',Q(0),Q(1),'same_control','a'*64,'9'*64,'c'*64,'d'*64,'e'*64)
    r=audit_hybrid_artifact_binding(gate,led,hand,tuple(tampered))
    assert 'NATIVE_TUBE_CROSS_ARTIFACT_MISMATCH:w_hidden' in r['reasons']

def test_hybrid_join_rejects_nonanticipative_control_difference():
    gate,led,hand,bnd=_evidence()
    b=list(bnd)
    b[1]=WorldSlabBinding('w_public',Q(0),Q(1),'different','a'*64,'b'*64,'c'*64,'d'*64,'e'*64)
    r=audit_hybrid_artifact_binding(gate,led,hand,tuple(b))
    assert 'NONANTICIPATIVE_CONTROL_BINDING_MISMATCH' in r['reasons']
    assert r['status']=='UNKNOWN'

def test_hybrid_join_missing_world_is_not_success():
    gate,led,hand,bnd=_evidence()
    r=audit_hybrid_artifact_binding(gate,led,hand,bnd[:1])
    assert 'MISSING_OR_EXTRA_WORLD_TIME_BINDINGS' in r['reasons']

def test_hybrid_join_protocol_contract_must_match_all_hidden_worlds():
    gate,led,hand,bnd=_evidence();b=list(bnd)
    b[1]=WorldSlabBinding('w_public',Q(0),Q(1),'same_control','f'*64,'b'*64,'c'*64,'d'*64,'e'*64)
    r=audit_hybrid_artifact_binding(gate,led,hand,tuple(b))
    assert 'PROTOCOL_CONTRACT_CHANGED_INSIDE_DECLARED_SUPPORT' in r['reasons']

def test_lateral_witness_invalid_trigger_fails_closed_not_exception():
    d=source();d['trials'][0]['trigger_frame']=None
    r=audit_steering_lane_witness(d)
    assert r['status']=='REVIEW' and 'INVALID_TRIGGER_FRAME' in r['reasons']

def test_lateral_witness_rejects_yaw_rate_not_consistent_with_heading_delta():
    d=source()
    for s in d['trials'][0]['samples']:
        if s['frame']>d['trials'][0]['trigger_frame']:
            s['yaw_rate_radps_carla']+=5.
    r=audit_steering_lane_witness(d)
    assert 'YAW_RATE_AND_HEADING_INCREMENT_INCONSISTENT' in r['reasons']

def test_lateral_witness_independently_computes_sampled_margin():
    r=audit_steering_lane_witness(source())
    assert r['independent_source_axis_sampled_min_margin_m']>0
    assert r['max_abs_heading_fd_yaw_rate_residual_radps']<0.12
