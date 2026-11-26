from fractions import Fraction as Q
from copy import deepcopy
import pytest
from rampd_core.a75_resource import monitor
from rampd_core.a75_wait_game import synthesize,replay,replan,successors
from rampd_core.a75_contract import factual,batch
from rampd_core.a73_native_context import contains

def g(**kw):return dict(dict(entry=True,stay=True,exit=True,ack=True,directions=['A','B'],capacity=2),**kw)
R=(2,0,4,2)
def check(paths,prior=None,directions=None,guard=None,age=0,clearance=0):return monitor(paths,R,prior or {},directions or {a:'A' for a in paths},guard or g(),dt=1,empty_age=age,clearance=clearance)

def test_entry_touch():
    assert not check({'e':((0,0,1,1),(1,0,2,1))},guard=g(entry=False))['ok']
def test_missing_history():
    assert not check({'e':((2,0,3,1),(3,0,4,1))})['ok']
def test_grandfathered_exit():
    r=check({'e':((3,0,4,1),(5,0,6,1))},{'e':'A'},guard=g(entry=False));assert r['ok'] and r['exits']==['e'] and r['empty_age']==Q(1,2)
def test_exit_closed():
    assert not check({'e':((3,0,4,1),(5,0,6,1))},{'e':'A'},guard=g(entry=False,exit=False))['ok']
def test_touch_not_clear():
    r=check({'e':((3,0,4,1),(4,0,5,1))},{'e':'A'});assert r['end_admitted']=={'e':'A'} and not r['empty_age']
def test_swept_through():
    r=check({'e':((0,0,1,1),(5,0,6,1))});assert r['entries']==r['exits']==['e'] and r['spans']['e']==['1/5','4/5']
def test_same_direction_platoon():
    r=check({'a':((2,0,3,1),(3,0,4,1)),'b':((0,1,1,2),(2,1,3,2))},{'a':'A'});assert r['ok']
def test_capacity_opposing():
    paths={'a':((0,0,1,1),(3,0,4,1)),'b':((5,1,6,2),(2,1,3,2))}
    assert 'OPPOSING' in check(paths,directions={'a':'A','b':'B'})['errors']
    assert 'CAPACITY' in check(paths,guard=g(capacity=1))['errors']
def test_clearance():
    assert not check({'e':((0,0,1,1),(2,0,3,1))},clearance=1)['ok']
def test_no_ack():
    assert not check({'e':((0,0,1,1),(2,0,3,1))},guard=g(ack=False))['ok']
def test_wait_and_rank():
    B,p=synthesize();assert p['rank']==12 and p['action']=='WAIT' and replay(B,p,14)==12
    assert synthesize(horizon=11)[1] is None
    for t in range(5):
        out=successors(B,p['action']);obs='SILENCE' if 'SILENCE' in out else 'GREEN';B=out[obs];p=p['children'][obs]
        assert replan(B,p,p)==p

def test_false_goal_and_reset():
    B,p=synthesize();bad={'rank':0,'terminal':True}
    with pytest.raises(ValueError):replay(B,bad,14)
    out=successors(B,p['action']);child=out['SILENCE'];old=p['children']['SILENCE'];bad=deepcopy(old);bad['rank']+=1
    with pytest.raises(ValueError):replan(child,old,bad)
def test_missing_obs():
    B,p=synthesize()
    for _ in range(5):B=successors(B,p['action'])['SILENCE'];p=p['children']['SILENCE']
    p['children'].pop('GREEN')
    with pytest.raises(ValueError):replay(B,p,14)
def test_contains_dimension():assert not contains([(0,1)],[(0,1),(0,1)])

def row():
    t=list(range(12));h='a'*64
    def track(i):return dict(track_id=i,category='vehicle',states=[dict(timestamp=j,x=j,y=0,heading=0,vx=1,vy=0,length=4,width=2,valid=True,observed=j<=1) for j in t])
    return dict(record_sha256=h,scene=dict(manifest=dict(dataset='womd_scenario',scenario_id='s',split='validation',source_digest=h,position_reference='bounding_box_center',coordinate_frame='womd_global_xy',timestamps=t,current_time_index=1,metadata=dict(source_track_count=2,sdc_track_index=0,source_track_indices=[0,1])),tracks=[track('ego'),track('other')]))
def test_scoped_factual():
    r=factual(row());assert r['heads']['joint']['mask'] and not r['heads']['joint']['training_allowed'];assert sum(v['mask'] for v in r['heads'].values())==1
    assert len(r['history'][0]['states'])==2 and len(r['targets'][0]['xy'])==10
@pytest.mark.parametrize('kind',['future','hash','time','duplicate'])
def test_factual_fail_closed(kind):
    r=row()
    if kind=='future':r['scene']['tracks'][0]['states'][2]['observed']=True
    elif kind=='hash':r['record_sha256']='b'*64
    elif kind=='time':r['scene']['manifest']['timestamps'][2]=1
    elif kind=='duplicate':
        with pytest.raises(ValueError):batch([r,r])
        return
    with pytest.raises(ValueError):factual(r)

from rampd_core.a75_rank import tighten

def test_rank_tightens_after_early_progress():
    assert tighten(10,Q(12),3,Q(4))==(3,Q(4))
    assert tighten(3,Q(4),1,Q(1),elapsed=Q(1),executed=True)==(1,Q(1))
    with pytest.raises(ValueError):tighten(1,Q(1),2,Q(1))

def test_rank_time_budget_consumption():
    with pytest.raises(ValueError):tighten(3,Q(4),2,Q(4),elapsed=Q(1),executed=True)
    with pytest.raises(ValueError):tighten(3,Q(4),3,Q(2),elapsed=Q(1),executed=True)
    with pytest.raises(ValueError):tighten(3,Q(4),2,Q(2),elapsed=Q(0),executed=True)

def test_right_continuous_entry_guard():
    p={'e':((0,0,1,1),(1,0,2,1))}
    assert not monitor(p,R,{}, {'e':'A'},g(),dt=1,empty_age=0,endpoint_guard=g(entry=False))['ok']
    assert monitor(p,R,{}, {'e':'A'},g(entry=False),dt=1,empty_age=0,endpoint_guard=g())['ok']

def test_right_endpoint_capacity_and_stay():
    p={'e':((1,0,2,1),(2,0,3,1))}
    r=monitor(p,R,{'e':'A'},{'e':'A'},g(),dt=1,empty_age=0,endpoint_guard=g(stay=False,capacity=0))
    assert 'ENDPOINT_STAY' in r['errors'] and 'CAPACITY' in r['errors']

def test_training_requires_separate_manifest():
    r=row();r['scene']['manifest']['split']='training';assert not batch([r])[0]['heads']['joint']['training_allowed']
    m={'s':{'source_digest':'a'*64,'split':'training'}};assert batch([r],split_manifest=m)[0]['heads']['joint']['training_allowed']
    m['s']['split']='validation'
    with pytest.raises(ValueError):batch([r],split_manifest=m)

def test_effectivity_without_receipt_and_no_guaranteed_opening():
    B,p=synthesize()
    for _ in range(5):
        B=successors(B,p['action'])['SILENCE'];p=p['children']['SILENCE']
    assert {s[0] for s in B}=={5,7} # physical change at t=5 does not reveal the world
    assert synthesize(openings=(5,99),horizon=20)[1] is None
