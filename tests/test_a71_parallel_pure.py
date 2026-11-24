"""A71 adversarial pure gates: CARLA paired physical, Waymax, SUMO, event priors, polygons."""
from pathlib import Path
from fractions import Fraction as Q
from copy import deepcopy
import json
import pytest
from rampd_core.a71_carla_factor_pairs import audit_brake_steer_pair
from rampd_core.a71_waymax_counterfactual_audit import audit_waymax_idm_pair
from rampd_core.a71_sumo_tls_evidence import audit_sumo_signal_trace
from rampd_core.a71_event_auxiliary import adapt_511ny_report,adapt_roadwork_scene
from rampd_core.a71_native_polygon_geometry import guaranteed_polygon_separation,polygon_vertices,audit_native_polygon_resources
BASE=Path(__file__).parent/'fixtures'

def carla_pair():
 return (json.loads((BASE/'a71_carla_brakeonly_b015.json').read_text()),
         json.loads((BASE/'a70_brake_b15.json').read_text()))

def test_real_carla_pure_combined_are_descriptive_but_not_calibrated():
 a,b=carla_pair();r=audit_brake_steer_pair(a,b)
 assert r['status']=='DESCRIPTIVE_MATCHED_CAPTURE_REVIEW_MODEL_UNCALIBRATED',r
 assert r['observations']['n_post_frames']==40
 assert r['observations']['max_abs_speed_difference_mps']>.3
 assert not r['safe_training_labels_allowed'] and not r['causal_identification_proved']

def test_carla_reject_wrong_brake():
 a,b=carla_pair();assert audit_brake_steer_pair(a,b,brake=.3)['status']=='REVIEW'

def test_carla_reject_forged_fresh_weather():
 a,b=carla_pair();b['world_provenance']['weather_raw']['wetness']+=1
 assert 'WORLD_WEATHER_RAW_DIFFERS' in audit_brake_steer_pair(a,b)['reasons']

def test_carla_reject_forged_physics_mass():
 a,b=carla_pair();b['physics']['mass_kg_raw']+=100
 assert 'PHYSICS_CONTROL_DIFFERENT' in audit_brake_steer_pair(a,b)['reasons']

def test_carla_reject_missing_timestamp():
 a,b=carla_pair();a['trials'][0]['samples'][28]['sim_time_s']+=.2
 assert any('simulation time sequence gap' in x for x in audit_brake_steer_pair(a,b)['reasons'])

def test_carla_reject_pure_steer_leak():
 a,b=carla_pair();a['trials'][0]['samples'][30]['command_steer']=.01
 assert any('pure arm contains steering' in x for x in audit_brake_steer_pair(a,b)['reasons'])

def test_carla_reject_combined_control_not_applied():
 a,b=carla_pair()
 for row in b['trials'][0]['samples']: row['actual_steer']=0
 assert any('combined arm has no steering pulse' in x for x in audit_brake_steer_pair(a,b)['reasons'])

def _waymax_fixture():
 A=[[[10+i,0,0,1,0],[i,0,0,1,0]] for i in range(3)]
 AA=deepcopy(A); B=deepcopy(A)
 B[1][0][0]+=1;B[2][0][0]+=2
 B[2][1][3]=.5
 audit=[dict(distance_m=5.,lead_speed_mps=1.,raw_accel_mps2=0.) for _ in range(2)]
 return dict(status='SYNTHETIC_IDM_RESPONSE_PASS',scope='SYNTHETIC_TWO_VEHICLE_STRAIGHT_ROUTE_ONLY',real_scene_used=False,
   counterfactual_training_labels_generated=False,safety_certified=False,actor_order=['ego','follower'],
   state_order=['x','y','yaw','vx','vy'],steps=2,dt_s=.1,rollouts={'A':A,'AA':AA,'B':B},
   ego_length_m=2,follower_length_m=2,official_internal_audit={w:deepcopy(audit) for w in ('A','AA','B')},
   idm_source_sha256='official-local-python-source-hash',waymax='pinned-version')

def test_waymax_synthetic_pair_audit():
 r=audit_waymax_idm_pair(_waymax_fixture())
 assert r['status']=='DESCRIPTIVE_SYNTHETIC_PAIR_REPLAYED',r
 assert not r['real_driver_counterfactual_proved']

def test_waymax_future_leak_rejected():
 x=_waymax_fixture();x['rollouts']['B'][1][1][3]=.4
 assert 'FUTURE_LEAD_STATE_LEAKED_INTO_FOLLOWER_DECISION' in audit_waymax_idm_pair(x)['reasons']

def test_waymax_modified_initial_conditions_rejected():
 x=_waymax_fixture();x['rollouts']['B'][0][0][0]+=1
 assert 'DIFFERENT_PREINTERVENTION_INITIAL_CONDITIONS' in audit_waymax_idm_pair(x)['reasons']

def test_waymax_identical_intervention_rejected():
 x=_waymax_fixture();x['rollouts']['B']=deepcopy(x['rollouts']['A'])
 assert 'PAIRED_INTERVENTION_NO_SENSITIVE_RESPONSE' in audit_waymax_idm_pair(x)['reasons']

def _sumo_fixture():
 rows=[];target={'A':'Gr','B':'rG'}
 for k in range(3):
  t=str(Q(k,10))
  if k:
   for d in 'AB':rows.append(dict(kind='POST_STEP_READBACK',time=t,tls_id=d,
           expected=target[d],observed=target[d],proof_scope='TRACI_SIGNAL_STATE_NOT_FIELD_ACTUATION_ACK'))
  for d in 'AB':rows.append(dict(kind='COMMAND_READBACK',time=t,tls_id=d,
       desired=target[d],readback=target[d],controller_phase='A_GREEN',controller_version=1,
       entry_link_indices=[0],exit_link_indices=[1],proof_scope='TRACI_SIGNAL_STATE_NOT_FIELD_ACTUATION_ACK'))
 summary=dict(status='SUMO_LOGICAL_CORRIDOR_PASS',traci_signal_state_readback_observed=True,
              signal_records=len(rows),steps=[dict(time_s=.1),dict(time_s=.2)])
 return summary,rows

def test_sumo_traci_temporal_replay():
 s,r=_sumo_fixture();q=audit_sumo_signal_trace(s,r)
 assert q['status']=='DESCRIPTIVE_TRAFFIC_LIGHT_STATE_TRACE_REPLAYED',q
 assert not q['physical_signal_ack_proven']

def test_sumo_missing_next_tick_readback_rejected():
 s,r=_sumo_fixture();r=[x for x in r if not (x['kind']=='POST_STEP_READBACK' and x['time']=='1/5' and x['tls_id']=='B')]
 assert 'MISSING_SIGNAL_STATE_FOR_TICK' in audit_sumo_signal_trace(s,r)['reasons']

def test_sumo_signal_state_changed_while_not_commanded_rejected():
 s,r=_sumo_fixture();r[-4]['observed']='rr'
 assert audit_sumo_signal_trace(s,r)['status']=='REVIEW'

def test_sumo_report_cannot_create_physical_ack():
 s,r=_sumo_fixture();s['status']='ERROR'
 assert 'NO_SUCCESSFUL_INSTRUMENTED_SUMO_RUN' in audit_sumo_signal_trace(s,r)['reasons']

def report():
 return dict(source_event_id='evt-1',source_dataset_sha256='f'*64,event_type='Construction',
             reported_create_time='2026-11-24T08:00:00-05:00',reported_close_time='2026-11-24T09:00:00-05:00')

def test_511ny_never_promotes_report_time_to_effective_time():
 r=adapt_511ny_report(report());assert r['status']=='DESCRIPTIVE_REPORT_TIMES_ONLY'
 assert r['physical_rule_effective_at'] is None and r['vehicle_received_at'] is None
 assert not any(r['formal_label_masks'].values())

def test_511ny_negative_report_duration_quarantined():
 x=report();x['reported_close_time']='2026-11-24T07:00:00-05:00'
 assert 'NEGATIVE_REPORTED_DURATION_QUARANTINE' in adapt_511ny_report(x)['reasons']

def test_511ny_unzoned_time_rejected():
 x=report();x['reported_create_time']='2026-11-24T08:00:00'
 with pytest.raises(ValueError):adapt_511ny_report(x)

def _roadwork():
 return dict(status='VISUAL_SEMANTICS_ONLY_NEEDS_CALIBRATED_WORLD_GENERATOR',template_id='rw-1',
  source=dict(source_group='original-video-group',source_annotation_sha256='a'*64,image_file='x.png',
              objects=[dict(category='Barrier'),dict(category='Traffic Cone')]))

def test_roadwork_visual_source_never_metric_resource():
 r=adapt_roadwork_scene(_roadwork());assert r['metric_polygon'] is None
 assert r['physical_rule_effective_at'] is None and not any(r['formal_label_masks'].values())

def test_roadwork_missing_image_group_rejected():
 x=_roadwork();x['source']['source_group']=''
 with pytest.raises(ValueError):adapt_roadwork_scene(x)

POLY=((10,10),(12,10),(12,12),(10,12))
TUBE=[[0,1],[0,1],[0,0],[1,1],[0,0],[0,0]]

def test_exact_polygon_separation_large_clearance():
 r=guaranteed_polygon_separation(TUBE,POLY,length_m=4,width_m=2)
 assert r['status']=='DECLARED_TUBE_POLYGON_STRICTLY_SEPARATED'
 assert Q(r['min_unscaled_gap'])>0 and r['exact_rational_arithmetic']

def test_exact_polygon_possible_contact_unknown():
 r=guaranteed_polygon_separation(TUBE,((0,0),(2,0),(2,2),(0,2)),length_m=4,width_m=2)
 assert r['status']=='MAY_INTERSECT_DECLARED_POLYGON'

def test_polygon_geometry_handles_concave_hull_conservatively():
 poly=((10,10),(14,10),(11,11),(14,14),(10,14))
 assert guaranteed_polygon_separation(TUBE,poly,length_m=4,width_m=2)['status'].endswith('SEPARATED')

def test_polygon_degenerate_rejected():
 with pytest.raises(ValueError):polygon_vertices(((0,0),(1,0),(2,0)))

def test_polygon_exact_touch_not_declared_separation():
 # The conservative orientation-independent x-radius is R=(4+2)/2=3.
 p=((3,-1),(4,-1),(4,1),(3,1))
 assert guaranteed_polygon_separation([[0,0],[0,0],[0,0],[0,0],[0,0],[0,0]],p,length_m=4,width_m=2)['status']=='MAY_INTERSECT_DECLARED_POLYGON'

def test_native_polygon_bogus_report_fails_closed():
 r=audit_native_polygon_resources(dict(status='UNKNOWN',rows=[],expected_world_slabs=0,replayed_world_slabs=0),{},
      {'R':POLY},length_m=4,width_m=2,verify_native=lambda x:False)
 assert r['status']=='UNKNOWN' and not r['formal_safe_training_labels_allowed']

def test_511_csv_normalizer_preserves_report_only(tmp_path):
 import importlib.util
 p=Path(__file__).parents[1]/'scripts/a71_normalize_511ny_csv.py'
 spec=importlib.util.spec_from_file_location('a71_csv_test',p);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
 csv_file=tmp_path/'511.csv';out=tmp_path/'normalized.jsonl'
 csv_file.write_text('Event Type,Organization Name,State,Facility Name,Create Time,Close Time,Latitude,Longitude\n'
   'Construction,NY DOT,NY,Interstate 90,2026-11-24T09:00:00-05:00,2026-11-24T10:00:00-05:00,42.0,-73.0\n'
   'Construction,NY DOT,NY,Interstate 90,2026-11-24T10:00:00-05:00,2026-11-24T09:00:00-05:00,42.0,-73.0\n')
 r=m.normalize_csv(csv_file,out)
 assert r['counts']['normalized_rows']==1 and r['counts']['negative_report_duration_quarantined']==1
 doc=json.loads(out.read_text().splitlines()[0])
 assert not doc['unique_source_event_identity_attested'] and doc['scope']=='REPORT_ONLY'
 assert adapt_511ny_report(doc)['physical_rule_effective_at'] is None

def test_511_csv_normalizer_missing_columns_fails(tmp_path):
 import importlib.util
 p=Path(__file__).parents[1]/'scripts/a71_normalize_511ny_csv.py'
 spec=importlib.util.spec_from_file_location('a71_csv_test2',p);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
 f=tmp_path/'bad.csv';f.write_text('foo,bar\n1,2\n')
 with pytest.raises(ValueError):m.normalize_csv(f,tmp_path/'out.jsonl')


def test_roadwork_empty_annotated_objects_not_ground_truth_no_workzone():
 x=_roadwork();x['source']['objects']=[]
 r=adapt_roadwork_scene(x)
 assert r['categories']==[] and r['empty_annotation_does_not_prove_no_workzone']
 assert not r['formal_label_masks']['L_occupancy']
