"""Synthetic and captured-file regressions: fail closed before certification."""
import copy,importlib.util,json,sys
from fractions import Fraction as Q
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'python'))
from rampd_core.a64_carla_smoke_evidence import audit_single_control_smoke
from rampd_core.a64_hybrid_handoff import SlabHandoff,audit_slab_handoffs
from rampd_core.a61_hybrid_partition import ClockWorld,partition_clock_worlds


def one_smoke(kind='brake'):
    # Deliberately constructed synthetic samples, not simulator evidence.
    stable={'status':'DESCRIPTIVE_STATIONARY_HEIGHT_STABLE',
            'lane_audit':{'status':'DESCRIPTIVE_RECTANGLE_WITHIN_LANE'},
            'ground_height_proxy':{'status':'DESCRIPTIVE_WHEEL_HEIGHT_NEAR_ROAD'}}
    samples=[]
    for i in range(46):
        post=i>=6
        steer=.03 if post and kind!='brake' else 0.
        brake=(.7 if kind=='brake' else .45 if kind=='combined' else 0.) if post else 0.
        sample={'frame':10+i,'sim_time_s':i*.05,'planar_speed_mps':5.,
            'speed_mps':5.,'vertical_speed_mps':0.,'command_throttle':.7 if not post else 0.,
            'command_brake':brake,'command_steer':steer,
            'actual_throttle':.7 if not post else 0.,'actual_brake':brake,
            'actual_steer':steer,
            'signed_longitudinal_accel_mps2':-2. if post else 0.,
            'yaw_rate_radps_carla':.01 if steer else 0.,
            'command_reference_sim_time_s':(i-1)*.05 if i else -.05,
            'wheel_steer_deg_front_left_raw':1. if steer else 0.,
            'wheel_steer_deg_front_right_raw':1. if steer else 0.,
            'wheel_steer_query_error':None,'command_issued_before_tick':True,
            'lane_audit':{'status':'DESCRIPTIVE_RECTANGLE_WITHIN_LANE'}}
        samples.append(sample)
    return {'schema':'rampd.carla.a59_1.raw_trials.v1',
        'experiment_scope':'SINGLE_CONTROL_SMOKE',
        'status':'RAW_CARLA_TRIALS_CAPTURED_NOT_CERTIFIED',
        'carla_server_version':'0.9.16','map':'Carla/Maps/Town06_Opt',
        'world_exclusive_confirmed':True,'actor_type':'vehicle.tesla.model3',
        'calibrated_vehicle_dynamics':False,'step_s':.05,'actor_id':101,
        'physics':{'actor_type':'vehicle.tesla.model3','wheels':[{} for _ in range(4)]},
        'site_audit':{'chosen_start_projection_audit':{'status':'DESCRIPTIVE_LANE_IDENTITY_REPRODUCED'}},
        'start_lane_recheck':{'accepted':True},
        'trials':[{'status':'CAPTURED','target_speed_mps':5,'maneuver':kind,
                   'trigger_frame':15,'trigger_speed_mps':5.,'settling':stable,'actor_id':101,
                   'samples':samples}]}


def test_all_control_types_accept_only_descriptively():
    for kind in ('brake','steer','combined'):
        r=audit_single_control_smoke(one_smoke(kind))
        assert r['status']=='DESCRIPTIVE_SINGLE_CONTROL_SMOKE_CAPTURED_NOT_CALIBRATED',r
        assert not r['physical_certified'] and not r['safe_training_labels_allowed']


def test_no_false_success_from_pretrial_readiness_uploaded_shape():
    d=json.loads((ROOT/'tests/fixtures/a63_readiness_abort_excerpt.json').read_text())
    r=audit_single_control_smoke(d)
    assert r['status']=='REVIEW' and 'NOT_A_SINGLE_CONTROL_SMOKE' in r['reasons']


def test_missing_trigger_or_post_control_rejected():
    d=one_smoke(); d['trials'][0]['trigger_frame']=-1
    assert audit_single_control_smoke(d)['status']=='REVIEW'
    d=one_smoke();d['trials'][0]['samples']=d['trials'][0]['samples'][:7]
    assert 'INCOMPLETE_TWO_SECOND_POSTCONTROL_WINDOW' in audit_single_control_smoke(d)['reasons']


def test_steer_without_real_wheel_angle_rejected():
    d=one_smoke('steer')
    for s in d['trials'][0]['samples']:
        s['wheel_steer_deg_front_left_raw']=0.
        s['wheel_steer_deg_front_right_raw']=0.
    assert 'NO_MEASURABLE_FRONT_WHEEL_STEER_RESPONSE' in audit_single_control_smoke(d)['reasons']


def test_broken_command_clock_lane_and_velocity_rejected():
    d=one_smoke('brake');d['trials'][0]['samples'][10]['command_reference_sim_time_s']=999
    assert 'COMMAND_REFERENCE_TIME_MISMATCH' in audit_single_control_smoke(d)['reasons']
    d=one_smoke('brake');d['trials'][0]['samples'][10]['lane_audit']['status']='REVIEW'
    assert 'LANE_ENVELOPE_UNVERIFIED' in audit_single_control_smoke(d)['reasons']
    d=one_smoke('brake');d['trials'][0]['samples'][10]['speed_mps']=10
    assert 'SPEED_COMPONENT_INCONSISTENCY' in audit_single_control_smoke(d)['reasons']


def test_wrong_actor_or_applied_command_rejected():
    d=one_smoke();d['trials'][0]['actor_id']=999
    assert 'ACTOR_ID_NOT_BOUND_TO_TRIAL' in audit_single_control_smoke(d)['reasons']
    d=one_smoke();d['trials'][0]['samples'][8]['actual_brake']=0.0
    assert 'APPLIED_CONTROL_DIFFERS_FROM_COMMAND' in audit_single_control_smoke(d)['reasons']


def test_missing_site_physics_or_lane_identity_rejected():
    d=one_smoke();d['site_audit']={}
    assert 'START_SITE_IDENTITY_UNVERIFIED' in audit_single_control_smoke(d)['reasons']
    d=one_smoke();d['physics']['wheels']=[]
    assert 'ACTOR_PHYSICS_NOT_CAPTURED' in audit_single_control_smoke(d)['reasons']


def test_all_zero_vehicle_commands_never_count_as_control():
    d=one_smoke()
    for s in d['trials'][0]['samples'][6:]:s['command_brake']=0.
    assert 'CONTROL_EXCITATION_NOT_COMMANDED' in audit_single_control_smoke(d)['reasons']


def handoff_gate():
    return partition_clock_worlds((ClockWorld('a',(),declared_complete=True,public_history_id='h'),
                                   ClockWorld('b',(),declared_complete=True,public_history_id='h')),
                                  start=Q(0),end=Q(1))


def test_exact_one_slab_all_worlds():
    gate=handoff_gate()
    assert gate.status=='CONDITIONAL_EXACT_MODEL_HYBRID_PARTITION_READY'
    rows=tuple(SlabHandoff(w,Q(0),Q(1),((Q(0),Q(1)),),((Q(0),Q(2)),)) for w in ('a','b'))
    out=audit_slab_handoffs(gate,rows)
    assert out['status']=='CONDITIONAL_RATIONAL_SLAB_HANDOFFS_CONSISTENT_NOT_CERTIFIED'
    assert not out['native_picard_replayed'] and not out['safety_certified']
    assert audit_slab_handoffs(gate,rows[:1])['status']=='UNKNOWN'


def test_interval_handoff_direction_and_missing_slabs():
    # Use a hand-constructed two-slab gate with the structure of the real gate.
    from rampd_core.a61_hybrid_partition import AtomicClockSlab,HybridClockGate
    gate=HybridClockGate('CONDITIONAL_EXACT_MODEL_HYBRID_PARTITION_READY',(),
      (AtomicClockSlab(Q(0),Q(1,2),(),()),AtomicClockSlab(Q(1,2),Q(1),(),())),
      (),((Q(0),Q(1,2),(((),('a',)),)),(Q(1,2),Q(1),(((),('a',)),))),False)
    a=SlabHandoff('a',Q(0),Q(1,2),((Q(0),Q(1)),),((Q(-1),Q(2)),))
    b=SlabHandoff('a',Q(1,2),Q(1),((Q(-1),Q(2)),),((Q(-2),Q(3)),))
    assert audit_slab_handoffs(gate,(a,b))['status'].startswith('CONDITIONAL_')
    bad=SlabHandoff('a',Q(1,2),Q(1),((Q(0),Q(1)),),((Q(0),Q(2)),))
    assert any('ENDPOINT_NOT_ENCLOSED_BY_NEXT_START' in x
               for x in audit_slab_handoffs(gate,(a,bad))['reasons'])


def test_exact_rational_time_required():
    import pytest
    with pytest.raises(ValueError):SlabHandoff('a',0.,Q(1),((Q(0),Q(1)),),((Q(0),Q(1)),))
    with pytest.raises(TypeError):SlabHandoff('a',Q(0),Q(1),((0.,Q(1)),),((Q(0),Q(1)),))


def test_smoke_mode_cannot_silently_launch_full_27_trials():
    spec=importlib.util.spec_from_file_location(
        'a64_carla_driver',ROOT/'scripts'/'a60_carla_actor_trials.py')
    driver=importlib.util.module_from_spec(spec);spec.loader.exec_module(driver)
    assert driver.controlled_trial_matrix('smoke',3,5,'brake')==((5,'brake',0),)
    full=driver.controlled_trial_matrix('trials',3,5,'brake')
    assert len(full)==27 and len(set(full))==27
    assert len(driver.controlled_trial_matrix('trials',1,5,'brake'))==9
    import pytest
    with pytest.raises(ValueError):driver.controlled_trial_matrix('readiness',3,5,'brake')
