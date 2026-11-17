from fractions import Fraction as Q
from dataclasses import replace
import pytest
from rampd_core.a53_rule_models import (ExternalReport, FlowSnapshot, AlternatingConfig,
    AlternatingState, advance_alternating, WorkZoneState, advance_work_zone)


def ext():
    return ExternalReport('construction','road authority','declared-test-ODD','lane',1,
                          Q(1),Q(2),Q(8),Q(0),Q(3),'DELIVERED','planned closure')


def test_issue_effectivity_and_receipt_are_distinct_and_visibility_causal():
    e=ext()
    assert e.issue<e.activation<e.effective_on<e.receive
    assert not e.visible_to_ego(Q(5,2)) and e.visible_to_ego(Q(3))
    assert replace(e,physical_change=Q(5)).external_request_signature()==e.external_request_signature()
    with pytest.raises(ValueError): replace(e,receive=Q(-1))
    with pytest.raises(ValueError): replace(e,receive=None)
    assert not replace(e,receive=None,delivery_status='PENDING').visible_to_ego(Q(10))


def test_actuated_switch_requires_min_green_other_queue_and_clearance():
    c=AlternatingConfig(Q(1),Q(2),Q(5),Q(2),2)
    s=AlternatingState('A_GREEN',Q(0),Q(0))
    rows=[]
    for i,n in enumerate((1,1,0,1,0,0,0),1):
        s=advance_alternating(c,s,FlowSnapshot(Q(i),0,4,n));rows.append(s.phase)
        assert not(s.permissions[0] and s.permissions[2])
    assert rows==['A_GREEN','A_DRAIN','A_DRAIN','A_DRAIN','A_DRAIN','A_DRAIN','B_GREEN']


def test_flow_driven_not_every_yield_is_rule_and_same_inputs_same_outputs():
    c=AlternatingConfig(Q(1),Q(2),Q(5),Q(1),2); s=AlternatingState('A_GREEN',Q(0),Q(1))
    low=FlowSnapshot(Q(2),5,0,0); high=replace(low,queue_b=9)
    assert advance_alternating(c,s,low).phase=='A_GREEN'
    assert advance_alternating(c,s,high).phase=='A_DRAIN'
    assert advance_alternating(c,s,high)==advance_alternating(c,s,high)
    with pytest.raises(ValueError): advance_alternating(c,s,replace(low,time=Q(4)))
    with pytest.raises(ValueError): replace(low,occupants=-1)


def test_external_closure_with_deployment_interlock_and_reopening_ack():
    e=ext(); s=WorkZoneState('OPEN',Q(0)); phases=[]
    for t,n in enumerate((1,1,0,1,0,0,0,0,0),1):
        s=advance_work_zone(e,s,FlowSnapshot(Q(t),0,0,n),tick=Q(1),clearance=Q(2),physical_barrier_removed=t==9)
        phases.append(s.phase)
    assert phases==['OPEN','DRAIN','DRAIN','DRAIN','DRAIN','DRAIN','BLOCKED','RELEASE_PENDING','OPEN']
    assert WorkZoneState('DRAIN',Q(1)).permissions==(False,True)


def test_planned_closure_pair_has_same_external_request_but_different_drain_duration():
    e=ext(); results=[]
    for flow in ((0,0,0,0,0),(0,1,1,0,0)):
        s=WorkZoneState('OPEN',Q(0)); times=[]
        for t,n in enumerate(flow,1):
            s=advance_work_zone(e,s,FlowSnapshot(Q(t),0,0,n),tick=Q(1),clearance=Q(1))
            if s.phase=='BLOCKED': times.append(t)
        results.append(times[0])
    assert results==[3,5]
    assert e.external_request_signature()==e.external_request_signature()
