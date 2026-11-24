import copy,json,sys,dataclasses,types
from pathlib import Path
from fractions import Fraction as Q
import pytest
from rampd_core.a73_joint_reference import contact,safe_edge,solve
from rampd_core.a73_native_context import audit_context
from rampd_core.a73_physics import diagnose,campaign
from rampd_core.a73_guard_trace import audit_trace
from rampd_core.a73_auxiliary import export,MASKS
from rampd_core.a71_native_polygon_geometry import polygon_vertices
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
from a73_roadwork_site_split import strict_split
from a72_probe_real_waymax_scenes import run

def b(x,y=0):return [x,y,x+1,y+1]
def guard(**kw):return dict(entry=True,stay=True,exit=True,ack=True,version=1,ack_version=1,directions=['east','west','stationary'],capacity=1,**{})|kw

def state(x,y=0,other=20,accept=False):return dict(actors={'ego':b(x,y),'other':b(other,0)},legal=True,task_accept=accept)

def model():
    states={'A':state(0),'B':state(0),'a':state(2),'b':state(2),'ga':state(8,accept=True),'gb':state(8,accept=True),'dead':state(2)}
    g={'r':guard()};bad={'r':guard(entry=False)}
    # A and B cannot use different actions at the same observation history.
    def row(t,o='silent',G=g):return dict(to=t,observations=[o],guards=G)
    edges={s:{a:[row(s)] for a in ('advance','left','right')} for s in states}
    edges['A']['advance']=[row('a','A')];edges['B']['advance']=[row('b','B')]
    edges['a']['left']=[row('ga')];edges['a']['right']=[row('dead')]
    edges['b']['right']=[row('gb')];edges['b']['left']=[row('dead')]
    return dict(states=states,actions=['advance','left','right'],roster=['ego','other'],ego='ego',resources={'r':[4,-1,5,2]},conflicts=[],initial=['A','B'],goal=[7,-1,10,2],edges=edges)

def test_mid_interval_contact():assert contact(b(0),b(10),b(5),b(5))==(Q(2,5),Q(3,5))
def test_moving_pair_collision():assert contact(b(0),b(10),b(10),b(0))==(Q(9,20),Q(11,20))
def test_disjoint():assert contact(b(0),b(10),b(5,3),b(5,3)) is None
def test_touch():assert contact(b(0),b(4),b(5),b(5))==(Q(1),Q(1))
def test_guard_midstep_closed():
    why,_=safe_edge(state(0),state(8),{'r':[4,-1,5,2]},{'r':guard(entry=False)},[],['ego','other']);assert 'GUARD:r:ego' in why
@pytest.mark.parametrize('field,value',[('ack',False),('ack_version',0),('stay',False),('exit',False),('capacity',0),('directions',['west'])])
def test_guard_failures(field,value):assert safe_edge(state(0),state(8),{'r':[4,-1,5,2]},{'r':guard(**{field:value})},[],['ego','other'])[0]
def test_capacity_simultaneous_noncolliding():
    s=state(0);s['actors']['other']=b(0,2);t=state(8);t['actors']['other']=b(8,2)
    assert 'CAPACITY:r' in safe_edge(s,t,{'r':[4,-1,5,4]},{'r':guard()},[],['ego','other'])[0]
def test_conflict():
    s=state(0);s['actors']['other']=b(0,3);t=state(8);t['actors']['other']=b(8,3)
    assert 'RESOURCE_CONFLICT:r:s' in safe_edge(s,t,{'r':[4,-1,5,2],'s':[4,3,5,5]},{'r':guard(),'s':guard()},[('r','s')],['ego','other'])[0]
def test_observed_branch_rank():
    r=solve(model(),2);assert r['status']=='CONDITIONAL_FINITE_TRANSLATION_WIN';p=r['policy'];assert p['rank']==2 and p['children']['A']['action']=='left' and p['children']['B']['action']=='right'
def test_silence_merges_worlds():
    m=model();m['edges']['A']['advance'][0]['observations']=['silent'];m['edges']['B']['advance'][0]['observations']=['silent'];assert solve(m,2)['policy'] is None
def test_multiple_observations_no_optimistic_pruning():
    m=model();m['edges']['A']['advance'][0]['observations'].append('ambiguous');m['edges']['B']['advance'][0]['observations'].append('ambiguous');assert solve(m,2)['policy'] is None
def test_budget_unknown():assert solve(model(),2,budget=1)['status']=='UNKNOWN_BUDGET'
def test_missing_action_rejected():
    m=model();del m['edges']['A']['left'];
    with pytest.raises(ValueError):solve(m,2)
def test_missing_actor_rejected():
    m=model();del m['states']['a']['actors']['other'];
    with pytest.raises(ValueError):solve(m,2)
def test_not_goal_even_if_task_accept():
    m=model();m['states']['A']['task_accept']=True;m['initial']=['A'];assert solve(m,0)['policy'] is None
def test_native_context_horizon():
    c=dict(params={},control=[[0,0]]*2,derivative_disturbance=[[0,0]]*6,initial=[[0,0]]*6,horizon_hex=(.5).hex(),segments=[dict(start_time_exact=['0','1'],end_time_exact=['1','2'],initial=[[0,0]]*6,endpoint=[[0,0]]*6)])
    k=('A',Q(0),Q(1,2));d=dict(params={},control=[[0,0]]*2,disturbance=[[0,0]]*6,initial=[[0,0]]*6);assert audit_context({k:c},{k:d})==[]
    c['horizon_hex']=(.25).hex();assert audit_context({k:c},{k:d})
def test_native_wrong_control():
    k=('A',Q(0),Q(1,2));c=dict(params={},control=[[0,0]]*2,derivative_disturbance=[[0,0]]*6,initial=[[0,0]]*6,horizon_hex=(.5).hex());d=dict(params={},control=[[1,1]]*2,disturbance=[[0,0]]*6,initial=[[0,0]]*6);assert 'physical context mismatch' in audit_context({k:c},{k:d})[0]
def test_polygon_backtracking():
    with pytest.raises(ValueError):polygon_vertices([(0,0),(3,0),(2,0),(3,3),(0,3)])
def sample_report():return dict(source_family='511NY',status='DESCRIPTIVE_REPORT_TIMES_ONLY',formal_label_masks=MASKS.copy(),reported_facility=' I-87 ',reported_organization='A',reported_create_time='2014-01-01T00:00:00+00:00',event_type_as_reported='Accident',source_dataset_sha256='abc',source_event_id='row1')
def test_group_across_year_and_source():
    x=sample_report();y=dict(x,source_dataset_sha256='def',reported_create_time='2015-02-01T00:00:00+00:00',reported_organization='B');r=export([x,y]);assert r['counts']['families']==1 and r['rows'][0]['partition']==r['rows'][1]['partition']
@pytest.mark.parametrize('patch',[{'event_type_as_reported':'531'},{'formal_label_masks':{}},{'formal_label_masks':{'L_event':1}}])
def test_aux_quarantine(patch):assert export([sample_report()|patch])['counts']['quarantined']==1

def test_strict_site_group_exclusion():
    val=[dict(group='v',image_id=1,gps=[40,-74])];train=[dict(group='a',image_id=2,gps=None),dict(group='a',image_id=3,gps=[42,-74]),dict(group='b',image_id=4,gps=[43,-74]),dict(group='c',image_id=5,gps=[40,-74])];tr,_,q,_=strict_split(train,val);assert [x['group'] for x in tr]==['b'] and len(q)==3

def test_waymax_config_dataclass(monkeypatch,tmp_path):
    import numpy as np
    @dataclasses.dataclass(frozen=True)
    class C:
        path:str='old';max_num_objects:int=0;repeat:int=0;num_shards:int=0;batch_dims:tuple=();deterministic:bool=False;shuffle_seed:object=None
    t=types.SimpleNamespace(valid=np.ones((2,3),bool),x=np.zeros((2,3)),y=np.zeros((2,3)),vel_x=np.zeros((2,3)),vel_y=np.zeros((2,3)))
    s=types.SimpleNamespace(log_trajectory=t,object_metadata=types.SimpleNamespace(object_types=np.array([1,1]),is_sdc=np.array([1,0])))
    def gen(config):assert config.repeat==1 and config.path==str(f);return iter([s])
    monkeypatch.setitem(sys.modules,'waymax',types.SimpleNamespace(config=types.SimpleNamespace(WOD_1_3_1_VALIDATION=C()),dataloader=types.SimpleNamespace(simulator_state_generator=gen)))
    f=tmp_path/'shard';f.write_bytes(b'test');r=run(f,1);assert r['real_records'][0]['consecutive_valid_actor_pairs']==4 and not r['real_records'][0]['official_scenario_id_verified']

def trace():
    return dict(dt='1/10',map_sha256='m',registry_sha256='r',roster=['ego'],resources={'r':[3,-1,4,2]},ticks=[dict(time=str(Q(i,10)),tick=i,effective='0',issue='0',readback='0',version=1,readback_version=1,command='open',observed_execution='open',actors={'ego':b(i*3)},permissions={'r':dict(capacity=1,entry=True,stay=True,exit=True)},reported_occupancy={'r':['ego'] if i==1 else []}) for i in range(3)])
def test_guard_trace():assert audit_trace(trace())['status']=='DESCRIPTIVE_DECLARED_SAMPLED_CHAIN'
@pytest.mark.parametrize('key,value',[('observed_execution','closed'),('readback_version',0),('reported_occupancy',{'r':[]}),('time','1/2')])
def test_guard_trace_mutation(key,value):
    t=trace();t['ticks'][1][key]=value;assert audit_trace(t)['status']=='REVIEW'

def test_physics_historical_pure():
    d=json.loads((ROOT/'tests/fixtures/a71_carla_brakeonly_b015.json').read_text());r=diagnose(d,.15,'pure');assert r['regimes']['moving']['n']>0 and not r['guaranteed_brake']
def test_physics_every_repeat_validated():
    d=json.loads((ROOT/'tests/fixtures/a71_carla_brakeonly_b015.json').read_text());e=copy.deepcopy(d);e['actor_id']=999;report=campaign({(.15,'pure'):[d,e]},levels=(.15,),repeats=2);assert any('reused sampled trace' in x for x in report['errors'])

from rampd_core.a73_native_multi_actor import geometry_guard_screen

def tube(x,y):return {'segments':[{'tube':[[x,x],[y,y],[0,0],[0,0],[0,0],[0,0]]}]}
def test_native_geometry_separation_and_occupancy():
    cs={'ego':tube(0,0),'other':tube(20,0)};g={a:(2,1,0,0) for a in cs};r={'r':[[-1,-1],[1,-1],[1,1],[-1,1]]};gs={'r':guard(all_directions=True)}
    x=geometry_guard_screen(cs,g,r,gs,[]);assert not x['reasons'] and x['may_occupy']['r']==['ego'] and not x['actual_occupancy_known']
    gs['r']['entry']=False;assert geometry_guard_screen(cs,g,r,gs,[])['reasons']
def test_native_geometry_near_actor_unknown():
    cs={'ego':tube(0,0),'other':tube(1,0)};g={a:(2,1,0,0) for a in cs};assert any('POSSIBLE_ACTOR_CONTACT' in x for x in geometry_guard_screen(cs,g,{}, {},[])['reasons'])
def test_native_geometry_capacity_unknown():
    cs={'ego':tube(0,0),'other':tube(20,0)};g={a:(2,1,0,0) for a in cs};r={'r':[[-1,-1],[21,-1],[21,1],[-1,1]]};gs={'r':guard(all_directions=True)};assert 'POSSIBLE_CAPACITY_VIOLATION:r' in geometry_guard_screen(cs,g,r,gs,[])['reasons']
from a73_review_sumo_metric import vehicle_polygon

def test_sumo_front_bumper_not_center():
    r=dict(front_bumper_xy=[10,0],angle_navigation_deg=90,length_m=4,width_m=2)
    assert vehicle_polygon(r).bounds==pytest.approx((6,-1,10,1))

def test_sumo_front_bumper_north():
    r=dict(front_bumper_xy=[0,10],angle_navigation_deg=0,length_m=4,width_m=2)
    assert vehicle_polygon(r).bounds==pytest.approx((-1,6,1,10))
