"""A59/1a actual Native Picard-to-resource integration, not a final SC certificate."""
from fractions import Fraction as Q
from rampd_core.a60_clock_resource import (ResourcePermission,ClockEvent,
    audit_native_resource_tubes,native_sc_predecessor_a59_1)
from test_phase6c_a59_native import setup_sample
from test_phase6c_a58_native import args
from rampd_core.a58_native_safety import guarded_physical_post


def permissions(p):
    return {p.atom.atom_id:ResourcePermission('r',True,True,True,('A',),1) for p in (p,)}


def test_native_resource_slab_construction_from_replayed_picard():
    a=args();_,_,tubes,_=guarded_physical_post(**a)
    r=audit_native_resource_tubes(a['parents'],tubes,ego_geometry=a['ego_geometry'],
      resource=a['resource'],permissions_by_parent=permissions(a['parents'][0]),
      directions_by_actor={'ego':'A'},complete_roster=True)
    assert r.status=='CONDITIONAL_RESOURCE_SLAB_GATE_PASS' and r.coverage
    assert not r.certified


def test_native_resource_contact_cannot_bypass_a58_safety_or_rank():
    a=args(initial=(14,0,0,1,0,0))
    source=setup_sample()[1]  # deliberate source mismatch => never a SC candidate
    _,_,tubes,audit=guarded_physical_post(**a)
    r=audit_native_resource_tubes(a['parents'],tubes,ego_geometry=a['ego_geometry'],
      resource=a['resource'],permissions_by_parent=permissions(a['parents'][0]),
      directions_by_actor={'ego':'A'},complete_roster=True)
    assert r.status in ('UNKNOWN','CONDITIONAL_RESOURCE_SLAB_GATE_PASS')
    assert audit.status=='UNKNOWN'  # original A58 resource avoidance remains


def test_native_sc_extended_gate_all_subobligations_but_never_certified():
    a,source,posterior,audit,target,contract,sc=setup_sample()
    out=native_sc_predecessor_a59_1(source,a['parents'],a['control'],contract=contract,
        sc_result=sc,target_cells=(target,),params=a['params'],ego_geometry=a['ego_geometry'],
        disturbance=a['disturbance'],resource=a['resource'],queue_a=a['queue_a'],
        queue_b=a['queue_b'],limits=a['limits'],
        permissions_by_parent=permissions(a['parents'][0]),
        directions_by_actor={'ego':'A'},clock_complete=True,complete_actor_roster=True)
    assert out[3].status=='CONDITIONAL_EGO_AVOIDANCE_PASS'
    assert out[4].status=='CONDITIONAL_PHYSICAL_RANK_PREDECESSOR_CANDIDATE'
    assert out[5].status=='CONDITIONAL_RESOURCE_SLAB_GATE_PASS'
    assert out[6].status=='CONDITIONAL_EXACT_MODEL_CLOCK_PASS'
    assert out[7].status=='CONDITIONAL_A59_1_SUBGATE_CANDIDATE' and not out[7].certified


def test_native_sc_rejects_unsplit_internal_rule_effectivity():
    a,source,posterior,audit,target,contract,sc=setup_sample()
    base=dict(contract=contract,sc_result=sc,target_cells=(target,),params=a['params'],
       ego_geometry=a['ego_geometry'],disturbance=a['disturbance'],resource=a['resource'],
       queue_a=a['queue_a'],queue_b=a['queue_b'],limits=a['limits'],
       permissions_by_parent=permissions(a['parents'][0]),directions_by_actor={'ego':'A'},
       clock_complete=True,complete_actor_roster=True)
    e=ClockEvent('rule-1','RULE_EFFECTIVE',Q(1,2),'model')
    out=native_sc_predecessor_a59_1(source,a['parents'],a['control'],clock_events=(e,),**base)
    assert out[7].status=='UNKNOWN'
    assert 'UNSUPPORTED_INTERNAL_EVENT_IN_NATIVE_SINGLE_TICK_POST' in out[6].reasons
