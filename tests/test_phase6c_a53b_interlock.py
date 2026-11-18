from fractions import Fraction as Q
from dataclasses import replace
import pytest
from rampd_core.a53b_interlock import (ClearanceObservation,BarrierAck,WorkZoneInterlock,advance_interlock)
from test_phase6c_a53_rule_models import ext


def advance(s, e, *, empty=True, complete=True, ack=None):
    return advance_interlock(e,s,ClearanceObservation(s.last_tick,s.last_tick+1,complete,empty,'fixture interval',s.event_id,s.version,s.resource_id),tick=Q(1),clearance=Q(2),ack=ack)


def pending():
    e=ext(); s=WorkZoneInterlock.initial(e,Q(0))
    for _ in range(4): s=advance(s,e)
    assert s.phase=='DEPLOY_PENDING' and s.command_time==4
    return e,s


def ack(s,physical,*,settled=True):
    return BarrierAck(s.event_id,s.version,s.resource_id,s.command_id,s.last_tick+1,physical,settled,'sim sensor/registry fixture')


def test_command_not_ack_and_no_reopen_until_matching_removal():
    e,s=pending()
    assert s.permissions==(False,False)
    s=advance(s,e,ack=replace(ack(s,'PRESENT'),command_id='stale'))
    assert s.phase=='DEPLOY_PENDING'
    s=advance(s,e,ack=ack(s,'PRESENT'));assert s.phase=='BLOCKED'
    s=advance(s,e);s=advance(s,e);assert s.phase=='REMOVE_PENDING'
    s=advance(s,e,ack=ack(s,'ABSENT',settled=False));assert s.phase=='REMOVE_PENDING'
    s=advance(s,e,ack=ack(s,'ABSENT'));assert s.phase=='OPEN'


def test_pending_deploy_expiry_requires_cancel_and_settled_absence():
    e,s=pending(); old=s.command_id
    while s.last_tick<8: s=advance(s,e)
    assert s.phase=='REMOVE_PENDING' and s.command_id!=old
    s=advance(s,e,ack=replace(ack(s,'ABSENT'),command_id=old));assert s.phase=='REMOVE_PENDING'
    assert advance(s,e,ack=ack(s,'ABSENT')).phase=='OPEN'


def test_no_clearance_from_incomplete_interval_or_nonempty():
    e=ext(); s=WorkZoneInterlock.initial(e,Q(0));s=advance(advance(s,e),e)
    s=advance(s,e);assert s.empty_since==2
    s=advance(s,e,empty=False,complete=False);assert s.empty_since is None
    s=advance(s,e);assert s.phase=='DRAIN'
    s=advance(s,e,empty=False);assert s.empty_since is None
    with pytest.raises(ValueError): ClearanceObservation(Q(0),Q(1),False,True,'fixture')


def test_misaligned_activation_and_new_version_fail_closed():
    e=replace(ext(),effective_on=Q(3,2));s=WorkZoneInterlock.initial(e,Q(0));s=advance(s,e)
    with pytest.raises(ValueError,match='split tick'): advance(s,e)
    with pytest.raises(ValueError,match='reconciliation'): advance(s,replace(e,version=2))


def test_intrusion_during_deployment_aborts_even_with_present_ack():
    e,s=pending(); s=advance(s,e,empty=False,ack=ack(s,'PRESENT'))
    assert s.phase=='REMOVE_PENDING' and s.permissions==(False,False)
    s=advance(s,e,ack=ack(s,'ABSENT'))
    assert s.phase=='DRAIN' and s.permissions==(False,True)
