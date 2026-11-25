from fractions import Fraction as Q
from copy import deepcopy
from pathlib import Path
import sys,types
import pytest
from rampd_core.a74_successor import merge_endpoint_support
from rampd_core.a73_joint_reference import safe_edge
from rampd_core.a73_guard_trace import audit_trace
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from a74_roadwork_bind_split import bind
from a74_womd_format_probe import classify
from test_a73 import guard,state,trace

def fixture():
    b=[[0,0]]*6;c={'segments':[dict(start_time_exact=['0','1'],end_time_exact=['1','2'],initial=b,endpoint=b)]};ks=[('A',Q(0),Q(1,2)),('B',Q(0),Q(1,2))];cs={a:{k:c for k in ks} for a in ('ego','other')};o={w:[dict(observation='silent',atom=w,latent=w)] for w in ('A','B')};t={'silent':{w:dict(latent=w,actors={a:b for a in cs}) for w in o}};return cs,o,t

def test_union():
    c,o,t=fixture();assert merge_endpoint_support(c,o,t,['ego','other'],end=Q(1,2))=={'silent':['A','B']}
@pytest.mark.parametrize('mutation',['missing_world','missing_actor','missing_child','missing_observation','wrong_latent','undercover','alias'])
def test_reject(mutation):
    c,o,t=deepcopy(fixture())
    if mutation=='missing_world':o.pop('A')
    elif mutation=='missing_actor':c.pop('other')
    elif mutation=='missing_child':t['silent'].pop('B')
    elif mutation=='missing_observation':t.clear()
    elif mutation=='wrong_latent':t['silent']['B']['latent']='A'
    elif mutation=='undercover':t['silent']['B']['actors']['ego']=[[1,1]]*6
    elif mutation=='alias':o['B'][0]['atom']='A'
    with pytest.raises(ValueError):merge_endpoint_support(c,o,t,['ego','other'],end=Q(1,2))

def test_touch_at_start_guard():
    # touch at start and enter immediately; no established previous occupancy
    reasons,_=safe_edge(state(0),state(2),{'r':[1,-1,4,2]},{'r':guard(entry=False)},[],['ego','other']);assert 'GUARD:r:ego' in reasons

def test_command_epoch_independent():
    t=trace()
    for i,r in enumerate(t['ticks']):r.update(command_epoch=i,readback_epoch=i,command=str(i),observed_execution=str(i))
    assert audit_trace(t)['status']=='DESCRIPTIVE_DECLARED_SAMPLED_CHAIN'
    t['ticks'][1]['readback_epoch']=0;assert audit_trace(t)['status']=='REVIEW'

def test_split_lineage():
    r={'group':'a','image_id':1,'file_name':'x','source_annotation_sha256':'h'};a={'source_sha256':{'train':'h'}};t={'source':{'source_group':'a','source_image_id':1,'image_file':'x','source_annotation_sha256':'h','source_split':'train'}}
    assert len(bind([t],[r],[],a)[0])==1
    assert not bind([t],[],[],a)[0]
    assert not bind([t],[dict(r,source_annotation_sha256='bad')],[],a)[0]

def test_format_classifier():
    class Bad:
        def ParseFromString(self,p):raise ValueError('not scenario')
    class Example:
        def ParseFromString(self,p):self.features=types.SimpleNamespace(feature={k:None for k in ('state/past/x','state/current/x','state/id')})
    assert classify(b'abc',Bad,Example)['kind']=='TFEXAMPLE_NOT_SCENARIO'
    assert classify(b'abc',Bad,Bad)['kind']=='UNKNOWN_RECORD_FORMAT'

from rampd_core.a74_finite_policy_replay import replay
from rampd_core.a73_joint_reference import solve
from test_a73 import model

def test_independent_policy_replay():
    m=model();p=solve(m,2)['policy'];assert replay(m,p,2)['status']=='CONDITIONAL_FINITE_POLICY_REPLAY'
    p['children'].pop('B');assert replay(m,p,2)['status']=='UNKNOWN'

def test_rank_and_target_mutations():
    m=model();p=solve(m,2)['policy'];p['children']['A']['rank']=2;assert replay(m,p,2)['status']=='UNKNOWN'
    p=solve(m,2)['policy'];m['states']['ga']['task_accept']=False;assert replay(m,p,2)['status']=='UNKNOWN'
