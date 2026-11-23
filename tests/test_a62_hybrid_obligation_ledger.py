from __future__ import annotations
from dataclasses import replace
from fractions import Fraction as Q
from rampd_core.a60_clock_resource import ClockEvent
from rampd_core.a61_hybrid_partition import ClockWorld,partition_clock_worlds
from rampd_core.a62_hybrid_obligation_ledger import WorldSlabEvidence,audit_world_slab_ledger
import pytest


def gate():
    a=ClockWorld('a',(ClockEvent('e','RULE_EFFECTIVE',Q(1,2),'synthetic','', 'EXACT_MODEL'),),(),True,'h')
    b=ClockWorld('b',(),(),True,'h')
    return partition_clock_worlds((a,b),start=Q(0),end=Q(1))


def records():
    return tuple(WorldSlabEvidence(w,lo,hi,'common_control',
       'native-'+w,'guard-'+w,'resource-'+w,'obs-'+w)
       for lo,hi in ((Q(0),Q(1,2)),(Q(1,2),Q(1))) for w in ('a','b'))


def test_both_hidden_worlds_each_slab_must_have_physical_evidence():
    g=gate();out=audit_world_slab_ledger(g,records())
    assert out['world_slabs_required']==4
    assert out['rows_received']==4
    assert out['status']=='UNKNOWN' and out['unclosed_obligations']
    assert not out['sc_certified'] and not out['label_viability_allowed']


def test_missing_hidden_world_cannot_be_treated_as_support_complete():
    out=audit_world_slab_ledger(gate(),records()[:-1])
    assert any('MISSING_WORLD_SLAB:b' in x for x in out['reasons'])


def test_preobservation_different_control_rejected_despite_both_native_refs():
    rs=list(records());rs[1]=replace(rs[1],public_control_id='clairvoyant_b')
    out=audit_world_slab_ledger(gate(),tuple(rs))
    assert any('NONANTICIPATIVE_PUBLIC_CONTROL_VIOLATION' in x for x in out['reasons'])


def test_even_all_paper_flags_do_not_authenticate_native_proofs():
    flags=dict(tube_replayed=True,guard_authority_replayed=True,
      resource_topology_replayed=True,observation_support_replayed=True,
      task_tail_replayed=True)
    rs=tuple(replace(r,**flags) for r in records())
    out=audit_world_slab_ledger(gate(),rs)
    assert out['status']=='CONDITIONAL_COMPLETE_WORLD_SLAB_OBLIGATION_TABLE_NOT_CERTIFIED'
    assert not out['all_replays_independently_authenticated']
    assert not out['label_deadline_allowed']


def test_duplicate_and_wrong_time_records_rejected():
    rs=records();o=audit_world_slab_ledger(gate(),rs+(rs[0],))
    assert any('DUPLICATE_WORLD_SLAB' in x for x in o['reasons'])
    wrong=replace(rs[0],start=Q(1,8))
    o=audit_world_slab_ledger(gate(),(wrong,)+rs[1:])
    assert any('EXTRANEOUS_OR_WRONG_TIME' in x for x in o['reasons'])


def test_incomplete_clock_support_cannot_generate_tasks():
    g=partition_clock_worlds((ClockWorld('a',(),(),False,'h'),),start=Q(0),end=Q(1))
    out=audit_world_slab_ledger(g,(WorldSlabEvidence('a',Q(0),Q(1),'common'),))
    assert 'PARTITION_NOT_READY' in out['reasons']


def test_typed_replay_statuses_require_actual_boolean():
    with pytest.raises(TypeError):
        WorldSlabEvidence('a',Q(0),Q(1),'ctrl',tube_replayed='PASS')
