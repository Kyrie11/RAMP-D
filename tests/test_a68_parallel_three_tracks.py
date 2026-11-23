"""A68 three-track tests; adversarial inputs MUST never become certified labels."""
from __future__ import annotations
import copy,hashlib,json
from dataclasses import replace
from fractions import Fraction as Q
from pathlib import Path

from rampd_core.a61_hybrid_partition import AtomicClockSlab,HybridClockGate
from rampd_core.a68_affine_slab_replay import QInterval,AffineSlab,audit_affine_slab_replay,analytic_reach
from rampd_core.a68_guard_resource_monitor import ZoneTick,audit_zone_transitions
from rampd_core.a68_physical_campaign import audit_physical_repeat_campaign
from rampd_core.a68_supervision_release import SourceClaim,review_supervision_sources,LABELS

_FIX=Path(__file__).parent/'fixtures'

def q(x):return Q(x)
def iv(a,b=None):return QInterval(q(a),q(a if b is None else b))
def gate():
    ids=('h0','h1')
    return HybridClockGate('CONDITIONAL_EXACT_MODEL_HYBRID_PARTITION_READY',(),
        (AtomicClockSlab(q(0),q(1),(),()),AtomicClockSlab(q(1),q(2),(),())),
        (((),ids),),((q(0),q(1),(((),ids),)),(q(1),q(2),(((),ids),))),False)

def rows():
    res=[]
    for w in ('h0','h1'):
        res.extend((
          AffineSlab(w,q(0),q(1),'u0',iv(0),iv(1),iv(0),iv(1),iv(1),iv(0,1),iv(1)),
          AffineSlab(w,q(1),q(2),'u1',iv(1),iv(1),iv(0),iv(2),iv(1),iv(1,2),iv(1))))
    return tuple(res)

def test_math_exact_two_worlds_two_slabs_pass_model_only():
    result=audit_affine_slab_replay(gate(),rows())
    assert result['status']=='CONDITIONAL_EXACT_AFFINE_MODEL_REPLAY_PASS'
    assert result['exact_rational_affine_model_replayed']
    assert not result['native_mpfr_picard_replayed'] and not result['safe_training_labels_allowed']

def test_math_endpoint_underapproximation_fails():
    rr=list(rows());rr[0]=replace(rr[0],x_end=iv(0))
    assert 'UNDERAPPROXIMATED_X_ENDPOINT:h0' in audit_affine_slab_replay(gate(),tuple(rr))['reasons']

def test_math_tube_underapproximation_fails():
    rr=list(rows());rr[0]=replace(rr[0],x_tube=iv(0))
    assert 'UNDERAPPROXIMATED_X_TUBE:h0' in audit_affine_slab_replay(gate(),tuple(rr))['reasons']

def test_math_handoff_wrong_inclusion_direction_fails():
    rr=list(rows());rr[1]=replace(rr[1],x_start=iv(2))
    assert 'X_HANDOFF_UNDERAPPROXIMATION:h0' in audit_affine_slab_replay(gate(),tuple(rr))['reasons']

def test_math_hidden_world_missing_fails():
    assert 'INCOMPLETE_OR_EXTRA_WORLD_SLABS' in audit_affine_slab_replay(gate(),rows()[:2])['reasons']

def test_math_public_control_cannot_depend_on_hidden_world():
    rr=list(rows());rr[2]=replace(rr[2],public_control_id='peek-hidden')
    assert 'PUBLIC_NONANTICIPATIVITY_VIOLATION' in audit_affine_slab_replay(gate(),tuple(rr))['reasons']

def test_math_exact_rational_negative_acceleration_and_interior_turn():
    a=AffineSlab('w',q(0),q(1),'u',iv(0),iv(1),iv(-4),iv(-1),iv(-3),iv(-1,1),iv(-3,1))
    xe,ve,xt,vt=analytic_reach(a)
    assert xe==iv(-1) and ve==iv(-3) and xt.covers(iv(0,1))

def test_math_rejects_float_as_interval_endpoint():
    import pytest
    with pytest.raises(ValueError):QInterval(0.0,q(1))

def z(time,occ=(),**extra):
    fields=dict(time=q(time),command_version=1,ack_version=1,entry_open=True,stay_open=True,
                exit_open=True,resource_clear_before=not bool(occ),capacity=1,occupants=tuple(occ))
    fields.update(extra)
    return ZoneTick(**fields)

def valid_zone():return (z(0),z(1,(('ego','A'),),resource_clear_before=True),
                             z(2,(('ego','A'),),entry_open=False,resource_clear_before=False),
                             z(3,(),resource_clear_before=False))

def valid_zone_report(ticks):return audit_zone_transitions(tuple(ticks),dt=q(1),
                    actor_roster_attested=True,controller_authority_attested=True)

def test_guard_entry_stay_exit_and_closed_entry_during_stay():
    r=valid_zone_report(valid_zone())
    assert r['status']=='CONDITIONAL_DECLARED_ZONE_TRANSITIONS_PASS'
    assert not r['continuous_occupancy_proven']

def test_guard_missing_ack_entry_rejected():
    arr=list(valid_zone());arr[1]=replace(arr[1],ack_version=None)
    assert 'ENTRY_WITHOUT_EFFECTIVE_MATCHING_ACK' in valid_zone_report(arr)['reasons']

def test_guard_closed_entry_rejected():
    arr=list(valid_zone());arr[1]=replace(arr[1],entry_open=False)
    assert 'ENTRY_GUARD_CLOSED' in valid_zone_report(arr)['reasons']

def test_guard_stay_denial_rejected():
    arr=list(valid_zone());arr[2]=replace(arr[2],stay_open=False)
    assert 'STAY_GUARD_CLOSED' in valid_zone_report(arr)['reasons']

def test_guard_exit_denial_rejected():
    arr=list(valid_zone());arr[3]=replace(arr[3],exit_open=False)
    assert 'EXIT_GUARD_CLOSED' in valid_zone_report(arr)['reasons']

def test_guard_opposite_direction_and_capacity_rejected():
    arr=list(valid_zone());arr[1]=replace(arr[1],occupants=(('ego','A'),('other','B')))
    r=valid_zone_report(arr)
    assert 'OPPOSING_DIRECTIONS_SIMULTANEOUS' in r['reasons']
    assert 'ZONE_CAPACITY_EXCEEDED' in r['reasons']

def test_guard_time_gap_rejected():
    arr=list(valid_zone());arr[3]=replace(arr[3],time=q(4))
    assert 'MISSING_OR_NONUNIFORM_TICK' in valid_zone_report(arr)['reasons']

def test_guard_initial_clearance_lie_rejected():
    arr=list(valid_zone());arr[2]=replace(arr[2],resource_clear_before=True)
    assert 'FALSE_PREENTRY_CLEARANCE_WITH_PRIOR_OCCUPANTS' in valid_zone_report(arr)['reasons']

def test_guard_untested_authority_never_certifies():
    r=audit_zone_transitions(valid_zone(),dt=q(1))
    assert r['status']=='UNKNOWN' and 'CONTROLLER_AUTHORITY_NOT_ATTESTED' in r['reasons']

def raw_campaign():return {str(i):(_FIX/f'a68_combined_repeat{i}.json').read_bytes() for i in (1,2,3)}

def test_physical_real_three_repeat_files():
    r=audit_physical_repeat_campaign(raw_campaign())
    assert r['status']=='DESCRIPTIVE_THREE_REPEAT_PROTOCOL_REPRODUCED_MODEL_REVIEW'
    assert r['deterministic_response_repeated'] and r['all_three_show_torque_only_discrepancy']
    assert [x['actor_id'] for x in r['runs']]==[121,122,123]
    assert not r['safe_vehicle_dynamic_enclosure_available']

def test_physical_duplicate_bytes_rejected():
    d=raw_campaign();d['3']=d['1']
    assert audit_physical_repeat_campaign(d)['status']=='REVIEW'

def test_physical_duplicated_json_key_rejected():
    d=raw_campaign();d['2']=d['2'].rstrip()[:-1]+b',"actor_id":122}'
    assert 'DUPLICATE_JSON_KEY' in ' '.join(audit_physical_repeat_campaign(d)['reasons'])

def test_physical_changed_actual_brake_rejected():
    d=raw_campaign();obj=json.loads(d['3']);t=obj['trials'][0]
    t['samples'][30]['actual_brake']=0.2
    d['3']=json.dumps(obj).encode()
    assert 'COMMAND_AND_EXECUTED_CONTROL_MISMATCH' in ' '.join(audit_physical_repeat_campaign(d)['reasons'])

def test_physical_changed_mass_cannot_pool():
    d=raw_campaign();obj=json.loads(d['3']);obj['physics']['mass_kg_raw']+=10
    d['3']=json.dumps(obj).encode()
    assert 'NONUNIFORM_ACTUAL_PHYSICS_OR_PROTOCOL' in audit_physical_repeat_campaign(d)['reasons']

def test_physical_command_pulse_corruption_rejected():
    d=raw_campaign();obj=json.loads(d['1']);obj['trials'][0]['samples'][28]['command_steer']=0
    d['1']=json.dumps(obj).encode()
    assert 'STEER_NOT_3_FRAME_PULSE' in ' '.join(audit_physical_repeat_campaign(d)['reasons'])

def claim(label='L_joint',role='FACTUAL_TRACK_LOG',value=None):
    raw=b'{"source":"demo"}'
    return SourceClaim(label,role,raw,hashlib.sha256(raw).hexdigest(),value)

def test_eight_source_missing_is_not_negative():
    r=review_supervision_sources(())
    assert set(r['labels'])==set(LABELS)
    assert all(v['status']=='MISSING' and v['formal_label_mask']==0
               for v in r['labels'].values())

def test_factual_joint_is_auxiliary_only():
    r=review_supervision_sources((claim(),))
    assert r['labels']['L_joint']['status']=='AUXILIARY_SOURCE_BYTES_VERIFIED_ONLY'
    assert r['labels']['L_joint']['formal_label_mask']==0

def test_event_report_cannot_masquerade_as_simulator_effectivity():
    r=review_supervision_sources((claim('L_event','511NY_REPORT'),))
    assert 'SOURCE_ROLE_NOT_ALLOWED_FOR_LOSS' in r['labels']['L_event']['reasons']

def test_formal_viability_self_asserted_positive_is_rejected():
    r=review_supervision_sources((claim('L_viability','COMPLETE_SC_ORACLE_PROOF',True),))
    assert r['labels']['L_viability']['formal_label_mask']==0
    assert 'INDEPENDENT_M1_M12_PROOF_REPLAY_NOT_AVAILABLE' in r['labels']['L_viability']['reasons']

def test_formal_negative_zero_cannot_be_inferred_from_unknown():
    r=review_supervision_sources((claim('L_viability','COMPLETE_SC_ORACLE_PROOF',0),))
    assert 'RAW_VALUE_OFFERED_WITHOUT_INDEPENDENT_LABEL_CONSTRUCTION' in r['labels']['L_viability']['reasons']
    assert r['labels']['L_viability']['training_label_value'] is None

def test_source_digest_tamper_is_rejected():
    c=replace(claim(),claimed_sha256='0'*64)
    assert 'SOURCE_BYTES_SHA256_MISMATCH' in review_supervision_sources((c,))['labels']['L_joint']['reasons']

def test_source_duplicate_json_key_rejected():
    x=b'{"e":1,"e":2}'
    c=SourceClaim('L_event','SIMULATED_EVENT_LOG',x,hashlib.sha256(x).hexdigest())
    assert 'SOURCE_JSON_UNREADABLE_OR_NONCANONICAL' in review_supervision_sources((c,))['labels']['L_event']['reasons']

def test_source_duplicate_label_rejected():
    assert 'DUPLICATED_LABEL_SOURCE:L_joint' in review_supervision_sources((claim(),claim()))['reasons']

def test_causal_pair_not_certified_by_paired_manifest():
    r=review_supervision_sources((claim('L_causal','DECLARED_PAIRED_INTERVENTION_LOG'),))
    assert r['labels']['L_causal']['formal_label_mask']==0 and r['labels']['L_causal']['status']=='REVIEW'

from rampd_core.a68_waymax_action_contract import JerkSteerState,audit_waymax_piecewise_action

def test_waymax_jerk_adapter_exact_longitudinal_discrepancy():
    r=audit_waymax_piecewise_action(JerkSteerState(q(10),q(1),q(0)),
          dt=q(1),jerk=q(2),steering_rate_radps=q(0),wheelbase_m=q(3))
    assert r['exact_nominal_terminal_speed_mps']=='12'
    assert r['nominal_longitudinal_position_discrepancy_abs_m']=='1/6'
    assert r['waymax_action_accel_mps2']==2.0
    assert not r['lateral_discretization_error_bounded']

def test_waymax_zero_jerk_matches_longitudinal_constant_acceleration():
    r=audit_waymax_piecewise_action(JerkSteerState(q(10),q(1),q(0)),
          dt=q(1),jerk=q(0),steering_rate_radps=q(0),wheelbase_m=q(3))
    assert r['nominal_longitudinal_position_discrepancy_abs_m']=='0'

def test_waymax_steer_rate_creates_curvature_range():
    r=audit_waymax_piecewise_action(JerkSteerState(q(10),q(0),q(0)),
          dt=q(1),jerk=q(0),steering_rate_radps=Q(1,10),wheelbase_m=q(3))
    assert r['curvature_range_per_m'][0]==0 and r['curvature_range_per_m'][1]>0
    assert not r['coordinate_frame_alignment_verified']

def test_waymax_negative_terminal_speed_fail_closed():
    import pytest
    with pytest.raises(ValueError):audit_waymax_piecewise_action(
        JerkSteerState(q(1),q(-3),q(0)),dt=q(1),jerk=q(0),
        steering_rate_radps=q(0),wheelbase_m=q(3))

def test_math_rejects_forged_empty_clock_and_empty_world_support():
    g=replace(gate(),slabs=(),posterior_worlds_by_slab=())
    r=audit_affine_slab_replay(g,())
    assert 'CLOCK_SLAB_DECLARATION_INCONSISTENT' in r['reasons']
    assert 'EMPTY_DECLARED_HIDDEN_SUPPORT' in r['reasons']

def test_math_gate_slab_times_must_match_public_partition():
    g=replace(gate(),slabs=(AtomicClockSlab(q(0),q(2),(),()),))
    assert 'CLOCK_SLAB_DECLARATION_INCONSISTENT' in audit_affine_slab_replay(g,rows())['reasons']

from rampd_core.a64_carla_smoke_evidence import audit_single_control_smoke
from rampd_core.a67_carla_combined_diagnostics import audit_combined_dynamics

def test_carla_graded_brake_015_is_not_falsely_rejected_as_no_combined_control():
    # This is a *synthetic protocol consistency test*; it is NOT an actual
    # new CARLA .15-brake response and must not become a dynamics label.
    d=json.loads((_FIX/'a68_combined_repeat1.json').read_text())
    t=d['trials'][0];t['combined_brake_fraction']=.15
    for s in t['samples']:
        if s['frame']>t['trigger_frame']:
            s['command_brake']=.15;s['actual_brake']=.15
    cap=audit_single_control_smoke(d)
    dyn=audit_combined_dynamics(d)
    assert cap['status']=='DESCRIPTIVE_SINGLE_CONTROL_SMOKE_CAPTURED_NOT_CALIBRATED'
    assert dyn['diagnostic_repetition_allowed']
    assert dyn['declared_brake_fraction']==.15
    assert dyn['simultaneous_command_frames']==3
    assert not dyn['safety_training_labels_allowed']

def test_carla_graded_brake_declared_profile_mismatch_fails_closed():
    d=json.loads((_FIX/'a68_combined_repeat1.json').read_text())
    d['trials'][0]['combined_brake_fraction']=.15
    assert 'POSTTRIGGER_BRAKE_NOT_DECLARED_PROFILE' in audit_single_control_smoke(d)['reasons']
    assert not audit_combined_dynamics(d)['diagnostic_repetition_allowed']

def test_carla_legacy_missing_fraction_is_descriptively_inferred_not_certified():
    d=json.loads((_FIX/'a68_combined_repeat1.json').read_text())
    d['trials'][0].pop('combined_brake_fraction')
    cap=audit_single_control_smoke(d);dyn=audit_combined_dynamics(d)
    assert cap['status']=='DESCRIPTIVE_SINGLE_CONTROL_SMOKE_CAPTURED_NOT_CALIBRATED'
    assert cap['combined_brake_profile_source']=='LEGACY_CONSTANT_COMMAND_INFERRED_DESCRIPTIVELY'
    assert dyn['diagnostic_repetition_allowed']
    assert dyn['combined_brake_profile_source']=='LEGACY_CONSTANT_COMMAND_INFERRED_DESCRIPTIVELY'
    assert dyn['verified_uncertainty_enclosure'] is False

def test_carla_legacy_varying_undeclared_brake_is_rejected():
    d=json.loads((_FIX/'a68_combined_repeat1.json').read_text())
    t=d['trials'][0];t.pop('combined_brake_fraction')
    t['samples'][30]['command_brake']=.2;t['samples'][30]['actual_brake']=.2
    assert 'INVALID_DECLARED_COMBINED_BRAKE_PROFILE' in audit_single_control_smoke(d)['reasons']
    assert not audit_combined_dynamics(d)['diagnostic_repetition_allowed']
