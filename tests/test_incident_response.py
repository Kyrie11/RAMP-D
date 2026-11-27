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
