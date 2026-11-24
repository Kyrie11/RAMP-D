"""A72 targeted mutation tests. All formal certificates remain unauthorized."""
from __future__ import annotations
import copy,json,hashlib
from pathlib import Path
from fractions import Fraction as Q
import pytest
from rampd_core.a71_native_polygon_geometry import polygon_vertices,guaranteed_polygon_separation
from rampd_core.a72_native_world_resource import audit_clock_bound_polygon_exclusion
from rampd_core.a60_clock_resource import ClockEvent
from rampd_core.a61_hybrid_partition import ClockWorld
from rampd_core.a72_physics_factorial import audit_available_brake_factorial
from rampd_core.a72_waymax_sensitivity import audit_waymax_lookahead
from rampd_core.a72_auxiliary_pretraining import audit_auxiliary_training_records,auxiliary_training_row

FIX=Path(__file__).parent/'fixtures'

def raw(name):return json.loads((FIX/name).read_text())

@pytest.mark.parametrize('poly',[
    ((0,0),(2,2),(0,2),(2,0)),             # crossing bow tie
    ((0,0),(3,0),(3,3),(1,0),(0,3)),       # non-adjacent vertex touch
    ((0,0),(3,0),(3,3),(0,3),(1,0)),       # edge overlaps at vertex
])
def test_polygon_rejects_non_simple_resource_footprint(poly):
    with pytest.raises(ValueError):polygon_vertices(poly)

def test_polygon_still_allows_concave_simple_resource():
    p=((0,0),(3,0),(2,1),(3,3),(0,3))
    assert len(polygon_vertices(p))==5

def test_polygon_safety_cannot_be_inferred_from_exact_touch():
    r=guaranteed_polygon_separation([[0,0],[0,0],[0,0],[0,0],[0,0],[0,0]],
         ((3,-1),(4,-1),(4,1),(3,1)),length_m=4,width_m=2)
    assert r['status']=='MAY_INTERSECT_DECLARED_POLYGON'

def test_clock_bound_polygon_rejects_unchecked_hidden_support():
    worlds=(ClockWorld('A',(ClockEvent('ruleA','RULE_EFFECTIVE',Q(1,20),'sim'),),declared_complete=True,public_history_id='h'),
            ClockWorld('B',(ClockEvent('ruleB','RULE_EFFECTIVE',Q(1,20),'sim'),),declared_complete=True,public_history_id='h'))
    fake=dict(status='CONDITIONAL_DECLARED_EGO_NATIVE_PICARD_SEGMENTED_REPLAY',
        rows=[dict(world='A',start='0',end='1/20')],clock_interval=['0','1/10'],
        clock_worlds_digest='forged',expected_world_slabs=1,replayed_world_slabs=1)
    r=audit_clock_bound_polygon_exclusion(fake,{},worlds,{'r':((0,0),(1,0),(1,1),(0,1))},
                                      start=Q(0),end=Q(1,10),length_m=4,width_m=2)
    assert r['status']=='UNKNOWN' and 'INDEPENDENT_CLOCK_PARTITION_OR_WORLD_SUPPORT_MISMATCH' in r['reasons']
    assert not r['sc_certified']

def test_native_polygon_requires_event_declaration_digest():
    worlds=(ClockWorld('A',(ClockEvent('ruleA','RULE_EFFECTIVE',Q(1,20),'sim'),),declared_complete=True,public_history_id='h'),)
    report=dict(status='CONDITIONAL_DECLARED_EGO_NATIVE_PICARD_SEGMENTED_REPLAY',rows=[],clock_interval=['0','1/10'],clock_worlds_digest='bad')
    r=audit_clock_bound_polygon_exclusion(report,{},worlds,{'r':((0,0),(1,0),(1,1),(0,1))},
            start=Q(0),end=Q(1,10),length_m=4,width_m=2)
    assert 'CLOCK_EVENT_DECLARATION_BYTES_CHANGED' in r['reasons']

def test_factorial_missing_arm_stays_review():
    arms={(0.15,'pure'):[raw('a71_carla_brakeonly_b015.json')],
          (0.15,'combined'):[raw('a70_brake_b15.json')]}
    r=audit_available_brake_factorial(arms)
    assert r['status']=='REVIEW' and any('MISSING_ONE_STEERING_ARM' in x for x in r['reasons'])
    assert len(r['pairs'])==1 and r['pairs'][0]['status'].startswith('DESCRIPTIVE')

def test_factorial_forged_duplicate_replication_rejected():
    x=raw('a71_carla_brakeonly_b015.json');y=raw('a70_brake_b15.json')
    r=audit_available_brake_factorial({(.15,'pure'):[x,x,x],(.15,'combined'):[y,y,y]},levels=(.15,))
    assert any('DUPLICATED_RAW_REPLICATION' in x for x in r['reasons'])

def _waymax_synthetic(look):
    A=[[[10+i,0,0,1,0],[i,0,0,1,0]] for i in range(3)];B=copy.deepcopy(A);B[1][0][0]+=1;B[2][0][0]+=2;B[2][1][3]=.5
    audit=[dict(distance_m=5.,lead_speed_mps=1.,raw_accel_mps2=0.) for _ in range(2)]
    return dict(status='SYNTHETIC_IDM_RESPONSE_PASS',scope='SYNTHETIC_TWO_VEHICLE_STRAIGHT_ROUTE_ONLY',
       lookahead_points=look,real_scene_used=False,counterfactual_training_labels_generated=False,
       safety_certified=False,actor_order=['ego','follower'],state_order=['x','y','yaw','vx','vy'],
       steps=2,dt_s=.1,rollouts={'A':A,'AA':copy.deepcopy(A),'B':B},ego_length_m=2,
       follower_length_m=2,official_internal_audit={w:copy.deepcopy(audit) for w in ('A','AA','B')},
       idm_source_sha256='official-code-hash',waymax='declared-version',ego_control_profile='constant',
       initial_center_offset_m=10.)

def test_waymax_ablation_remains_synthetic_auxiliary():
    d={'30':_waymax_synthetic(30),'60':_waymax_synthetic(60)}
    r=audit_waymax_lookahead(d)
    assert r['status']=='DESCRIPTIVE_SYNTHETIC_IDM_SENSITIVITY_ONLY',r
    assert not r['real_womd_scenario_behavior_validated']

def test_waymax_rejects_confounding_geometry():
    d={'30':_waymax_synthetic(30),'60':_waymax_synthetic(60)}
    d['60']['ego_length_m']=3.
    assert 'CONFOUNDED_HYPERPARAMETER_ARMS' in audit_waymax_lookahead(d)['reasons']

def test_waymax_rejects_wrong_lookahead_identity():
    r=audit_waymax_lookahead({'30':_waymax_synthetic(60),'60':_waymax_synthetic(30)})
    assert any('LOOKAHEAD_ARM_MISLABELED' in x for x in r['reasons'])

def _511():
    return dict(source_family='511NY',status='DESCRIPTIVE_REPORT_TIMES_ONLY',
       source_event_id='row-1',source_dataset_sha256='f'*64,event_type_as_reported='construction',
       reported_facility='I-90',reported_organization='NYSDOT',reported_create_time='2026-11-24T12:00:00+00:00',formal_label_masks={'L_event':0})

def test_511_real_world_auxiliary_pretraining_only():
    r=auxiliary_training_row(_511())
    assert r['weak_target']=='reported_event_category' and r['formal_rampd_label'] is None
    assert '511NY:' in r['source_family_id'] and r['partition'] in ('train','validation','test')

def test_511_missing_category_not_silently_imputed():
    x=_511();x['event_type_as_reported']=''
    with pytest.raises(ValueError):auxiliary_training_row(x)

def test_511_same_facility_month_same_split_despite_row_ids():
    a=_511();b=copy.deepcopy(a);b['source_event_id']='row-2'
    r=audit_auxiliary_training_records((a,b))
    assert r['status']=='DESCRIPTIVE_AUXILIARY_DATASET_PREPARED'
    assert r['rows'][0]['source_family_id']==r['rows'][1]['source_family_id']

def test_roadwork_visual_only_auxiliary():
    x=dict(source_family='ROADWork',status='DESCRIPTIVE_WORKZONE_OBJECTS_ONLY',source_group='video_7',source_annotation_sha256='a'*64,
           categories=['Cone','Barrier'],formal_label_masks={'L_occupancy':0})
    r=auxiliary_training_row(x)
    assert r['partition']=='unassigned_needs_official_gps_split'
    assert r['spatial_role']=='PIXEL_ANNOTATIONS_NO_METRIC_CLOSURE'

def test_no_formal_mask_escalation():
    x=_511();x['formal_label_masks']['L_viability']=1
    with pytest.raises(ValueError):auxiliary_training_row(x)

def test_auxiliary_export_quarantines_bad_row(tmp_path):
    import importlib.util
    f=Path(__file__).parents[1]/'scripts/a72_export_auxiliary_v2.py'
    spec=importlib.util.spec_from_file_location('a72_export',f)
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
    p=tmp_path/'in.jsonl';p.write_text('\n'.join(json.dumps(x) for x in [dict(source_event_id='row1',source_dataset_sha256='f'*64,event_type='construction',reported_create_time='2026-11-24T12:00:00+00:00',reported_facility='I-90',reported_organization='NYSDOT'),
                          dict(source_event_id='row2',source_dataset_sha256='f'*64,event_type='',reported_create_time='2026-11-24T12:00:00+00:00')])+'\n')
    good=tmp_path/'ok.jsonl';bad=tmp_path/'bad.jsonl';r=m.export_sources([(p,'511ny')],good,bad)
    assert r['counts']['accepted']==1 and r['counts']['quarantined']==1
    assert not any(json.loads(x)['formal_label_masks']['L_viability'] for x in good.read_text().splitlines())
    with pytest.raises(ValueError):m.export_sources([(p,'511ny')],good,bad)

def test_carla_nonzero_throttle_is_confounder_not_valid_pair():
    from rampd_core.a71_carla_factor_pairs import audit_brake_steer_pair
    a=raw('a71_carla_brakeonly_b015.json');b=raw('a70_brake_b15.json')
    b['trials'][0]['samples'][28]['actual_throttle']=.1
    r=audit_brake_steer_pair(a,b,brake=.15)
    assert any('nonzero or missing throttle' in x for x in r['reasons'])

def test_roadwork_same_video_different_annotation_sha_cannot_split():
    a=dict(source_family='ROADWork',status='DESCRIPTIVE_WORKZONE_OBJECTS_ONLY',source_group='video:v01',
        source_annotation_sha256='a'*64,categories=['Cone'],formal_label_masks={},official_gps_split='train')
    b=copy.deepcopy(a);b['source_annotation_sha256']='b'*64;b['official_gps_split']='val'
    r=audit_auxiliary_training_records((a,b))
    assert 'CROSS_SPLIT_SOURCE_FAMILY_LEAK' in r['reasons']

def test_roadwork_official_gps_split_is_retained():
    a=dict(source_family='ROADWork',status='DESCRIPTIVE_WORKZONE_OBJECTS_ONLY',source_group='video:v01',
        source_annotation_sha256='a'*64,categories=['Cone'],formal_label_masks={},official_gps_split='val')
    assert auxiliary_training_row(a)['partition']=='validation'

def test_incident_prior_requires_independently_parameterized_simulator_clock():
    from rampd_core.a72_incident_intervention import make_report_conditioned_simulation
    from rampd_core.a71_event_auxiliary import adapt_511ny_report
    r=adapt_511ny_report(dict(source_event_id='1',source_dataset_sha256='f'*64,event_type='construction',
      reported_create_time='2026-11-24T12:00:00+00:00',reported_facility='I90',reported_organization='NYSDOT'))
    v=make_report_conditioned_simulation(r,sim_world_id='sim-1',rule_effective_at=Q(3),
                public_issue_at=Q(4),public_receive_at=Q(6),authority_id='simulated_authority',resource_id='res-1')
    assert v['rule_effective_at']=='3' and v['effectivity_generated_by_simulator_not_511ny']
    with pytest.raises(ValueError):make_report_conditioned_simulation(r,sim_world_id='sim-1',rule_effective_at=Q(3),
                public_issue_at=Q(6),public_receive_at=Q(4),authority_id='a',resource_id='r')

def test_waymax_real_array_inventory_helper_is_factual():
    import importlib.util,numpy as np
    path=Path(__file__).parents[1]/'scripts/a72_probe_real_waymax_scenes.py'
    spec=importlib.util.spec_from_file_location('a72_waymax',path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
    valid=np.array([[1,1,1],[0,1,1]],bool);x=np.array([[0.,1.,2.],[-1.,0.,1.]])
    r=m.summarize_arrays(valid,np.array([1,1]),np.array([1,0]),x,x,x,x)
    assert r['objects_present_any_time']==2 and r['sdc_valid_steps']==3
    with pytest.raises(ValueError):m.summarize_arrays(valid,np.array([1,1]),np.array([1,1]),x,x,x,x)
