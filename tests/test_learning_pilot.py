"""Pure training tests; mock raw Scenario decoder only in unit fixtures.
No fixture is a real data or safety certificate.
"""
import copy, hashlib, json, math
from pathlib import Path
from fractions import Fraction
from types import SimpleNamespace as Obj
import pytest
import torch
from rampd_core.datasets.split_manifest import build_manifest,stream_records,validate_manifest,canonical_digest
from rampd_core.datasets.feature_contract import build_features
from rampd_core.datasets.factual_dataset import prepare,load_cache
from rampd_core.datasets.rule_overlay import RuleOverlay
from rampd_core.datasets.collate import collate
from rampd_core.learning.joint_decoder import FactualJointModel
from rampd_core.learning.masked_losses import joint_nll,metric_sums
from rampd_core.learning.training import fit,evaluate

@pytest.fixture(autouse=True,scope='module')
def cpu_threads():
    old=torch.get_num_threads();torch.set_num_threads(1);yield;torch.set_num_threads(old)

def proto(sid):
    times=[i/10 for i in range(8)]; k=2
    def track(id,x,y,v,a):
        return Obj(id=id,object_type=1,states=[Obj(valid=True,center_x=x+v*t+.5*a*t*t,center_y=y,heading=0.,velocity_x=v+a*t,velocity_y=0.,length=4.5,width=1.9,height=1.5) for t in times])
    # Lane-like dict accepted by current record adapter, map feature object has WhichOneof in real proto.
    feature=Obj(id=10,lane=Obj(polyline=[Obj(x=-20.,y=0.,z=0.),Obj(x=20.,y=0.,z=0.)],entry_lanes=[],exit_lanes=[],left_neighbors=[],right_neighbors=[]))
    feature.WhichOneof=lambda _: 'lane'
    return Obj(scenario_id=sid,timestamps_seconds=times,current_time_index=k,tracks=[track(1,0.,0.,2.,0.),track(2,5.,0.,1.,7.),track(3,8.,3.,1.,5.)],sdc_track_index=0,tracks_to_predict=[],dynamic_map_states=[],map_features=[feature],objects_of_interest=[])

@pytest.fixture
def source(tmp_path):
    root=tmp_path/'scenario'; raw={}
    for split in ('training','validation'):
        folder=root/split; folder.mkdir(parents=True); p=folder/'part.tfrecord';p.touch();raw[p]=[(split+str(i)).encode() for i in range(2)]
    reader=lambda p:iter(raw[p]); decoder=lambda b:proto(b.decode())
    m=build_manifest(root,train_limit=2,validation_limit=2,reader=reader,decoder=decoder)
    return root,raw,reader,decoder,m

def records(source):
    _,_,read,decode,m=source;return list(stream_records(m,reader=read,decoder=decode))

def features(source):
    return [build_features(r,horizon=5,history_steps=3,max_map=16) for r in records(source)]

def test_manifest_duplicate(source):
    *_,m=source; q=copy.deepcopy(m);q['records'][-1]['scenario_id']=q['records'][0]['scenario_id'];
    with pytest.raises(ValueError,match='duplicate'):validate_manifest(q)

def test_manifest_hash_duplicate(source):
    *_,m=source;q=copy.deepcopy(m);q['records'][-1]['record_sha256']=q['records'][0]['record_sha256'];
    with pytest.raises(ValueError,match='duplicate'):validate_manifest(q)

def test_manifest_path(source):
    *_,m=source;q=copy.deepcopy(m);q['records'][0]['shard']='../bad';
    with pytest.raises(ValueError):validate_manifest(q)

def test_changed_record_rejected(source):
    _,raw,read,decode,m=source; raw[next(iter(raw))][0]=b'changed';
    with pytest.raises(ValueError,match='changed'):list(stream_records(m,reader=read,decoder=decode))

def test_missing_record_rejected(source):
    _,raw,read,decode,m=source;raw[next(iter(raw))].pop();
    with pytest.raises(ValueError,match='missing'):list(stream_records(m,reader=read,decoder=decode))

def test_split_symlink_rejected(source):
    root,_,read,decode,_=source; (root/'validation'/'part.tfrecord').unlink();(root/'validation').rmdir();(root/'validation').symlink_to(root/'training',target_is_directory=True)
    with pytest.raises(ValueError):build_manifest(root,reader=read,decoder=decode,train_limit=2,validation_limit=2)

def test_features_and_frame(source):
    f=features(source)[0]; assert f['actor_ids'][0]==f['ego_id'];assert f['inputs']['history'][0][-1][:2]==[0.,0.];assert f['stats']['valid_knots']==10;assert sum(f['heads'].values())==1;assert not any(f['targets']['valid'][0]);assert f['inputs']['map']

def test_future_mutation_does_not_change_inputs(source):
    r=records(source)[0]; f=build_features(r,horizon=5); q=copy.deepcopy(r);q['scene']['tracks'][1]['states'][-1]['x']+=10; q['scene']['map_context']['signals']=[{'hidden_future':True}];g=build_features(q,horizon=5)
    assert f['inputs']==g['inputs'];assert f['candidate']==g['candidate'];assert f['targets']!=g['targets']

def test_candidate_mutation_only_query(source):
    r=records(source)[0];f=build_features(r,horizon=5);q=copy.deepcopy(r);q['scene']['tracks'][0]['states'][-1]['x']+=10;g=build_features(q,horizon=5);assert f['inputs']==g['inputs'] and f['targets']==g['targets'] and f['candidate']!=g['candidate']

def test_future_birth_not_input(source):
    r=records(source)[0];r['scene']['tracks'][2]['states'][2]['valid']=False;f=build_features(r,horizon=5);assert '3' not in f['actor_ids'];assert f['stats']['future_births_unmodelled']==1

def test_invalid_target_mask(source):
    r=records(source)[0];r['scene']['tracks'][1]['states'][-1]['valid']=False;f=build_features(r,horizon=5);assert f['stats']['valid_knots']==9;assert f['targets']['xy'][1][-1]==[0.,0.]

def test_cache_authorization_and_tamper(source,tmp_path):
    _,_,reader,decoder,m=source; out=tmp_path/'cache'; s=prepare(m,out,horizon=5,reader=reader,decoder=decoder);sets,_=load_cache(out); assert len(s['accepted'])==4; assert all(x['training_allowed'] for x in sets['training']);assert not any(x['training_allowed'] for x in sets['validation']);
    with (out/'validation.jsonl').open('a') as f:f.write('\n')
    with pytest.raises(ValueError,match='bytes mismatch'):load_cache(out)

def test_cache_unbound(source,tmp_path):
    _,_,reader,decoder,m=source;m=copy.deepcopy(m);m['records'][0]['record_index']=77
    with pytest.raises(ValueError,match='missing'):prepare(m,tmp_path/'cache',horizon=5,reader=reader,decoder=decoder)

def overlay(source,**kwargs):
    r=records(source)[0]; defaults=dict(scenario_id=r['scene']['manifest']['scenario_id'],record_sha256=r['record_sha256'],event_id='e',lane_id='10',kind='LANE_CLOSURE',generation='0.1',effective_on='0.2',effective_off='4',issue='0.15',receipt='0.3',authority='sim',seed=7);defaults.update(kwargs);return RuleOverlay(**defaults),r

def test_overlay_hidden_and_expiry(source):
    e,r=overlay(source);assert e.teacher_active('0.2');assert e.public_view('0.2')=={'received_messages':[]};assert not e.teacher_active('4'); assert 'announced_window' not in e.public_view('0.3')['received_messages'][0];assert e.bind(r)['all_training_masks'] is False

def test_overlay_early_announcement(source):
    e,_=overlay(source,receipt='0.16',announce_window=True);assert not e.teacher_active('0.16');assert e.public_view('0.16')['received_messages'][0]['announced_window']==['0.2','4']

def test_overlay_invalid_clock_and_lane(source):
    with pytest.raises(ValueError):overlay(source,receipt='0.1')
    e,r=overlay(source,lane_id='bad');
    with pytest.raises(ValueError):e.bind(r)

def test_overlay_lost_message(source):
    e,_=overlay(source,receipt=None);assert e.public_view('5')=={'received_messages':[]}

def test_encoder_candidate_separation_and_gradients(source):
    b=collate(features(source)[:2]);m=FactualJointModel(d=16,modes=3,neighbors=4);enc=m.encode_scene(b['inputs']);p=m.decode_candidate(b['inputs'],enc,b['candidate']);q=m.decode_candidate(b['inputs'],enc,b['candidate']+1)
    assert torch.equal(p['logits'],q['logits']); assert not torch.equal(p['xy'],q['xy']);assert p['xy'].shape==(2,3,3,5,2)
    l=joint_nll(p,b['target'],b['valid']);l.backward();assert all(torch.isfinite(p.grad).all() for p in m.parameters() if p.grad is not None);assert any(p.grad is not None and p.grad.abs().sum()>0 for p in m.encoder.parameters())

def test_joint_nll_shared_mode_not_per_actor():
    y=torch.zeros(1,2,1,2);valid=torch.ones(1,2,1,dtype=torch.bool);xy=torch.zeros(1,2,2,1,2);xy[0,0,1,0,0]=10;xy[0,1,0,0,0]=10;p=dict(logits=torch.zeros(1,2),xy=xy)
    l=joint_nll(p,y,valid);assert l.item()==pytest.approx(math.log(2*math.pi)+25);assert metric_sums(p,y,valid,y)['joint_min_sum']==10

def test_mask_nan_and_empty():
    y=torch.tensor([[[[0.,0.],[float('nan'),float('nan')]]]]);valid=torch.tensor([[[True,False]]]);p=dict(logits=torch.zeros(1,1),xy=torch.zeros(1,1,1,2,2));assert joint_nll(p,y,valid).item()==pytest.approx(math.log(2*math.pi));assert joint_nll(p,y,torch.zeros_like(valid)) is None

def test_padding_invariance(source):
    f,g=features(source)[:2];g=copy.deepcopy(g);g['actor_ids'].pop();
    for key in ('history','category'):g['inputs'][key].pop()
    for key in ('xy','valid'):g['targets'][key].pop()
    g['baseline_cv'].pop();g['inputs']['map']=g['inputs']['map'][:1];m=FactualJointModel(d=16,modes=2,neighbors=4).eval();a=collate([g]);b=collate([f,g]);
    with torch.no_grad():p=m(a['inputs'],a['candidate']);q=m(b['inputs'],b['candidate']);assert torch.allclose(p['xy'][0],q['xy'][1,:,:2],atol=1e-6)

def test_overfit_and_freeze(source):
    fs=features(source);tr=[dict(f,training_allowed=True) for f in fs if f['split']=='training'];va=[dict(f,training_allowed=False) for f in fs if f['split']=='validation'];
    m,r=fit(tr,va,epochs=45,batch_size=1,d=16,modes=2,neighbors=4,lr=.01,diagnostic_overfit=True)
    assert r['history'][-1]['train']['joint_nll_per_knot'] < r['history'][0]['train']['joint_nll_per_knot']-.005
    assert r['active_heads']==['joint'] and len(r['inactive_heads'])==7 and r['overfit_diagnostic_pass'] is True
    m,r=fit(tr,va,epochs=2,d=16,modes=2,neighbors=4,freeze_encoder=True);assert all(p.grad is None and not p.requires_grad for p in m.encoder.parameters())

def test_train_rejects_validation(source):
    fs=features(source);r=next(f for f in fs if f['split']=='validation');
    with pytest.raises(ValueError,match='split'):fit([dict(r,training_allowed=True)],[dict(r,training_allowed=False)])

def test_cli_checkpoint_replay(source,tmp_path):
    import subprocess,sys,os
    _,_,reader,decoder,manifest=source;cache=tmp_path/'cache';prepare(manifest,cache,horizon=5,reader=reader,decoder=decoder);out=tmp_path/'train'
    root=Path(__file__).resolve().parents[1]
    p=subprocess.run([sys.executable,str(root/'scripts/train_factual.py'),'--cache',str(cache),'--output',str(out),'--epochs','2','--hidden','16','--modes','2','--threads','1'],capture_output=True,text=True)
    assert p.returncode==0,p.stdout+p.stderr
    r=json.loads((out/'training_report.json').read_text());assert r['checkpoint_replay_match'] and r['active_heads']==['joint'] and r['formal_sc'] is False

def test_lazy_public_api_does_not_load_native():
    import subprocess,sys
    root=Path(__file__).resolve().parents[1]
    p=subprocess.run([sys.executable,'-c',f"import sys;sys.path.insert(0,{str(root/'python')!r});import rampd_core;from rampd_core import SceneManifest,parse_womd_scenario_proto;assert 'rampd_core.interval' not in sys.modules"],capture_output=True,text=True)
    assert p.returncode==0,p.stderr

def test_overlay_outside_scene_rejected(source):
    e,r=overlay(source,effective_on='2',effective_off='4')
    with pytest.raises(ValueError,match='intersect'):e.bind(r)

# Fixed public query grid; actual future timestamps are target-side only.
def test_future_timestamp_jitter_not_public(source):
    r=records(source)[0];f=build_features(r,horizon=5);q=copy.deepcopy(r);q['scene']['manifest']['timestamps'][-1]+=.005
    for a in q['scene']['tracks']:a['states'][-1]['timestamp']+=.005
    g=build_features(q,horizon=5);assert f['inputs']==g['inputs'] and f['candidate']==g['candidate'];assert f['targets']['actual_dt']!=g['targets']['actual_dt']

def test_collate_rejects_future_history(source):
    f=features(source)[0];f['inputs']['history'][0][-1][8]=.1
    with pytest.raises(ValueError,match='history after'):collate([f])

def test_collate_rejects_numeric_mask(source):
    f=features(source)[0];f['targets']['valid'][1][0]=1
    with pytest.raises(ValueError,match='boolean'):collate([f])

def test_cv_initialization_and_epoch_zero(source):
    fs=features(source);tr=[dict(f,training_allowed=True) for f in fs if f['split']=='training'];va=[dict(f,training_allowed=False) for f in fs if f['split']=='validation']
    _,r=fit(tr,va,epochs=1,d=16,modes=2,neighbors=4,lr=.001)
    init=r['history'][0]['validation'];assert init['top1_ADE_m']==pytest.approx(init['cv_ADE_m'],abs=1e-6)
    assert r['checkpoint_validation']['joint_nll_per_knot']<=init['joint_nll_per_knot']+1e-7

def test_protocol_future_only_and_recipient_views(source):
    from rampd_core.datasets.rule_overlay import ScheduledDelivery,replay_scheduled_world
    e,r=overlay(source,generation='.2',effective_on='.4',issue='.25',receipt=None,announce_window=True)
    d=[ScheduledDelivery('1','.3','.6'),ScheduledDelivery('2','.3','.35'),ScheduledDelivery('3','.3',None)]
    p=replay_scheduled_world(r,e,d,query_steps=6);a=p['worlds']['EVENT'];b=p['worlds']['NO_EVENT'];assert a[0]['public_by_recipient']==b[0]['public_by_recipient'];assert a[2]['teacher']['rule_active'];assert a[2]['public_by_recipient']['1']==b[2]['public_by_recipient']['1'];assert a[2]['public_by_recipient']['2']['received_messages'];assert not a[-1]['public_by_recipient']['3']['received_messages'];assert p['event_training_allowed'] is False
    old,_=overlay(source,receipt=None)
    with pytest.raises(ValueError,match='history not regenerated'):replay_scheduled_world(r,old,d)

def test_publication_clock(source):
    from rampd_core.datasets.rule_overlay import ScheduledDelivery
    e,_=overlay(source)
    with pytest.raises(ValueError,match='publication before'):ScheduledDelivery('1','.1','.2').validate(e)
    with pytest.raises(ValueError,match='receipt before'):ScheduledDelivery('1','.3','.2').validate(e)

def test_event_clock_loss_masks():
    from rampd_core.learning.event_loss import event_clock_nll
    x=torch.zeros(3,4,requires_grad=True);a=torch.tensor([[True,False,False,False],[False,True,True,False],[True,True,True,True]]);k=torch.tensor([True,True,False]);loss=event_clock_nll(x,a,k);assert loss.item()==pytest.approx((math.log(4)+math.log(2))/2);loss.backward();assert x.grad[2].abs().sum()==0;assert event_clock_nll(x,a,torch.zeros_like(k)) is None
    with pytest.raises(ValueError):event_clock_nll(x,torch.zeros_like(a),k)

def test_lane_proposal(source):
    from rampd_core.datasets.incident_scenarios import propose
    r=records(source)[0]
    with pytest.raises(ValueError,match='logged time span'):propose(r)
    r['scene']['manifest']['timestamps'].append(1.1)
    for a in r['scene']['tracks']:
        a['states'].append(dict(a['states'][-1],timestamp=1.1,observed=False))
    p=propose(r);assert p['lane_proposal']['lane_id']=='10';assert p['joint_counterfactual_mask'] is False;assert p['teacher_schedule']['physical_activation'] is None

# Likelihood and metric separation; no new active task head.
def test_radial_laplace_proper_shared_density():
    y=torch.zeros(1,2,1,2);v=torch.ones(1,2,1,dtype=torch.bool);x=torch.zeros(1,2,2,1,2,requires_grad=True)
    with torch.no_grad():x[0,0,1,0,0]=4.;x[0,1,0,0,0]=4.
    p=dict(logits=torch.zeros(1,2),xy=x);l=joint_nll(p,y,v,family='radial_laplace');assert l.item()==pytest.approx(math.log(2*math.pi)+2.);l.backward();assert torch.isfinite(x.grad).all()
    with pytest.raises(ValueError):joint_nll(p,y,v,family='unsupported')

def test_wrong_logit_shape_rejected():
    with pytest.raises(ValueError,match='shape'):joint_nll(dict(logits=torch.zeros(1,1),xy=torch.zeros(1,2,1,1,2)),torch.zeros(1,1,1,2),torch.ones(1,1,1,dtype=torch.bool))

def test_cv_cache_mutation_rejected(source):
    f=features(source)[0];f['baseline_cv'][1][0][0]+=1
    with pytest.raises(ValueError,match='CV baseline'):collate([f])

def test_event_inactive_nonfinite_no_gradient():
    from rampd_core.learning.event_loss import event_clock_nll
    x=torch.tensor([[0.,0.],[float('nan'),float('nan')]],requires_grad=True);a=torch.tensor([[True,False],[False,False]]);k=torch.tensor([True,False]);l=event_clock_nll(x,a,k);assert l.item()==pytest.approx(math.log(2));l.backward();assert torch.equal(x.grad[1],torch.zeros(2))
    with pytest.raises(ValueError):event_clock_nll(x,torch.tensor([[True,False],[True,False]]),torch.ones(2,dtype=torch.bool))

def test_selection_ade_and_grad_groups(source):
    fs=features(source);tr=[dict(f,training_allowed=True) for f in fs if f['split']=='training'];va=[dict(f,training_allowed=False) for f in fs if f['split']=='validation'];_,r=fit(tr,va,epochs=2,d=16,modes=2,neighbors=4,objective='radial_laplace',selection='ade');assert r['checkpoint_validation']['top1_ADE_m']<=r['history'][0]['validation']['top1_ADE_m']+1e-7;assert set(r['history'][1]['grad_group_max'])=={'encoder','candidate','decoder','mode_logits'}

def test_replay_requires_full_recipient_roster(source):
    from rampd_core.datasets.rule_overlay import ScheduledDelivery,replay_scheduled_world
    e,r=overlay(source,generation='.2',effective_on='.4',issue='.25',receipt=None)
    with pytest.raises(ValueError,match='incomplete'):replay_scheduled_world(r,e,[ScheduledDelivery('1','.3','.6')])


def test_extend_manifest_keeps_validation_and_train(source):
    from rampd_core.datasets.split_manifest import extend_training_manifest
    root,raw,reader,decoder,base=source;path=next(p for p in raw if p.parent.name=='training');raw[path].append(b'training_extra')
    m=extend_training_manifest(base,train_limit=3,reader=reader,decoder=decoder)
    assert m['records'][:len(base['records'])]==base['records'];assert len(m['records'])==5;assert m['records'][-1]['scenario_id']=='training_extra';assert len(list(stream_records(m,reader=reader,decoder=decoder)))==5
    with pytest.raises(ValueError):extend_training_manifest(base,train_limit=1,reader=reader,decoder=decoder)


def test_radial_selection_uses_radial_likelihood(source):
    fs=features(source);tr=[dict(f,training_allowed=True) for f in fs if f['split']=='training'];va=[dict(f,training_allowed=False) for f in fs if f['split']=='validation'];_,r=fit(tr,va,epochs=1,d=16,modes=2,neighbors=4,objective='radial_laplace',selection='nll');assert r['selection_metric']=='radial_nll_per_knot';assert 'joint_nll_per_knot' in r['checkpoint_validation']


def test_joint_unlabelled_scene_logits_not_used():
    y=torch.zeros(2,1,1,2);v=torch.tensor([[[True]],[[False]]]);xy=torch.zeros(2,1,1,1,2,requires_grad=True);logits=torch.tensor([[0.],[float('nan')]],requires_grad=True)
    l=joint_nll(dict(logits=logits,xy=xy),y,v);assert l.item()==pytest.approx(math.log(2*math.pi));l.backward();assert logits.grad[1,0]==0 and xy.grad[1].abs().sum()==0
