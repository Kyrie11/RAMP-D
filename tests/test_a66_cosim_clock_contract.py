from fractions import Fraction as Q
from dataclasses import replace
import pytest
from rampd_core.a66_cosim_clock_contract import CoupledTick, audit_coupled_tick_trace

D='c'*64

def ticks():
    return tuple(CoupledTick(i,Q(i,20),100+i,Q(i,20),80+i,Q(i,20),
                             'bridge','CARLA','SUMO',2,2,True,True,True) for i in range(4))

def audit(rows):return audit_coupled_tick_trace(rows,dt=Q(1,20),required_tick_owner='bridge',map_registration_sha256=D)

def test_declared_clock_contract_not_physical_certificate():
    r=audit(ticks())
    assert r['status']=='CONDITIONAL_DECLARED_CO_SIM_TRACE_CONSISTENT_NOT_CERTIFIED'
    assert r['safe_training_labels_allowed'] is False
    assert r['signal_ack_physically_observed'] is False

def test_unauthorized_second_tick_owner_rejected():
    t=list(ticks());t[2]=replace(t[2],tick_owner='foreign_client')
    assert 'SIMULATOR_OR_CONTROLLER_OWNERSHIP_MISMATCH' in audit(tuple(t))['reasons']

def test_step_skips_fail():
    t=list(ticks());t[2]=replace(t[2],sumo_step=900)
    assert 'DUPLICATED_OR_SKIPPED_SIMULATOR_TICK' in audit(tuple(t))['reasons']

def test_offset_and_skew_fail():
    t=list(ticks());t[1]=replace(t[1],carla_time=Q(11,100))
    assert 'SYNCHRONOUS_TIME_ALIGNMENT_MISSING' in audit(tuple(t))['reasons']

def test_missing_ack_rejects_entry_but_allows_nonentry_as_unknown_ack():
    t=list(ticks());t[1]=replace(t[1],ack_version=None)
    assert 'ENTRY_BEFORE_EFFECTIVE_SIGNAL_ACK' in audit(tuple(t))['reasons']
    t[1]=replace(t[1],requested_resource_entry=False)
    assert 'ENTRY_BEFORE_EFFECTIVE_SIGNAL_ACK' not in audit(tuple(t))['reasons']

def test_shared_resource_permission_and_clearance_both_mandatory():
    t=list(ticks());t[1]=replace(t[1],permission_open=False,resource_clear=False)
    r=audit(tuple(t))
    assert 'ENTRY_WITH_PERMISSION_CLOSED' in r['reasons']
    assert 'ENTRY_WHILE_RESOURCE_NOT_CLEAR' in r['reasons']

def test_reject_unsupported_time_types_and_ack_rollback():
    with pytest.raises(ValueError):replace(ticks()[0],carla_time=0.0)
    t=list(ticks());t[2]=replace(t[2],ack_version=1)
    assert 'SIGNAL_ACK_VERSION_ROLLBACK' in audit(tuple(t))['reasons']

def test_map_registration_mandatory_and_not_proof():
    r=audit_coupled_tick_trace(ticks(),dt=Q(1,20),required_tick_owner='bridge')
    assert 'MAP_ALIGNMENT_NOT_DECLARED' in r['reasons']

def test_silent_missing_ack_does_not_hide_regression():
    t=list(ticks())
    t[1]=replace(t[1],ack_version=None,requested_resource_entry=False)
    t[2]=replace(t[2],ack_version=1,requested_resource_entry=False)
    assert 'SIGNAL_ACK_VERSION_ROLLBACK' in audit(tuple(t))['reasons']

def test_skipped_command_version_requires_explicit_event_slab():
    t=list(ticks())
    t[2]=replace(t[2],command_version=4,ack_version=2,requested_resource_entry=False)
    assert 'COMMAND_VERSION_SKIPPED_WITHOUT_EVENT_SLAB' in audit(tuple(t))['reasons']

def test_nonnegative_simulator_clocks_are_required():
    with pytest.raises(ValueError):replace(ticks()[0],carla_time=Q(-1,20))
