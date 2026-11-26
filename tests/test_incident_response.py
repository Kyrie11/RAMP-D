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
