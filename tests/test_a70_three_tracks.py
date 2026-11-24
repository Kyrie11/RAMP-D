"""A70 adversarial negative tests: actual native slab replays, CARLA timecourses, leakage."""
from __future__ import annotations
import copy,json,hashlib
from dataclasses import replace
from fractions import Fraction as Q
from pathlib import Path
import pytest
from rampd_core.model import BicycleParameters,ControlBounds,StateBounds
from rampd_core.interval import Interval
from rampd_core.reachability import integrate
from rampd_core.exact_time import binary64_bracket
from rampd_core.a5_replay_bridge import exact_step_endpoint
from rampd_core.a60_clock_resource import ClockEvent
from rampd_core.a61_hybrid_partition import ClockWorld
from rampd_core.a70_native_segmented import NativeSlabInput,replay_segmented_native
from rampd_core.a70_hybrid_guard_preflight import AtSlabStartPermission,audit_native_guard_projection,audit_rank_progress
from rampd_core.a70_physics_timecourse import audit_brake_timecourses
from rampd_core.a69_supervision_provenance import EvidenceRow
from rampd_core.a70_provenance_family import audit_recording_families

ROOT=Path(__file__).parents[1]
P=BicycleParameters(3,.9)
H=Q(1,20)
Z=(Interval.point(0),)*6
U=ControlBounds.point(0,0)


def cases():
    initial=StateBounds.point([0,0,0,4,0,0])
    prior=integrate(initial,U,P,binary64_bracket(H)[1])
    terminal=exact_step_endpoint(prior,H)
    worlds=tuple(ClockWorld(w,(ClockEvent('rule-'+w,'RULE_EFFECTIVE',H,'sim'),),
           declared_complete=True,public_history_id='same') for w in ('hA','hB'))
    rows=tuple(NativeSlabInput(w,a,b,'common',state,U,Z) for w in ('hA','hB')
                for a,b,state in ((Q(0),H,initial),(H,2*H,terminal)))
    return worlds,rows


def run(worlds=None,rows=None):
    w,r=cases();return replay_segmented_native(w if worlds is None else worlds,
        r if rows is None else rows,start=Q(0),end=2*H,params=P)


def per_rows():
    return tuple(AtSlabStartPermission(w,a,b,True,True,True,1,1,()) for w in ('hA','hB')
                 for a,b in ((Q(0),H),(H,2*H)))


def test_native_two_hidden_worlds_event_middle_actual_picard_replayed():
    report,certs=run()
    assert report['status']=='CONDITIONAL_DECLARED_EGO_NATIVE_PICARD_SEGMENTED_REPLAY',report
    assert report['replayed_world_slabs']==4 and len(certs)==4
    assert all(r['validated_picard_steps']>0 for r in report['rows'])
    assert not report['full_sc'] and not report['full_safe_tube']


def test_native_hidden_world_missing_is_unknown():
    w,r=cases();q,_=run(rows=r[:-1]);assert 'MISSING_OR_EXTRA_NATIVE_WORLD_SLAB' in q['reasons']


def test_native_same_control_id_but_different_physical_command_is_unknown():
    w,r=cases();r=list(r);r[2]=replace(r[2],control=ControlBounds.point(1,0))
    q,_=run(rows=tuple(r));assert 'PUBLIC_NONANTICIPATIVITY_CONTROL_ID_OR_VALUE_MISMATCH' in q['reasons']


def test_native_hidden_history_command_nonanticipativity():
    w,r=cases();r=list(r);r[2]=replace(r[2],public_control_id='secret-other')
    q,_=run(rows=tuple(r));assert 'PUBLIC_NONANTICIPATIVITY_CONTROL_ID_OR_VALUE_MISMATCH' in q['reasons']


def test_native_underapproximated_handoff_must_fail():
    w,r=cases();r=list(r);r[1]=replace(r[1],state_start=StateBounds.point([.2,0,0,4,0,0]))
    q,_=run(rows=tuple(r));assert any('NATIVE_HANDOFF_UNDERAPPROXIMATION' in a for a in q['reasons'])


def test_native_malicious_incomplete_rule_world_is_unknown():
    w,r=cases();w=list(w);w[1]=replace(w[1],declared_complete=False)
    q,_=run(worlds=tuple(w));assert any('INCOMPLETE_CLOCK_EVENT_SUPPORT' in a for a in q['reasons'])


def test_native_physical_budget_fails_closed():
    from rampd_core.reachability import PicardOptions
    w,r=cases();q,_=replay_segmented_native(w,r,start=Q(0),end=2*H,params=P,
                            options=PicardOptions(max_iterations=1,max_depth=0))
    assert q['status']=='UNKNOWN' and not q['full_sc']


def test_guard_native_far_resource_exclusion_conditional_not_sc():
    q,certs=run();w,_=cases()
    a=audit_native_guard_projection(q,certs,w,per_rows(),resource_x_lo=Q(10),
                resource_x_hi=Q(11),ego_half_length=Q(1,10),
                actor_roster_physically_complete=True,controller_authority_physically_attested=True)
    assert a['status']=='CONDITIONAL_NATIVE_RESOURCE_X_EXCLUSION' and not a['full_sc_certified']


def test_guard_frame_interior_may_enter_even_if_start_end_outside():
    q,certs=run();w,_=cases()
    a=audit_native_guard_projection(q,certs,w,per_rows(),resource_x_lo=Q(1,4),
                resource_x_hi=Q(3,10),ego_half_length=Q(1,10),
                actor_roster_physically_complete=True,controller_authority_physically_attested=True)
    assert a['status']=='UNKNOWN'
    assert any('POSSIBLE_INTERIOR_RESOURCE_OCCUPANCY' in x for x in a['reasons'])


def test_guard_closed_and_no_ack_at_slab_start_fail_closed():
    q,certs=run();w,_=cases()
    p=tuple(replace(s,entry_open=False,ack_version=None) for s in per_rows())
    a=audit_native_guard_projection(q,certs,w,p,resource_x_lo=Q(1,4),
                resource_x_hi=Q(3,10),ego_half_length=Q(1,10),
                actor_roster_physically_complete=True,controller_authority_physically_attested=True)
    assert any('MAY_ENTER_WHILE_ENTRY_GUARD_CLOSED' in s for s in a['reasons'])
    assert any('MAY_ENTER_WITHOUT_MATCHING_ACK_VERSION' in s for s in a['reasons'])


def test_guard_declared_ack_but_no_clock_ack_evidence():
    q,certs=run();w,_=cases()
    a=audit_native_guard_projection(q,certs,w,per_rows(),resource_x_lo=Q(1,4),
                resource_x_hi=Q(3,10),ego_half_length=Q(1,10),
                actor_roster_physically_complete=True,controller_authority_physically_attested=True)
    assert any('NO_CLOCK_ACK_BEFORE_RESOURCE_SLAB' in s for s in a['reasons'])


def test_guard_forged_raw_native_certificate_even_digest_changed_fails():
    q,certs=run();w,_=cases()
    key=list(certs)[0]; certs=dict(certs);certs[key]=copy.deepcopy(certs[key]);
    certs[key]['segments'][0]['tube'][0]=[0.,0.]
    altered=copy.deepcopy(q);raw=json.dumps(certs[key],sort_keys=True,separators=(',',':'),allow_nan=False).encode()
    altered['rows'][0]['certificate_sha256']=hashlib.sha256(raw).hexdigest()
    a=audit_native_guard_projection(altered,certs,w,per_rows(),resource_x_lo=Q(10),
                resource_x_hi=Q(11),ego_half_length=Q(1,10),
                actor_roster_physically_complete=True,controller_authority_physically_attested=True)
    assert any('CERTIFICATE_BYTES_OR_NATIVE_PROOF_INVALID' in x for x in a['reasons'])


def test_rank_not_decreasing_rejected():
    assert 'RANK_NOT_STRICTLY_DECREASING:o' in audit_rank_progress((('o',2,2,False,False),))['reasons']


def test_zero_rank_unverified_tail_rejected():
    r=audit_rank_progress((('o',1,0,True,False),))
    assert 'TERMINAL_ACCEPTANCE_TAIL_UNPROVEN:o' in r['reasons']


def test_rank_sanity_never_certifies_tail():
    r=audit_rank_progress((('o',1,0,True,True),));assert r['status'].startswith('CONDITIONAL') and not r['sc_certified']


def real_arms():
    return {'b15':(ROOT/'tests/fixtures/a70_brake_b15.json').read_bytes(),
            'b30':(ROOT/'tests/fixtures/a70_brake_b30.json').read_bytes(),
            'b45':(ROOT/'tests/fixtures/a70_brake_b45.json').read_bytes()}


def test_physical_actual_three_arm_peaks_are_in_different_speed_regimes():
    r=audit_brake_timecourses(real_arms())
    assert r['status']=='DESCRIPTIVE_TIMECOURSES_RECOMPUTED_MODEL_UNRESOLVED',r
    by={x['brake_fraction']:x for x in r['rows']}
    assert by[.15]['peak_regime']=='NEAR_STOP'
    assert by[.3]['peak_regime']=='MOVING' and by[.45]['peak_regime']=='MOVING'
    assert r['peak_speed_regimes_mixed'] and not r['actual_brake_saturation_identified']
    assert all(x['stop_observed'] for x in r['rows'])


def test_physical_one_arm_missing_rejected():
    r=audit_brake_timecourses(dict(list(real_arms().items())[:2]));assert r['status']=='REVIEW'


def test_physical_requires_three_replications_per_level_for_robustness():
    r=audit_brake_timecourses(real_arms(),min_repeats_per_level=3)
    assert r['status']=='REVIEW' and not r['physical_disturbance_support_certified']


def test_physical_incomplete_frame_time_rejected():
    a=real_arms();d=json.loads(a['b15']);t=d['trials'][0];t['samples'][-1]['sim_time_s']=t['samples'][-2]['sim_time_s']
    a['b15']=json.dumps(d).encode()
    r=audit_brake_timecourses(a)
    assert any('DISCONTIGUOUS_SIM_TIMESTAMPS' in x for x in r['reasons'])


def ev(sample,scenario,split,root='physical-scene',family='episode-42'):
    doc=dict(scenario_id=scenario,domain='sumo',source_role='SIMULATED_EVENT_LOG',
             event_or_sample_time=1,root_scenario_id=root,recording_family_id=family,
             dataset_id='sim-ds',exogenous_realization_id='seed-8')
    raw=json.dumps(doc).encode()
    return EvidenceRow(sample,scenario,split,'L_event','SIMULATED_EVENT_LOG',
                         'sumo',raw,hashlib.sha256(raw).hexdigest())


def test_supervision_same_root_renamed_scenarios_cannot_split():
    r=audit_recording_families((ev('one','scenario-A','train'),ev('two','scenario-B','test')))
    assert any('RECORDING_FAMILY_SPLIT_LEAK' in x for x in r['reasons'])


def test_supervision_new_recording_different_root_can_split():
    r=audit_recording_families((ev('one','scenario-A','train'),ev('two','scenario-B','test',root='other',family='episode-77')))
    assert r['status']=='CONDITIONAL_AUXILIARY_FAMILY_SPLITS_PASS'
    assert not r['safe_training_labels_allowed']


def test_supervision_missing_canonical_family_identity_refused():
    e=ev('one','scenario-A','train');d=json.loads(e.raw);del d['root_scenario_id'];raw=json.dumps(d).encode()
    e=replace(e,raw=raw,declared_sha256=hashlib.sha256(raw).hexdigest())
    r=audit_recording_families((e,))
    assert any('MISSING_CANONICAL_RECORDING_FAMILY_IDENTITY' in x for x in r['reasons'])


def test_supervision_formal_label_never_released():
    e=ev('one','scenario-A','train');e=replace(e,label='L_viability',role='COMPLETE_SC_ORACLE_PROOF')
    d=json.loads(e.raw);d['source_role']=e.role;raw=json.dumps(d).encode();e=replace(e,raw=raw,declared_sha256=hashlib.sha256(raw).hexdigest())
    r=audit_recording_families((e,));assert not any(r['formal_masks'].values())


def test_guard_initial_capacity_conflict_rejected_before_any_new_entry():
    q,certs=run();w,_=cases()
    perms=list(per_rows());perms[0]=replace(perms[0],initial_occupants=(('oldA','A'),('oldB','B')))
    a=audit_native_guard_projection(q,certs,w,tuple(perms),resource_x_lo=Q(10),
                resource_x_hi=Q(11),ego_half_length=Q(1,10),
                actor_roster_physically_complete=True,controller_authority_physically_attested=True)
    assert any('INITIAL_RESOURCE_CAPACITY_EXCEEDED' in x for x in a['reasons'])
    assert any('OPPOSING_DIRECTIONS_INITIAL_RESOURCE_CONFLICT' in x for x in a['reasons'])


def test_guard_delayed_ack_at_event_boundary_cannot_authorize_earlier_slab():
    ws,rr=cases()
    updated=[]
    for w in ws:
        ev=(ClockEvent('controller','COMMAND',Q(0),'sim','1'),
            ClockEvent('controller','ACK',H,'sim','1'))+w.events
        updated.append(replace(w,events=ev))
    q,certs=run(worlds=tuple(updated))
    assert q['status'].startswith('CONDITIONAL'),q['reasons']
    a=audit_native_guard_projection(q,certs,tuple(updated),per_rows(),resource_x_lo=Q(1,4),
                resource_x_hi=Q(3,10),ego_half_length=Q(1,10),
                actor_roster_physically_complete=True,controller_authority_physically_attested=True)
    assert a['status']=='UNKNOWN' and any('NO_CLOCK_ACK_BEFORE_RESOURCE_SLAB' in x for x in a['reasons'])


def test_physical_corrupted_timecourse_returns_review_not_descriptive():
    a=real_arms();d=json.loads(a['b15']);t=d['trials'][0]
    t['samples'][-1]['sim_time_s']=t['samples'][-2]['sim_time_s']
    a['b15']=json.dumps(d).encode();r=audit_brake_timecourses(a)
    assert r['status']=='REVIEW'


def test_carla_new_brake_only_point15_is_valid_declared_protocol():
    from rampd_core.a64_carla_smoke_evidence import brake_only_profile
    post=[dict(command_brake=.15)]*40
    assert brake_only_profile(dict(brake_only_fraction=.15),post)==(.15,'DECLARED_INTERVENTION')


def test_carla_brake_only_legacy_point70_inference_not_certified():
    from rampd_core.a64_carla_smoke_evidence import brake_only_profile
    f,provenance=brake_only_profile({},[dict(command_brake=.7)]*40)
    assert abs(f-.7)<1e-9 and provenance.startswith('LEGACY_')


def test_carla_brake_only_explicit_wrong_fraction_not_replaced_by_legacy():
    from rampd_core.a64_carla_smoke_evidence import brake_only_profile
    f,provenance=brake_only_profile(dict(brake_only_fraction=0),[dict(command_brake=.7)]*40)
    assert f==0 and provenance=='DECLARED_INTERVENTION'


def test_carla_brake_only_no_silent_steering_in_cmd_semantics():
    from rampd_core.a64_carla_smoke_evidence import audit_single_control_smoke
    d=json.loads(real_arms()['b15']);t=d['trials'][0]
    t['maneuver']='brake';t['brake_only_fraction']=.15
    for s in t['samples']:
        if s['frame']>t['trigger_frame']:
            s['command_steer']=.03;s['actual_steer']=.03
    result=audit_single_control_smoke(d)
    assert 'BRAKE_ONLY_ARM_CONTAINS_STEERING' in result['reasons']


def test_guard_tampered_hidden_clock_contract_bound_to_native_proof():
    q,certs=run();w,_=cases();w=list(w)
    w[0]=replace(w[0],events=(ClockEvent('other-rule','RULE_EFFECTIVE',H,'mutated-provenance'),))
    a=audit_native_guard_projection(q,certs,tuple(w),per_rows(),
                resource_x_lo=Q(10),resource_x_hi=Q(11),ego_half_length=Q(1,10),
                actor_roster_physically_complete=True,controller_authority_physically_attested=True)
    assert 'NATIVE_CLOCK_SUPPORT_DECLARATION_DIGEST_MISMATCH' in a['reasons']
