"""Declared longitudinal diagnostic only, not a Native proof."""
import copy
from fractions import Fraction as Q
import pytest
from rampd_core.datasets.incident_response import paired,rollout,Closure

def spec():
    return dict(family_id='synthetic_fixture',split='diagnostic',source_digest='0'*64,cutoff='0',ego_id='e',lane={'centerline_length_m':120.},vehicles=[dict(id='e',s=20.,v=6.,length=4.),dict(id='f',s=8.,v=6.,length=4.),dict(id='l',s=42.,v=6.,length=4.)],excluded_current=[],receipts={'e':'1.2','f':'0.5','l':None},closure=Closure(35.,43.).__dict__,scope='SYNTHETIC_DIAGNOSTIC')

def test_pairs_nonvacuous():
    p=paired(spec());assert p['aa_equal'];assert p['ego_intervention']['ego_m']>1.;assert p['ego_intervention']['other_m']>0.;assert p['rule_intervention']['ego_m']>0.;assert not p['all_training_masks'];assert not p['formal_sc']
    a,b=p['runs']['A'],p['runs']['B'];assert [f['rule_active'] for f in a['frames']]==[f['rule_active'] for f in b['frames']];assert [f['public'] for f in a['frames']]==[f['public'] for f in b['frames']]
    assert a['frames'][0]['state']==b['frames'][0]['state'];assert a['frames'][1]['state']==b['frames'][1]['state']

def test_hidden_actual_clock_not_behavior_input():
    s=spec();r=rollout(s);q=copy.deepcopy(s);q['closure']['effective_on']='0.85';z=rollout(q);assert [f['state'] for f in r['frames']]==[f['state'] for f in z['frames']];assert [f['rule_active'] for f in r['frames']]!=[f['rule_active'] for f in z['frames']]

def test_private_receipt_and_no_future_leak():
    r=rollout(spec());d={Q(f['t']):f for f in r['frames']};assert not d[Q('0.4')]['public']['f']['received'];assert d[Q('0.5')]['public']['f']['received'];assert not d[Q('0.8')]['public']['e']['received'];assert d[Q('1.2')]['public']['e']['received'];assert not d[Q('4')]['rule_active'];assert all(f['physical_ack'] is None for f in r['frames']);assert 'l' in r['frames'][0]['occupied'] # initially in resource

def test_missing_roster_or_bad_clock():
    s=spec();del s['receipts']['f'];
    with pytest.raises(ValueError):rollout(s)
    s=spec();s['receipts']['e']='0.2'
    with pytest.raises(ValueError,match='receipt before'):rollout(s)

def test_no_magic_stop_and_closed_entry():
    s=spec();s['receipts']={k:None for k in s['receipts']};r=rollout(s);assert any(v['kind']=='CLOSED_ENTRY' for v in r['violations']);assert all(f['state']['e'][1]>=0 for f in r['frames']);assert all(abs(v)<=4. for f in r['frames'][1:] for v in f['controls_from_previous'].values())

def test_clock_split_and_separate_planned_actual():
    s=spec();s['closure']['effective_on']='0.85';r=rollout(s);d={Q(f['t']):f for f in r['frames']};assert Q('.85') not in d and not d[Q('.8')]['rule_active'] and d[Q('.9')]['rule_active'];assert d[Q('1.2')]['public']['e']['announced_window']==['0.8','4']


def test_off_grid_private_message_does_not_reschedule_others():
    s=spec();s['receipts']['f']='0.55';a=rollout(s);d={Q(f['t']):f for f in a['frames']};assert Q('.55') not in d;assert not d[Q('.5')]['public']['f']['received'];assert d[Q('.6')]['public']['f']['received']


def test_independent_trace_replay_and_mutation():
    from rampd_core.datasets.incident_response import audit_pair
    p=paired(spec());assert audit_pair(p)['ok'];q=copy.deepcopy(p);q['runs']['B']['frames'][4]['state']['e'][0]+=.1;assert not audit_pair(q)['ok'];q=copy.deepcopy(p);q['runs']['B']['frames'][1]['public']['e']={'received':True};assert not audit_pair(q)['ok'];q=copy.deepcopy(p);q['all_training_masks']=True;assert not audit_pair(q)['ok']


def test_cached_proposal_binding_before_geometry():
    from rampd_core.datasets.incident_response import from_feature_and_proposal
    from rampd_core.datasets.split_manifest import canonical_digest
    e=dict(scenario_id='a',record_sha256='0'*64,lane_id='10');lane={'lane_id':'10'};d=[];p=dict(binding={'event':e},lane_proposal=lane,deliveries=d,scenario_spec_sha256=canonical_digest(dict(event=e,deliveries=d,lane=lane)),family_id='a',source_digest='0'*64,split='training',ego_id='e',decision_time='1')
    with pytest.raises(ValueError,match='identity'):from_feature_and_proposal({'scenario_id':'wrong'},p)


def test_unique_route_stops_at_branch_and_no_extrapolation():
    from rampd_core.datasets.incident_scenarios import extend_unique_route
    def lane(i,x,y,prev,succ):return dict(kind='lane',feature_id=i,vertices=[dict(x=x,y=0),dict(x=y,y=0)],predecessors=prev,successors=succ,attributes={'lane_type':'2'})
    r=dict(scene=dict(map_context=dict(primitives=[lane('a',0,20,[],['b']),lane('b',20,50,['a'],['c','d']),lane('c',50,70,['b'],[]),lane('d',50,80,['b'],[])])))
    q=extend_unique_route(r,dict(lane_id='a',centerline=[[0,0],[20,0]]));assert q['centerline_length_m']==50 and q['route_stop']=='BRANCH_OR_NO_SUCCESSOR';assert [x['lane_id'] for x in q['route_segments']]==['a','b']
    r['scene']['map_context']['primitives'][1]['vertices'][0]['x']=21;q=extend_unique_route(r,dict(lane_id='a',centerline=[[0,0],[20,0]]));assert q['centerline_length_m']==20 and q['route_stop']=='GEOMETRIC_JOIN_REJECTED'


def test_trace_ledger_and_delta_mutations():
    from rampd_core.datasets.incident_response import audit_pair
    s=spec();s['receipts']={k:None for k in s['receipts']};p=paired(s);assert audit_pair(p)['ok'];q=copy.deepcopy(p);q['runs']['B']['violations']=[];assert not audit_pair(q)['ok'];q=copy.deepcopy(p);q['ego_intervention']['other_m']+=1;assert not audit_pair(q)['ok'];q=copy.deepcopy(p);q['runs']['B']['stop']='MODEL_ROUTE_END';assert not audit_pair(q)['ok']


def test_scoped_projected_labels_never_authorize():
    from rampd_core.datasets.projected_labels import export_pair
    p=paired(spec());rows=export_pair(p);assert len(rows)==6 and all(not r['training_allowed'] and not any(r['heads'].values()) for r in rows);assert next(r for r in rows if r['run']=='NO_EVENT')['declared_event']['exists'] is False;assert all(r['physical_execution'] is None for r in rows)


def test_task_stop_time_distinguishes_unknown():
    from rampd_core.task_wait_metrics import task_stop_metrics
    r=task_stop_metrics([dict(t0=0,t1=.5,pending=True,speed_mps=.0,resource_status='BLOCKED'),dict(t0=.5,t1=1.5,pending=True,speed_mps=.1,resource_status='UNKNOWN'),dict(t0=1.5,t1=2,pending=True,speed_mps=0.,resource_status='AVAILABLE'),dict(t0=2,t1=3,pending=False,speed_mps=0.,resource_status='AVAILABLE')]);assert r['task_stop_s']==2 and r['blocked_stop_s']==.5 and r['available_stop_s']==.5 and r['unknown_resource_stop_s']==1


def test_sensor_and_reaction_delay_no_hidden_control_update():
    from rampd_core.datasets.incident_response import audit_pair,reaction_evidence
    s=spec();s['receipts']={i:None for i in s['receipts']};s['observation_model']=dict(physical_on='.8',physical_off='4',range_m=25.);s['reaction_delay_s']='.3'
    p=paired(s);assert audit_pair(p)['ok'];a=p['runs']['A'];n=p['runs']['NO_EVENT'];d=reaction_evidence(p)['A']['e'];assert d['message_available_at_tick'] is None and Q(d['first_local_positive_tick'])==Q('.8');assert Q(d['first_control_difference_vs_no_event_tick'])>=Q('1.1')
    for f,g in zip(a['frames'],n['frames']):
        if Q(f['t'])<=Q('1.1'):assert f['state']==g['state']
    q=copy.deepcopy(p);q['runs']['A']['frames'][1]['public']['e']['local_blocked']=True;assert not audit_pair(q)['ok']


def test_absent_event_not_right_censored_onset():
    from rampd_core.datasets.projected_labels import export_pair
    p=paired(spec());n=next(r for r in export_pair(p) if r['run']=='NO_EVENT');assert not n['declared_event']['onset']['known'] and n['declared_event']['onset']['kind']=='UNKNOWN'


def test_route_prepend_and_scope_geometry():
    from rampd_core.datasets.incident_scenarios import extend_unique_route,resource_applicability
    def lane(i,a,b,pre,succ):return dict(feature_id=i,kind='lane',vertices=[dict(x=a,y=0.),dict(x=b,y=0.)],predecessors=pre,successors=succ,attributes={'lane_type':'2'})
    r={'scene':{'map_context':{'primitives':[lane('p',-20,0,[],['a']),lane('a',0,20,['p'],['b']),lane('b',20,40,['a'],[])]}}}
    q=extend_unique_route(r,dict(lane_id='a',centerline=[[0,0],[20,0]],ego_arc_m=5.),prepend=True);assert q['centerline_length_m']==60 and q['ego_arc_m']==25 and [v['lane_id'] for v in q['route_segments']]==['p','a','b']
    a=resource_applicability(dict(lane=q,closure={'start':27,'end':35}));assert a['centerline_straight_closure_candidate'] and not a['physical_resource_verified']


def test_projected_2d_labels_scope():
    pytest.importorskip('shapely')
    from rampd_core.datasets.projected_labels import sampled_projected_2d
    s=spec();s['lane']['centerline']=[[0,0],[120,0]];p=paired(s);g=sampled_projected_2d(p,{'e':1.9,'f':1.9,'l':1.9});assert g['counts']['interior']>0 and g['counts']['separated']>0 and g['counts']['disagreement']==0 and not g['training_allowed']
    with pytest.raises(ValueError):sampled_projected_2d(p,{'e':1.9})


def test_entry_time_value_replayed():
    from rampd_core.datasets.incident_response import audit_pair
    s=spec();s['receipts']={i:None for i in s['receipts']};p=paired(s);assert audit_pair(p)['ok']
    q=copy.deepcopy(p);v=next(x for x in q['runs']['A']['violations'] if x['kind']=='CLOSED_ENTRY');v['entry_time_s']+=.05
    assert not audit_pair(q)['ok']


def test_no_delivery_is_not_conditional_clock():
    from rampd_core.datasets.projected_labels import export_pair
    s=spec();s['receipts']['f']=None;s['receipts']['e']='10';r=next(x for x in export_pair(paired(s)) if x['run']=='A')
    assert r['declared_delivery_target']=={'e':True,'f':False,'l':False}
    assert r['message_clock_evidence']['f']['kind']=='UNKNOWN' and r['message_clock_evidence']['e']['kind']=='RIGHT_CENSORED'
    assert not any(r['heads'].values())


def test_versioned_notice_and_cancel_not_physical_ack():
    from rampd_core.datasets.rule_lifecycle import Notice,public_notices
    a=Notice('event','agency',1,'LANE_CLOSURE',('lane',),'0.1','0.2','1','4')
    b=Notice('event','agency',2,'LANE_CLOSURE',('lane',),'1','1.1','1','4',cancelled=True)
    ds=[dict(authority='agency',event_id='event',version=1,recipient='e',receipt='3'),dict(authority='agency',event_id='event',version=2,recipient='e',receipt='2'),dict(authority='agency',event_id='event',version=1,recipient='f',receipt='0.3')]
    assert public_notices([a,b],ds,'e','1')==[]
    for t in ('2','4'):
        v=public_notices([a,b],ds,'e',t)[0];assert v['version']==2 and v['cancelled'] and 'effective_off' not in v and 'physical_ack' not in v
    assert public_notices([a,b],ds,'f','4')[0]['version']==1
    ds[0]['receipt']='0.1'
    with pytest.raises(ValueError,match='receipt before'):public_notices([a,b],ds,'e','4')


def test_speed_and_direction_payloads_and_device_cohort():
    from rampd_core.datasets.rule_lifecycle import Notice,route_equipped_recipients
    from dataclasses import replace
    n=Notice('event','agency',1,'TEMPORARY_SPEED_LIMIT',('lane',),'0.1','0.2','1','4',speed_limit_mps=5.)
    n.validate()
    with pytest.raises(ValueError):replace(n,speed_limit_mps=None).validate()
    with pytest.raises(ValueError):replace(n,kind='ALTERNATING_DIRECTION',speed_limit_mps=None).validate()
    kwargs=dict(source_digest='a'*64,other_receipt='1',ego_receipt=None)
    x=route_equipped_recipients(['e','a','b'],'e',**kwargs);y=route_equipped_recipients(['b','e','a'],'e',**kwargs);assert x==y
    assert route_equipped_recipients(['e','a'],'e',probability=0.,**kwargs)=={'e':None,'a':None}


def test_route_integrity_rejects_false_join():
    pytest.importorskip('shapely')
    from rampd_core.datasets.incident_scenarios import route_integrity
    lane=dict(lane_id='a',centerline=[[0.,0.],[20.,0.],[40.,0.]],centerline_length_m=40.,route_segments=[dict(lane_id='a',start_m=0.,end_m=20.),dict(lane_id='b',start_m=20.,end_m=40.)],route_joins=[dict(from_lane='a',to_lane='b',gap_m=0.,alignment=1.)]);assert route_integrity(lane)['ok']
    lane['route_joins'][0]['gap_m']=.05;assert not route_integrity(lane)['ok']


def test_shared_resource_interlock_version_and_unknown():
    from rampd_core.shared_resource_controller import SharedResourceController,SignalCommand
    c=SharedResourceController({'a':'A','b':'B'},clearance_ticks=1,green_ticks=1);free={'a':False,'b':False};red=SignalCommand(0,'RED')
    assert c.step(0,free,prior_swept_empty=None,ack=red)['permit'] is None
    r=c.step(1,free,prior_swept_empty=True,ack=red);assert r['command']=={'version':1,'direction':'A'} and r['permit'] is None
    assert c.step(2,free,prior_swept_empty=True,ack=red)['permit'] is None
    assert c.step(3,free,prior_swept_empty=True,ack=SignalCommand(1,'A'))['permit']=='A'
    r=c.step(4,{'a':True,'b':None},prior_swept_empty=False,ack=SignalCommand(1,'A'));assert r['permit'] is None and r['command']['direction']=='RED'
    with pytest.raises(ValueError):c.step(5,{'a':False},prior_swept_empty=True,ack=None)


def test_shared_resource_complete_and_tamper_labels():
    from rampd_core.datasets.shared_resource_scenario import simulate,audit
    from rampd_core.datasets.shared_resource_labels import release
    from rampd_core.datasets.split_manifest import canonical_digest
    a=simulate();b=simulate(ego_wait_ticks=12);assert a==simulate() and a!=b
    for r in (a,b):
        x=audit(r);assert x['ok'] and x['completed'] and all(x['entries'].values()) and all(x['exits'].values())
    z=release(a,split='training');assert z and z[0]['model_training_allowed'] and not z[0]['real_world_training_allowed'] and not any(z[0]['formal_heads'].values())
    q=copy.deepcopy(a);q['frames'][0]['controller']['permit']='A';q['digest']=canonical_digest({k:v for k,v in q.items() if k!='digest'});assert not audit(q)['ok']
    with pytest.raises(ValueError):release(q,split='training')


def test_declared_heads_reject_family_and_permission_leak():
    from rampd_core.datasets.shared_resource_scenario import simulate
    from rampd_core.datasets.shared_resource_labels import release
    from rampd_core.learning.resource_pilot import fit_head
    from rampd_core.datasets.split_manifest import canonical_digest
    tr=release(simulate(seed=0),split='training');va=release(simulate(seed=1),split='validation')
    with pytest.raises(ValueError,match='family'):fit_head(tr,release(simulate(seed=0),split='validation'),'event',epochs=1)
    q=copy.deepcopy(tr);q[0]['real_world_training_allowed']=True;q[0]['digest']=canonical_digest({k:v for k,v in q[0].items() if k!='digest'})
    with pytest.raises(ValueError,match='permission'):fit_head(q,va,'event',epochs=1)
    _,r=fit_head(tr,va,'event',epochs=1);assert r['formal_sc'] is False and r['validation_rows']==len(va)


def test_source_topology_not_just_polyline():
    from rampd_core.datasets.incident_scenarios import extend_unique_route,verify_route_source,route_integrity
    def lane(i,x,y,prev,succ):return dict(kind='lane',feature_id=i,vertices=[dict(x=x,y=0),dict(x=y,y=0)],predecessors=prev,successors=succ,attributes={'lane_type':'2'})
    r=dict(scene=dict(map_context=dict(primitives=[lane('a',0,20,[],['b']),lane('b',20,50,['a'],[])])))
    q=extend_unique_route(r,dict(lane_id='a',centerline=[[0,0],[20,0]]));assert verify_route_source(r,q)['ok']
    r['scene']['map_context']['primitives'][0]['successors']=[];assert route_integrity(q)['ok'] and not verify_route_source(r,q)['ok']


def test_heterogeneous_release_and_source_label_gate():
    from rampd_core.datasets.shared_resource_scenario import simulate,audit
    from rampd_core.datasets.shared_resource_labels import release,transition_rows
    from rampd_core.datasets.split_manifest import canonical_digest
    a=simulate();b=simulate(release_delays={'e':3,'a':0,'b':2,'c':1});assert a!=b and audit(b)['ok']
    assert any(f['public']['e']!=f['public']['a'] for f in b['frames'])
    q=copy.deepcopy(b);q['family_id']='fake';q['digest']=canonical_digest({k:v for k,v in q.items() if k!='digest'})
    with pytest.raises(ValueError):release(q,split='training')
    q=copy.deepcopy(b);q['frames'][0]['controller']['green_age']=100;q['digest']=canonical_digest({k:v for k,v in q.items() if k!='digest'})
    with pytest.raises(ValueError,match='reexecution'):release(q,split='training')
    x=transition_rows(b,split='training',horizon=8);assert len(x)==152 and len(x[0]['public_inputs'])==17
    # Labels use a future window, but input prefix is invariant under future ACK delay.
    d=simulate(ack_delay_ticks=3);p=transition_rows(a,split='training');q=transition_rows(d,split='training');assert p[0]['public_inputs']==q[0]['public_inputs'] and p[0]['cv_geometry']==q[0]['cv_geometry']
    assert not any(x[0]['formal_heads'].values())


def test_transition_head_and_finite_teacher():
    from rampd_core.datasets.shared_resource_scenario import simulate
    from rampd_core.datasets.shared_resource_labels import transition_rows
    from rampd_core.learning.resource_pilot import fit_transition_head
    from rampd_core.finite_wait_reference import finite_teacher
    tr=transition_rows(simulate(seed=0),split='training');va=transition_rows(simulate(seed=1),split='validation')
    with pytest.raises(ValueError,match='duplicate'):fit_transition_head(tr+tr,va,'event',epochs=1)
    for h in ('event','occupancy','observation'):
        _,r=fit_transition_head(tr,va,h,epochs=1);assert r['final']['loss']>=0 and not r['formal_sc']
    r=finite_teacher((5,7),14);assert r['rows'][11]['viable'] is False and r['rows'][12]['rank']==12 and r['rows'][14]['forced_wait_ticks_max']==9 and not r['training_allowed']
