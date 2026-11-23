"""A69 adversarial three-track gates. Pure Python and independent of CARLA server."""
from __future__ import annotations
import copy,hashlib,json
from dataclasses import replace
from fractions import Fraction as Q
from pathlib import Path
import pytest
from rampd_core.a61_hybrid_partition import AtomicClockSlab,HybridClockGate
from rampd_core.a68_affine_slab_replay import AffineSlab,QInterval
from rampd_core.a68_guard_resource_monitor import ZoneTick
from rampd_core.a69_hybrid_joint_reference import JointSlab,audit_joint_reference
from rampd_core.a69_physical_factors import audit_brake_sweep
from rampd_core.a69_supervision_provenance import EvidenceRow,audit_lineage
from rampd_core.a68_waymax_action_contract import JerkSteerState,audit_waymax_piecewise_action

BASE=Path(__file__).parent/'fixtures'

def interval(a,b=None):return QInterval(Q(a),Q(a if b is None else b))
def clock():
    ids=('hidden-A','hidden-B')
    return HybridClockGate('CONDITIONAL_EXACT_MODEL_HYBRID_PARTITION_READY',(),
      (AtomicClockSlab(Q(0),Q(1),(),()),AtomicClockSlab(Q(1),Q(2),(),())),
      (((),ids),),((Q(0),Q(1),(((),ids),)),(Q(1),Q(2),(((),ids),))),False)

def joint_rows():
    records=[]
    for w in ('hidden-A','hidden-B'):
        for i in range(2):
            records.append(JointSlab(
              AffineSlab(w,Q(i),Q(i+1),'policy-'+str(i),
                 interval(i),interval(1),interval(0),interval(i+1),interval(1),interval(i,i+1),interval(1)),
              ZoneTick(Q(i+1),1,1,True,True,True,True,1,())
            ))
    return tuple(records)

def checked(rows):
    return audit_joint_reference(clock(),tuple(rows),initial_occupants={'hidden-A':(), 'hidden-B':()},roster_attested=True,authority_attested=True)

def test_math_joint_two_hidden_worlds_two_slabs():
    r=checked(joint_rows());assert r['status']=='CONDITIONAL_JOINT_TOY_MODEL_REPLAY_PASS'
    assert not r['native_mpfr_picard_replayed'] and not r['safe_training_labels_allowed']

def test_math_joint_omitted_guard_world_fails():
    assert 'JOINT_SUPPORT_MISSING_OR_EXTRA' in checked(joint_rows()[:-1])['reasons']

def test_math_guard_timestamp_not_slab_end():
    rs=list(joint_rows());rs[0]=replace(rs[0],zone_at_end=replace(rs[0].zone_at_end,time=Q(3)))
    assert any('GUARD_SNAPSHOT_NOT_AT_SLAB_END' in v for v in checked(rs)['reasons'])

def test_math_underapproximated_physical_set_fails_even_guard_ok():
    rs=list(joint_rows());rs[0]=replace(rs[0],affine=replace(rs[0].affine,x_end=interval(0)))
    assert any('UNDERAPPROXIMATED_X_ENDPOINT' in v for v in checked(rs)['reasons'])

def test_math_closed_guard_without_ack_fails():
    rs=list(joint_rows());a=rs[0].affine
    rs[0]=replace(rs[0],zone_at_end=replace(rs[0].zone_at_end,occupants=(('ego','A'),),ack_version=None))
    assert any('ENTRY_WITHOUT_EFFECTIVE_MATCHING_ACK' in v for v in checked(rs)['reasons'])

def test_math_common_public_history_control_is_nonanticipative():
    rs=list(joint_rows());rs[2]=replace(rs[2],affine=replace(rs[2].affine,public_control_id='hidden-steer'))
    assert 'HIDDEN_WORLD_DEPENDENT_CONTROL' in checked(rs)['reasons']

def test_math_missing_initial_roster_fails_closed():
    r=audit_joint_reference(clock(),joint_rows(),roster_attested=True,authority_attested=True)
    assert 'INITIAL_ROSTER_MISSING_OR_EXTRA_WORLD' in r['reasons']

def test_math_authority_not_attested_fails_closed():
    r=audit_joint_reference(clock(),joint_rows(),initial_occupants={'hidden-A':(), 'hidden-B':()},roster_attested=True,authority_attested=False)
    assert r['status']=='UNKNOWN' and any('CONTROLLER_AUTHORITY_NOT_ATTESTED' in a for a in r['reasons'])

def test_waymax_interior_stop_rejected_despite_positive_terminal_speed():
    s=JerkSteerState(Q(1,100),Q(-1),Q(0))
    with pytest.raises(ValueError,match='INTERIOR_STOP_REVERSAL'):
        audit_waymax_piecewise_action(s,dt=Q(1,10),jerk=Q(20),steering_rate_radps=Q(0),wheelbase_m=Q(3))

def test_waymax_no_reversal_ordinary_case():
    s=JerkSteerState(Q(5),Q(0),Q(0))
    r=audit_waymax_piecewise_action(s,dt=Q(1,10),jerk=Q(1),steering_rate_radps=Q(0),wheelbase_m=Q(3))
    assert r['status']=='NOMINAL_DISCRETE_ACTION_ADAPTER_WITH_EXPLICIT_MISMATCH'


def raw_runs():return {str(i):(BASE/f'a68_combined_repeat{i}.json').read_bytes() for i in (1,2,3)}

def as_doc(raw):return json.loads(raw)

def arm(raw,level):
    doc=as_doc(raw);t=doc['trials'][0];t['combined_brake_fraction']=level
    for s in t['samples']:
        if s['frame']>t['trigger_frame']:
            s['command_brake']=level;s['actual_brake']=level
    return json.dumps(doc,sort_keys=True,allow_nan=False).encode()

def test_physical_uploaded_three_repeats_not_multifactor():
    r=audit_brake_sweep(raw_runs())
    assert r['status']=='REVIEW'
    assert any('MISSING_ARM_OR_REPEATS' in x for x in r['reasons'])
    assert not r['safe_training_labels_allowed']

def test_physical_one_factor_three_arms_descriptive_only():
    raws=raw_runs();r=audit_brake_sweep({str(i):arm(raws[str(i)],level) for i,level in zip((1,2,3),(.15,.30,.45))})
    assert r['status']=='DESCRIPTIVE_ONE_FACTOR_SWEEP_COMPLETE_MODEL_REVIEW'
    assert not r['physical_response_function_identified']

def test_physical_changed_map_confounder_rejected():
    raw=raw_runs();docs=[as_doc(v) for v in raw.values()]
    for d,level in zip(docs,(.15,.30,.45)):
        t=d['trials'][0];t['combined_brake_fraction']=level
        for s in t['samples']:
            if s['frame']>t['trigger_frame']:
                s['command_brake']=level;s['actual_brake']=level
    docs[1]['map']='Carla/Maps/Town04'
    r=audit_brake_sweep({str(i):json.dumps(d).encode() for i,d in enumerate(docs)})
    assert 'NONBRAKE_EXPERIMENT_FACTOR_CHANGED_OR_EMPTY' in r['reasons']

def test_physical_changed_site_confounder_rejected():
    raws=raw_runs()
    docs={str(i):arm(raws[str(i)],level) for i,level in zip((1,2,3),(.15,.30,.45))}
    d=as_doc(docs['2']);d['site_audit']['chosen_waypoint']['source']='spawn'
    docs['2']=json.dumps(d).encode()
    assert 'NONBRAKE_EXPERIMENT_FACTOR_CHANGED_OR_EMPTY' in audit_brake_sweep(docs)['reasons']

def test_physical_unmatched_trigger_speed_rejected():
    raws=raw_runs()
    docs={str(i):arm(raws[str(i)],level) for i,level in zip((1,2,3),(.15,.30,.45))}
    d=as_doc(docs['2']);t=d['trials'][0]
    next(s for s in t['samples'] if s['frame']==t['trigger_frame'])['planar_speed_mps']=4.4
    docs['2']=json.dumps(d).encode()
    r=audit_brake_sweep(docs)
    assert any('TRIGGER_SPEED_MISMATCH' in reason for reason in r['reasons'])

def test_physical_actual_command_fraud_rejected():
    raws=raw_runs();docs={str(i):arm(raws[str(i)],level) for i,level in zip((1,2,3),(.15,.30,.45))}
    d=as_doc(docs['1']);t=d['trials'][0];next(s for s in t['samples'] if s['frame']>t['trigger_frame'])['actual_brake']=0
    docs['1']=json.dumps(d).encode();r=audit_brake_sweep(docs)
    assert any('BRAKE_COMMAND_OR_ACTUAL_MISMATCH' in x for x in r['reasons'])

def test_physical_duplicate_json_keys_rejected():
    data=raw_runs();data['1']=b'{"trials":[],"trials":[]}'
    assert any('DUPLICATE_JSON_KEY' in x for x in audit_brake_sweep(data)['reasons'])

def test_physical_duplicate_source_rejected():
    raw=raw_runs();raw['2']=raw['1'];assert 'DUPLICATE_RAW_SOURCE' in audit_brake_sweep(raw)['reasons']

def ev(sample='a',scenario='case1',split='train',domain='sumo',role='SIMULATED_EVENT_LOG',
       label='L_event',payload=None):
    payload=payload or {'scenario_id':scenario,'domain':domain,'source_role':role,'event_or_sample_time':'12/5'}
    b=json.dumps(payload).encode();return EvidenceRow(sample,scenario,split,label,role,domain,b,hashlib.sha256(b).hexdigest())

def test_supervision_lineage_auxiliary_never_formal():
    r=audit_lineage((ev(),ev('b','case2','test')))
    assert r['status']=='CONDITIONAL_AUXILIARY_LINEAGE_INVENTORY_PASS'
    assert all(v==0 for v in r['formal_label_masks'].values())

def test_supervision_prevent_same_scenario_cross_split():
    r=audit_lineage((ev(),ev('b','case1','test')))
    assert 'SCENARIO_LEAKED_ACROSS_SPLITS:case1' in r['reasons']

def test_supervision_internal_scenario_provenance_fraud():
    r=audit_lineage((ev(payload={'scenario_id':'other','domain':'sumo','source_role':'SIMULATED_EVENT_LOG','event_or_sample_time':1}),))
    assert any('EVIDENCE_INTERNAL_PROVENANCE_MISMATCH' in x for x in r['reasons'])

def test_supervision_511_report_cannot_be_formal_event_authority():
    r=audit_lineage((ev(role='REPORT_TIME_AS_PHYSICAL_EFFECT'),))
    assert 'ROLE_MISMATCH:L_event' in r['reasons']

def test_supervision_sha_tampering_detected():
    a=ev();a=replace(a,declared_sha256='f'*64)
    assert 'SOURCE_HASH_MISMATCH:a' in audit_lineage((a,))['reasons']

def test_supervision_one_bytes_two_domains_refused():
    a=ev();b=replace(a,sample_id='b',scenario_id='case2',split='test')
    r=audit_lineage((a,b))
    assert 'SAME_RAW_BYTES_REASSIGNED_TO_OTHER_DOMAIN_OR_SPLIT' in r['reasons']

def test_supervision_viability_needs_independent_proof():
    a=ev(label='L_viability',role='COMPLETE_SC_ORACLE_PROOF')
    r=audit_lineage((a,));assert 'FORMAL_PROOF_REPLAY_ABSENT:L_viability' in r['reasons']

def test_supervision_causal_needs_exogenous_pairing():
    a=ev(label='L_causal',role='DECLARED_PAIRED_INTERVENTION_LOG')
    assert 'PAIRED_EXOGENOUS_INTERVENTIONS_UNVERIFIED' in audit_lineage((a,))['reasons']

def test_supervision_missing_time_rejected():
    r=audit_lineage((ev(payload={'scenario_id':'case1','domain':'sumo','source_role':'SIMULATED_EVENT_LOG'}),))
    assert any('MISSING_SOURCE_TIME_PROVENANCE' in x for x in r['reasons'])

from rampd_core.a69_affine_artifact_semantics import audit_affine_native_artifact_semantics
from rampd_core.a66_hybrid_contract_binding import WorldSlabBinding

def native_artifacts(mutator=None):
    bs=[];raw={}
    protocol=json.dumps(dict(schema='rampd.a67.protocol_contract.v1',
        contract_id='toy-two-hidden-worlds',semantic_model='exact_affine_xdot_v_vdot_a_v1')).encode()
    pd=hashlib.sha256(protocol).hexdigest()
    for row in joint_rows():
        a=row.affine
        body=dict(model='exact_affine_xdot_v_vdot_a_v1')
        for name in ('x_start','v_start','a_set','x_end','v_end','x_tube','v_tube'):
            v=getattr(a,name)
            body[name]=[str(v.lo),str(v.hi)]
        doc=dict(schema='rampd.a67.context_artifact.v1',role='native_tube',
            world_id=a.world_id,start=str(a.start),end=str(a.end),
            public_control_id=a.public_control_id,body=body)
        if mutator:mutator(doc)
        b=json.dumps(doc,sort_keys=True).encode();dg=hashlib.sha256(b).hexdigest()
        raw[(a.world_id,a.start,a.end)]=b
        bs.append(WorldSlabBinding(a.world_id,a.start,a.end,a.public_control_id,
            pd,dg,'f'*64,'f'*64,'f'*64))
    return tuple(bs),raw,protocol

def test_semantic_replay_exact_toy_artifact_passes():
    bs,raw,p=native_artifacts()
    r=audit_affine_native_artifact_semantics(clock(),bs,raw,protocol_bytes=p)
    assert r['status']=='CONDITIONAL_TOY_AFFINE_ARTIFACT_SEMANTICS_REPLAYED'
    assert not r['mpfr_picard_native_proof_replayed']

def test_semantic_replay_underapproximated_payload_rejected_even_hash_updated():
    def bad(doc):
        if doc['world_id']=='hidden-A' and doc['start']=='0':doc['body']['x_end']=['0','0']
    bs,raw,p=native_artifacts(bad)
    assert any('UNDERAPPROXIMATED_X_ENDPOINT' in x for x in
               audit_affine_native_artifact_semantics(clock(),bs,raw,protocol_bytes=p)['reasons'])

def test_semantic_replay_corrupted_bytes_rejected():
    bs,raw,p=native_artifacts();raw=dict(raw);raw[('hidden-A',Q(0),Q(1))]=b'{}'
    assert any('NATIVE_ROLE_BYTES_HASH_MISMATCH' in x for x in
               audit_affine_native_artifact_semantics(clock(),bs,raw,protocol_bytes=p)['reasons'])

def test_semantic_replay_missing_world_rejected():
    bs,raw,p=native_artifacts();raw=dict(raw);del raw[('hidden-A',Q(0),Q(1))]
    assert 'INCOMPLETE_OR_DUPLICATE_NATIVE_ROLE_EVIDENCE' in audit_affine_native_artifact_semantics(clock(),bs,raw,protocol_bytes=p)['reasons']

def test_semantic_replay_cross_world_payload_rejected():
    def bad(doc):
        if doc['world_id']=='hidden-A' and doc['start']=='0':doc['world_id']='hidden-B'
    bs,raw,p=native_artifacts(bad)
    assert any('NATIVE_WORLD_TIME_CONTROL_CONTEXT_INVALID' in x for x in
               audit_affine_native_artifact_semantics(clock(),bs,raw,protocol_bytes=p)['reasons'])

def test_semantic_replay_missing_protocol_bytes_fails():
    bs,raw,p=native_artifacts()
    r=audit_affine_native_artifact_semantics(clock(),bs,raw,protocol_bytes=None)
    assert 'MISSING_RAW_PROTOCOL_CONTRACT_BYTES' in r['reasons']

def test_semantic_replay_swapped_protocol_bytes_fails():
    bs,raw,p=native_artifacts()
    bad=p.replace(b'toy-two-hidden-worlds',b'unrelated-case')
    r=audit_affine_native_artifact_semantics(clock(),bs,raw,protocol_bytes=bad)
    assert any('RAW_PROTOCOL_DIGEST_MISMATCH' in x for x in r['reasons'])
