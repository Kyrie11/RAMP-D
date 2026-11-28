import copy
import pytest
import torch
from rampd_core.learning.relation_context import RelationContext,RelationPilot
from rampd_core.datasets.shared_resource_labels import relation_rows,public_relation_tokens,marked_transition_evidence
from rampd_core.datasets.shared_resource_scenario import simulate
from rampd_core.shared_resource_controller import sampled_polygon_occupancy
from rampd_core.finite_wait_reference import finite_criticality
from rampd_core.datasets.incident_scenarios import enumerate_route_hypotheses,verify_route_source,route_integrity


def test_attention_mask_and_gradient_and_permutation():
    m=RelationContext();x=torch.randn(2,4,5,6,requires_grad=True);mask=torch.ones(2,4,5,dtype=torch.bool);mask[:,1:,4]=False;mask[:,0,1]=False
    z,w=m(x,mask);assert torch.allclose(w.sum(-1),torch.ones(2,4));assert not w[~mask].any();q=x.detach().clone();q[~mask]=float('nan');zz,ww=m(q,mask);assert torch.equal(z,zz) and torch.equal(w,ww)
    z.sum().backward();assert not x.grad[~mask].any();assert torch.isfinite(x.grad).all()
    ix=[2,0,3,1];assert torch.allclose(m(x[:,ix],mask[:,ix])[0],z[:,ix])

@pytest.mark.parametrize('variant',['flat','uniform','gated'])
def test_time_distribution_normalization(variant):
    m=RelationPilot(8,'event',variant);x=torch.randn(3,4,5,6);mask=torch.ones(3,4,5,dtype=torch.bool);p,_=m(x,mask);assert torch.allclose(p.exp().sum(-1),torch.ones(3));(-p[:,0].mean()).backward();assert all(torch.isfinite(v.grad).all() for v in m.parameters() if v.grad is not None)


def test_public_prefix_and_label_scope():
    r=simulate(seed=0,release_delays={'e':3,'a':0,'b':2,'c':1});rows=relation_rows(r,split='training');m=marked_transition_evidence(r,split='validation');assert len(rows)==len(m)==152
    for row,mark in zip(rows,m):
        assert not any(a[4] for a in row['available'][1:]);assert not row['start_mask'][0];assert not any(row['formal_heads'].values());assert mark['mark_valid']['event']==bool(mark['event_time']);assert mark['mark_valid']['observation']==bool(mark['observation_time']);assert mark['training_allowed'] is False
    # Alter hidden other release delays only; same public prefix must give same tokens.
    q=simulate(seed=0,release_delays={'e':3,'a':8,'b':8,'c':8});v=relation_rows(q,split='training');assert rows[0]['tokens']==v[0]['tokens'] and rows[0]['available']==v[0]['available']
    a,b=public_relation_tokens([-10,-16,-10,-16],[0]*4,history_valid=False,ego_signal=None,age=1,public_durations=(16,2));assert a==rows[0]['tokens'] and b==rows[0]['available']


def test_polygon_sample_missing_and_touch():
    rect=[(0,0),(2,0),(2,2),(0,2)];touch=[(2,0),(3,0),(3,1),(2,1)];r=sampled_polygon_occupancy(rect,{'a':touch},['a','b']);assert r['occupancy']=={'a':True,'b':None} and not r['sampled_empty'] and r['prior_swept_empty'] is None
    r=sampled_polygon_occupancy(rect,{'a':touch},['a'],tolerance_m=.01);assert r['occupancy']['a'] is None


def test_branch_hypotheses_cap_and_raw_topology():
    def l(i,x,z,prev,succ):return dict(kind='lane',feature_id=i,vertices=[dict(x=x,y=0),dict(x=z,y=0)],predecessors=prev,successors=succ,attributes={'lane_type':'2'})
    r=dict(scene=dict(map_context=dict(primitives=[l('a',0,20,[],['b','c']),l('b',20,50,['a'],[]),l('c',20,60,['a'],[])])))
    q=dict(lane_id='a',centerline=[[0,0],[20,0]],centerline_length_m=20.)
    result=enumerate_route_hypotheses(r,q,max_paths=1);assert len(result['paths'])==1 and result['unexplored_prefixes']==1 and not result['complete_physical_support'];assert verify_route_source(r,result['paths'][0])['ok']
    bad=copy.deepcopy(r);bad['scene']['map_context']['primitives'][0]['successors']=[];assert not verify_route_source(bad,result['paths'][0])['ok']
    bad=copy.deepcopy(result['paths'][0]);bad['route_segments'][0]['end_m']=float('nan')
    with pytest.raises(ValueError):route_integrity(bad)


def test_rare_world_changes_common_actions():
    q=finite_criticality((5,7),14);row=next(r for r in q['rows'] if r['t']==5 and r['x']==0);assert set(row['viable_actions'])=={'WAIT'};assert next(x for x in row['impacts'] if x['removed_opening']==7)['added_viable_actions']==['GO'];assert q['formal_sc'] is False and q['deadline_is_not_ICG']


def test_public_adapter_identity_missing_and_gradient():
    from rampd_core.learning.relation_context import PublicRelationAdapter
    m=PublicRelationAdapter(16);a=torch.randn(2,4,16);x=torch.randn(2,4,6,16);mask=torch.ones(2,4,6,dtype=torch.bool);mask[:,2]=False;av=torch.ones(2,4,dtype=torch.bool);av[:,3]=False
    z,w=m(a,x,mask,av);assert torch.equal(a,z);z.sum().backward();assert m.residual.weight.grad.abs().sum()>0
    with torch.no_grad():m.residual.weight.fill_(.1)
    z,w=m(a,x,mask,av);assert torch.equal(z[:,2:],a[:,2:]);assert not w[:,2:].any();q=x.clone();q[:,2:]=float('nan');assert torch.equal(z,m(a,q,mask,av)[0])


def test_external_record_holdout_gate():
    from rampd_core.datasets.split_manifest import SCHEMA,validate_external_evaluation
    def r(split,sid,index):return dict(split=split,scenario_id=str(sid),record_sha256=f'{sid:064x}',shard=f'{split}/one.tfrecord',record_index=index)
    a=dict(schema=SCHEMA,scope='BOUNDED_OFFICIAL_DIRECTORY_PILOT',records=[r('training',1,0),r('validation',2,0)])
    b=dict(a,records=[r('training',1,0),r('validation',3,1)])
    assert validate_external_evaluation(a,b)['validation_records']==1
    b['records'][1]=r('validation',4,0)
    with pytest.raises(ValueError):validate_external_evaluation(a,b)
