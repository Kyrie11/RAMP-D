from fractions import Fraction as Q
from dataclasses import replace
from pathlib import Path
import json,sys,zipfile
import pytest
from rampd_core.a54_signal import SignalPlan, SignalController
from rampd_core.a53b_interlock import ClearanceObservation
from rampd_core.a56_guard import GuardCase,GuardParent,advance_support,queue_box_cases
from rampd_core.a53_rule_models import FlowSnapshot
from rampd_core.a56_motion import center_from_rear,idm_net_gap,straight_jerk_step,smooth_stop_profile,arc_friction_ratio
from test_phase6c_a53b2_data_incident import timeline
from test_phase6c_a53b3_roadwork import make,mod
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from extract_roadwork_semantics import extract
from summarize_511ny_lifetimes import summarize
from probe_sumo_alternating import comfortable_switch_ready,Vehicle

def controller():return SignalController.initial('c',1,'r',SignalPlan(Q(1),Q(1),Q(3),Q(1),Q(1),Q(1),1,'fixture',Q(2)))
def evidence(c,complete=True,empty=True):return ClearanceObservation(c.last_tick,c.last_tick+1,complete,empty,'fixture','c',1,'r')
def case(c,k,a,b,obs=('silence',),ready=True):return GuardCase(k,FlowSnapshot(c.last_tick+1,a,b,0),evidence(c),obs,ready)

def test_guard_correlated_cases_no_cartesian_invention():
    c=controller();p=GuardParent('w',c,(case(c,'a',0,0),case(c,'b',2,2)))
    s,out=advance_support((p,));assert s=='NEVER' and len(out['silence'])==2
    s,out=advance_support((GuardParent('w',c,queue_box_cases(c,(0,2),(0,2),evidence(c),occupants=0)),));assert s=='MAY' and len(out['silence'])==9

def test_guard_nondeterministic_public_observation():
    c=controller();p=GuardParent('world1',c,(case(c,'a',0,1,('silence','message')),));q=GuardParent('world2',c,(case(c,'b',0,0),))
    s,out=advance_support((p,q));assert s=='MAY' and len(out['silence'])==2 and len(out['message'])==1
    assert {o.controller.phase for o in out['silence']}=={'A_YELLOW','A_GREEN'}
    with pytest.raises(ValueError):advance_support((p,q),max_cases=2)
    with pytest.raises(ValueError):case(c,'bad',0,0,'silence')

def test_guard_extension_exhaustion_fail_closed():
    c=controller()
    for i in range(4):c=c.advance(FlowSnapshot(c.last_tick+1,0,1,0),evidence(c),switch_ready=False)
    with pytest.raises(RuntimeError):advance_support((GuardParent('w',c,(case(c,'a',0,1,ready=False),case(c,'b',0,1))),))
    assert c.advance(FlowSnapshot(Q(5),0,1,0),evidence(c),switch_ready=True).phase=='A_YELLOW'

def test_exact_smooth_stop_and_internal_reverse():
    rows=smooth_stop_profile(60);assert rows[50]==rows[60]==(Q(25),Q(0),Q(0))
    assert all(v>=0 for _,v,_ in rows)
    with pytest.raises(ValueError):straight_jerk_step(Q(1),Q(-3),Q(3),Q(2))

def test_rigid_reference_and_idm_and_friction():
    assert center_from_rear(0,0,0,10,0.2,1,0)==(1,0,10,.2)
    assert idm_net_gap(10,10,10.5)==pytest.approx(-3.778391,abs=1e-5)
    with pytest.raises(ValueError):idm_net_gap(10,10,0)
    assert arc_friction_ratio(10,0,.1,.1,1)==pytest.approx(10/9.80665)

def test_comfort_screen():
    v={'a':Vehicle('A',198,4.5,8)};b={'A':(200,260),'B':(200,260)}
    assert not comfortable_switch_ready(v,b,'A')[0]
    assert comfortable_switch_ready(v,b,'B')[0]

def test_tim_total_normal_flow():
    t=timeline();assert t.duration('normal_flow') is None
    t=replace(t,incident_occurrence=Q(2));assert t.duration('normal_flow')==16 and t.duration('lanes_available')==10 and t.duration('last_responder_left')==11
    with pytest.raises(ValueError):replace(t,incident_occurrence=Q(5))

def test_roadwork_extract_hash_and_masks(tmp_path):
    make(tmp_path);p=tmp_path/'annotations.zip'
    with zipfile.ZipFile(p) as z:src={n:json.loads(z.read(n)) for n in z.namelist()}
    for d in src.values():d['annotations'][0]['attributes']={'state':'NONE'};d['images'][0]['scene_level_tags']={'active':None}
    with zipfile.ZipFile(p,'w') as z:
        for n,d in src.items():z.writestr(n,json.dumps(d))
    alignment=mod.audit(tmp_path,1);out=extract(tmp_path,tmp_path/'sem',alignment)
    assert out['status']=='VISUAL_SOURCE_EXTRACTION_PASS' and not out['formal_rule_labels_generated']
    rec=json.loads((tmp_path/'sem/train_visual_semantics.jsonl').read_text());assert rec['objects'][0]['source_attributes']=={'state':'NONE'} and rec['scene_level_tags']=={'active':None} and rec['formal_rule_target'] is None
    alignment['splits'][0]['annotation_sha256']='x'
    with pytest.raises(ValueError,match='digest'):extract(tmp_path,tmp_path/'bad',alignment)

def test_511_histogram_bracket_not_exact_quantile():
    r={'status':'BOUNDED_511_REPORT_INVENTORY_PASS','counts':{'rows':4,'ny_road_agency_proxy':4},'groups':{'breakdown':{'rows':4,'nonnegative_report_lifetime':3,'negative_lifetime':1,'zero_lifetime':1,'lifetime_lt_60s':1,'lifetime_lt_300s':1}},'full_scan':True,'timezone_assumption':'test'}
    o=summarize(r)['groups']['breakdown'];assert o['p50']['hi_s']==60 and o['negative_fraction']==.25
    r['groups']['breakdown']['lifetime_lt_60s']=2
    with pytest.raises(ValueError):summarize(r)
