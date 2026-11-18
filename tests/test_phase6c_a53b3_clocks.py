from fractions import Fraction as Q
from dataclasses import replace
import pytest
from rampd_core.a53b_event_clock import *
from rampd_core.a53_schedule import PermissionEpoch
from test_phase6c_a53b_interlock import pending,advance

def test_uncertain_switch_meet_contains_every_sampled_actual_rule():
    a=PermissionEpoch('r',Q(0),Q(6),True,True,'forward',2,'old')
    b=replace(a,alpha=False,direction='reverse',capacity=1,source_ref='new')
    s=uncertain_switch_schedule(Q(0),Q(5),Q(6),a,b,Q(1),Q(3),'interval model')
    assert s.permission_at(Q(0))['r']==(True,True,'forward',2)
    assert s.permission_at(Q(1))['r']==(False,True,'NO_COMMON_DIRECTION',1)
    assert s.permission_at(Q(3))['r']==(False,True,'reverse',1)
    for t in (Q(i,4) for i in range(21)):
        actual=[a if t<q else b for q in (Q(i,4) for i in range(4,13))]
        alpha,beta,d,c=s.permission_at(t)['r']
        assert all((not alpha or e.alpha) and (not beta or e.beta) and c<=e.capacity and (d=='NO_COMMON_DIRECTION' or d==e.direction) for e in actual)

def test_message_silence_never_uses_hidden_issue_or_future_receipt():
    w=[MessageWorld('no-issue','m','p',None,None,'fixture'),MessageWorld('drop','m','p',Q(1),None,'fixture'),MessageWorld('late','m','p',Q(1),Q(4),'fixture'),MessageWorld('early','m','p',Q(1),Q(2),'fixture')]
    assert len(partition_message_worlds(w,Q(1)))==1
    p=partition_message_worlds(w,Q(2));assert set(p[('SILENCE',)])=={'no-issue','drop','late'}
    assert p['RECEIVED','m','p',Q(2)]==('early',)
    assert set(partition_message_worlds(w,Q(4))[('SILENCE',)])=={'no-issue','drop'}

def test_clock_labels_do_not_impute_missing_as_zero():
    assert sampled_onset(Q(1),Q(2),False,True,complete=True,source_ref='frame').kind=='AT_LEAST_ONE_ONSET_BRACKET'
    assert sampled_onset(Q(1),Q(2),False,True,complete=False,source_ref='frame').kind=='UNKNOWN'
    assert receipt_label(None,Q(3),None,monitoring_complete=True,source_ref='log').kind=='UNKNOWN'
    assert receipt_label(Q(1),Q(3),None,monitoring_complete=False,source_ref='log').kind=='UNKNOWN'
    assert receipt_label(Q(1),Q(3),None,monitoring_complete=True,source_ref='log').kind=='RIGHT_CENSORED_RECEIPT'
    with pytest.raises(ValueError): receipt_label(Q(2),Q(3),Q(1),monitoring_complete=True,source_ref='log')

def test_same_version_changed_rule_rejected_but_physical_ack_fields_not_binding():
    e,s=pending()
    with pytest.raises(ValueError,match='reconciliation'): advance(s,replace(e,effective_off=Q(9)))
    assert advance(s,replace(e,physical_change=Q(4))).phase=='DEPLOY_PENDING'

def test_actuated_clearance_requires_complete_intervals():
    from rampd_core.a53b_alternating import ContinuousAlternating
    from rampd_core.a53_rule_models import AlternatingConfig,FlowSnapshot
    from rampd_core.a53b_interlock import ClearanceObservation
    c=ContinuousAlternating.initial('ctrl',1,'lane',AlternatingConfig(Q(1),Q(1),Q(4),Q(2),1))
    def step(c,complete=True,empty=True,occupants=0):
        t=c.state.last_tick
        return c.advance(FlowSnapshot(t+1,0,5,occupants),ClearanceObservation(t,t+1,complete,empty,'fixture','ctrl',1,'lane'))
    c=step(c);assert c.state.phase=='A_DRAIN' and c.state.empty_since is None
    c=step(c,False,False);assert c.state.empty_since is None
    c=step(c);assert c.state.empty_since==2
    c=step(c,False,False);assert c.state.empty_since is None
    c=step(c);assert c.state.phase=='A_DRAIN'
    assert step(c).state.phase=='B_GREEN'
    with pytest.raises(ValueError,match='disagree'): step(c,occupants=1)

def test_mutcd_table_two_way_range_and_sight_distance_units():
    from rampd_core.a53b_ttc import taper_guidance_m,stopping_sight_table_m
    assert taper_guidance_m('ONE_LANE_TWO_WAY',Q('3.6'),Q(30))==(Q('15.24'),Q('30.48'))
    assert taper_guidance_m('SHIFTING',Q('3.6'),Q(30))==(Q(27),None)
    assert stopping_sight_table_m(Q(30))==Q('60.96')
    with pytest.raises(ValueError): stopping_sight_table_m(Q(42))

def test_confirmed_drop_not_a_numeric_delay():
    r=receipt_label(Q(1),Q(3),None,monitoring_complete=True,source_ref='channel terminal log',confirmed_drop=True)
    assert r.kind=='CONFIRMED_MODEL_DROP' and r.lower is r.upper is None
    with pytest.raises(ValueError):receipt_label(Q(1),Q(3),Q(2),monitoring_complete=True,source_ref='bad',confirmed_drop=True)
