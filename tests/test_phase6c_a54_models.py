from fractions import Fraction as Q
from dataclasses import replace
import pytest
from rampd_core.a54_message_mission import DeclaredHistory,compile_histories
from rampd_core.a53b_event_clock import MessageWorld
from rampd_core.a53_schedule import PermissionSchedule,PermissionEpoch,local_protocol
from rampd_core.a54_signal import SignalPlan,SignalController
from rampd_core.a53_rule_models import FlowSnapshot
from rampd_core.a53b_interlock import ClearanceObservation,advance_interlock
from test_phase6c_a53b_interlock import pending


def histories():
    before=PermissionEpoch('r',Q(0),Q(5),True,True,'forward',1,'declared')
    a=PermissionSchedule(Q(0),Q(4),('r',),(before,))
    b=PermissionSchedule(Q(0),Q(4),('r',),(replace(before,off=Q(1,2)),replace(before,on=Q(1,2),alpha=False)))
    return (DeclaredHistory('open',a),DeclaredHistory('closed-drop',b,(MessageWorld('drop','m','close',Q(0),None,'fixture'),)),DeclaredHistory('closed-late',b,(MessageWorld('late','m','close',Q(0),Q(3,2),'fixture'),)))


def test_history_compiler_no_hidden_observation_and_persistent_worlds():
    m=compile_histories(histories(),Q(1)); p=m.protocol
    first=p.outgoing(p.initial_state_id)
    assert len(first)==3 and {e.observation for e in first}=={'silence'}
    second=[p.outgoing(e.target_state_id)[0] for e in first]
    assert len([e for e in second if e.observation=='silence'])==2
    assert len([e for e in second if e.observation.startswith('ingress:')])==1
    assert all(len(p.outgoing(e.target_state_id))==1 for e in second)
    assert len(m.branch_schedules)==12
    assert local_protocol(p,[e.target_state_id for e in first],Q(1),Q(2),m.manifest_digest).transitions
    assert m.manifest_digest==compile_histories(reversed(histories()),Q(1)).manifest_digest


def test_history_compiler_rejects_past_message_and_noninteger_grid():
    h=histories()[0]
    with pytest.raises(ValueError,match='pre-root'): replace(h,messages=(MessageWorld('w','m','payload',Q(0),Q(0),'ref'),))
    with pytest.raises(ValueError,match='tile'):compile_histories(histories(),Q(3,2))
    with pytest.raises(ValueError,match='unique'):compile_histories((h,h),Q(1))


def test_multiple_receipts_at_one_boundary_and_manifest_binding():
    h=histories()[0]; a=MessageWorld('w','m1','p',Q(0),Q(1,3),'r'); b=MessageWorld('w','m2','q',Q(0),Q(2,3),'r')
    h1=replace(h,messages=(a,b)); h2=replace(h,messages=(b,a))
    assert h1.observation(Q(0),Q(1))==h2.observation(Q(0),Q(1))
    assert compile_histories((h1,),Q(1)).manifest_digest==compile_histories((h2,),Q(1)).manifest_digest
    assert h1.observation(Q(1),Q(2))=='silence'
    assert compile_histories((h1,),Q(1)).manifest_digest!=compile_histories((replace(h,messages=(a,)),),Q(1)).manifest_digest


def test_signal_yellow_red_clearance_no_conflicting_green():
    p=SignalPlan(Q(1),Q(2),Q(4),Q(3),Q(5),Q(2),1,'declared engineering fixture')
    s=SignalController.initial('signal',1,'r',p)
    def step(s,complete=True,empty=True):
        t=s.last_tick; return s.advance(FlowSnapshot(t+1,0,4,0 if empty else 1),ClearanceObservation(t,t+1,complete,empty,'test','signal',1,'r'))
    s=step(step(s)); assert s.displays==('YELLOW','RED') and s.permissions==(True,True,False,False)
    for _ in range(2): s=step(s); assert s.displays==('YELLOW','RED')
    s=step(s); assert s.displays==('RED','RED') and s.permissions==(False,True,False,False)
    for _ in range(4): s=step(s); assert s.displays==('RED','RED')
    s=step(s,False,False); assert s.displays==('RED','RED') and s.empty_since is None
    s=step(s); assert s.displays==('RED','RED')
    s=step(s); assert s.displays==('RED','GREEN')
    assert p.yellow_guidance_met


def test_signal_plan_no_silent_grid_rounding_or_universal_red_cap():
    with pytest.raises(ValueError):SignalPlan(Q(1),Q(2),Q(4),Q(7,2),Q(9),Q(2),1,'fixture')
    assert SignalPlan(Q(1),Q(2),Q(4),Q(3),Q(30),Q(2),1,'long facility').red_min==30


def test_interlock_clearance_config_bound():
    e,s=pending(); t=s.last_tick
    with pytest.raises(ValueError,match='timing plan'):advance_interlock(e,s,ClearanceObservation(t,t+1,True,True,'test',s.event_id,s.version,s.resource_id),tick=Q(1),clearance=Q(1))


def test_waymax_discrete_reference_different_from_continuous_arc():
    import importlib.util,math
    from pathlib import Path
    spec=importlib.util.spec_from_file_location('wm_dynamics',Path(__file__).resolve().parents[1]/'scripts/probe_waymax_dynamics.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
    assert m.reference(0,0,0,10,0,2,0,.1)[:3]==pytest.approx((1.01,0,0))
    assert m.exact_arc(0,0,0,10,0,.1,.1)==pytest.approx((math.sin(.1)/.1,(1-math.cos(.1))/.1,.1))
    assert m.reference(0,0,0,10,0,0,.1,.1)[:3]==pytest.approx((1,0,.1))
    with pytest.raises(ValueError): m.exact_arc(0,0,0,.1,-3,0,.1)
    assert m.reference(0,0,0,.1,0,-3,0,.1)[3]<0


def test_gate_preflight_stderr_reported(tmp_path):
    import os,subprocess,json
    from pathlib import Path
    gate=Path(__file__).resolve().parents[1]/'scripts/validate_phase6c_a5_3b4.sh'
    fake=tmp_path/'fakepython';fake.write_text('#!/bin/sh\necho intentional-preflight-failure >&2\nexit 17\n');fake.chmod(0o755)
    out=tmp_path/'report'; proc=subprocess.run(['bash',str(gate)],env={**os.environ,'PYTHON_BIN':str(fake),'REPORT_DIR':str(out)},capture_output=True,text=True)
    assert proc.returncode==17
    assert 'intentional-preflight-failure' in (out/'release_integrity.log').read_text()
    result=json.loads((out/'phase6c_a5_3b4_acceptance_summary.json').read_text())
    assert result['stage']=='release_integrity' and result['returncode']==17
