from fractions import Fraction as Q
from dataclasses import replace
import pytest
from rampd_core.a58_jerk import (Longitudinal,JerkLeg,propagate,plan_stop,nominal_stop_invariant)
from rampd_core.a58_closure_evidence import (Pose2,BarrierDesign,PhysicalFrame,audit_barrier_frame)
from rampd_core.a58_roadwork_templates import template_from_manifest_row
from rampd_core.a58_sumo_audit import audit_runs


def test_analytic_stop_matches_a56_profile_and_invariant():
    p=plan_stop(Longitudinal(Q(0),Q(10),Q(0)),comfort_decel=Q(5,2),jerk_limit=Q(5,2))
    assert p.total_time==5 and p.stopping_distance==25
    assert p.final==Longitudinal(Q(25),Q(0),Q(0))
    assert [l.duration for l in p.legs]==[Q(1),Q(3),Q(1)]
    assert nominal_stop_invariant(p,jerk_after=Q(0),steering_rate_after=Q(0),disturbances_zero=True)
    assert not nominal_stop_invariant(p,jerk_after=Q(0),steering_rate_after=Q(0),disturbances_zero=False)


def test_arbitrary_initial_acceleration_and_delay_are_not_clipped():
    init=Longitudinal(Q(2),Q(12),Q(1))
    p=plan_stop(init,comfort_decel=Q(3),jerk_limit=Q(2),delay=Q(1,2),accel_min=Q(-5),accel_max=Q(2))
    assert p.after_delay==Longitudinal(Q(2)+Q(49,8),Q(25,2),Q(1)) # x=2 + 6 + 1/8
    assert p.final.v==p.final.a==0
    assert p.final.x>p.after_delay.x
    assert p.total_time>p.delay
    assert p.stopping_distance>0


def test_short_stop_does_not_silently_invent_jerk_triangular_solution():
    with pytest.raises(ValueError,match='UNKNOWN_TRIANGULAR'):
        plan_stop(Longitudinal(Q(0),Q(1),Q(0)),comfort_decel=Q(4),jerk_limit=Q(2))
    with pytest.raises(ValueError,match='speed crosses'):
        propagate(Longitudinal(Q(0),Q(1),Q(-4)),JerkLeg(Q(1),Q(0)))
    with pytest.raises(ValueError,match='exceeds actuator braking capability'):
        plan_stop(Longitudinal(Q(0),Q(10),Q(0)),comfort_decel=Q(4),jerk_limit=Q(2),accel_min=Q(-3))
    with pytest.raises(TypeError):plan_stop(Longitudinal(Q(0),Q(10),Q(0)),comfort_decel=2.5,jerk_limit=Q(2))


def test_resting_state_requires_zero_accel_and_disturbance():
    p=plan_stop(Longitudinal(Q(0),Q(0),Q(0)),comfort_decel=Q(2),jerk_limit=Q(2))
    assert p.holds_invariant_nominally and not p.legs
    assert not nominal_stop_invariant(p,jerk_after=Q(1),steering_rate_after=Q(0),disturbances_zero=True)


def barrier_and_frame():
    d=BarrierDesign('e',2,'r','deploy-9',17,Pose2(12,0,0),.2,.1)
    f=PhysicalFrame(Q(2),20,Q(2),((17,Pose2(12.01,.01,.01)),),(),True,True,False)
    return d,f


def test_monitor_frame_sampled_success_no_continuous_claim():
    d,f=barrier_and_frame()
    r=audit_barrier_frame(d,f,protected_aabb=(10,-2,15,2))
    assert r.status=='SAMPLED_FRAME_PASS' and r.observed_present
    assert not r.continuous_coverage_proved and not r.ready_to_reopen

@pytest.mark.parametrize('mutation,why',[
    ({'barrier_poses':()},'BARRIER_ACTOR_MISSING'),
    ({'barrier_poses':((17,Pose2(14,0,0)),)},'BARRIER_DISPLACED'),
    ({'barrier_poses':((17,Pose2(12,0,.4)),)},'BARRIER_ROTATED'),
    ({'observations_complete':False},'ROSTER_OR_OBSERVATION_INCOMPLETE'),
    ({'outstanding_commands':True},'UNSETTLED_COMMANDS'),
    ({'detected_vehicle_boxes':((11,-1,12,1),)},'VEHICLE_INSIDE_PROTECTED_REGION')])
def test_monitor_fault_cases(mutation,why):
    d,f=barrier_and_frame();r=audit_barrier_frame(d,replace(f,**mutation),protected_aabb=(10,-2,15,2))
    assert r.status=='REVIEW_OR_FAULT' and r.reason==why


def test_monitor_time_mismatch_and_duplicate_actor():
    _,f=barrier_and_frame()
    with pytest.raises(ValueError):replace(f,sumo_time=Q(3))
    with pytest.raises(ValueError):replace(f,barrier_poses=(f.barrier_poses[0],f.barrier_poses[0]))


def test_roadwork_template_is_lossless_and_not_a_formal_label():
    row={'group':'video:v1','source_annotation_sha256':'shasum','source_split':'train','file_name':'f.jpg','image_id':31,
    'scene_tags':{'travel_alteration':['partial']},'objects':[
        {'id':1,'category':'cone','bbox_usable':True,'bbox':[1,2,3,4],'attributes':{'orange':True}},
        {'id':2,'category':'cone','bbox_usable':True,'bbox':[5,6,7,8]}]}
    t=template_from_manifest_row(row)
    assert t['object_count_by_class']=={'cone':2}
    assert t['source']['objects'][0]['attributes']=={'orange':True}
    assert t['formal_traffic_rule'] is None and t['physical_world_positions'] is None
    assert t==template_from_manifest_row(row)
    with pytest.raises(ValueError):template_from_manifest_row({**row,'objects':[{**row['objects'][0],'bbox_usable':False}]})


def test_sumo_audit_fails_on_comfort_and_unverified_terminal(tmp_path):
    import json
    def doc(seed,brakes,complete=True):return {'scope':'TRAFFIC_ACTUATED_LOGICAL_CORRIDOR_NOT_PHYSICAL_SINGLE_LANE','seed':seed,
        'departed_count':70,'arrived_count':70,'roster_completion_pass':complete,'drained_at_cutoff':True,
        'brake_steps':[{}]*brakes,'comfort_review_required':False,'violations':[],'transitions':[{}], 'status':'SUMO_LOGICAL_CORRIDOR_PASS'}
    a=tmp_path/'a.json';b=tmp_path/'b.json'
    a.write_text(json.dumps(doc(1,0)));b.write_text(json.dumps(doc(2,4)))
    r=audit_runs((a,b,));assert r['status']=='REVIEW' and r['runs'][0]['result']=='PASS_SCOPED'
    assert not r['terminal_tail_certified']
    with pytest.raises(ValueError,match='repeated seed'):audit_runs((a,a))


def test_rear_reference_no_slip_and_calibration_provenance():
    from math import sin,cos
    from rampd_core.a58_frames import FrameCalibration,transform_observed_center
    c=FrameCalibration(1.4,0,2.8,'calibrated-box',.03)
    yaw=.4;rear_speed=9;yaw_rate=.25
    vx=rear_speed*cos(yaw)-yaw_rate*1.4*sin(yaw)
    vy=rear_speed*sin(yaw)+yaw_rate*1.4*cos(yaw)
    out=transform_observed_center(10+1.4*cos(yaw),4+1.4*sin(yaw),yaw,vx,vy,yaw_rate,c)
    assert out['status']=='KINEMATIC_REFERENCE_NOMINAL_PASS'
    assert out['rear_px']==pytest.approx(10) and out['rear_py']==pytest.approx(4)
    assert out['rear_speed_model']==pytest.approx(9)
    assert transform_observed_center(10,4,yaw,vx,vy+2,yaw_rate,c)['status']=='UNKNOWN_NO_SLIP_MODEL'
    assert not out['certified_physical']


def test_sumo_stress_profiles_are_not_just_seed_changes():
    from rampd_core.a58_sumo_profiles import get_profile
    base=get_profile('baseline');assert base.expected_vehicles==70
    dense=get_profile('dense');assert dense.expected_vehicles>base.expected_vehicles
    assert dense.sigma>0 and dense.speed_dev>0
    assert get_profile('slow_reaction').tau>base.tau
    with pytest.raises(ValueError):get_profile('not_a_profile')


def test_cosim_single_owner_and_sensor_clock():
    from rampd_core.a58_cosim_contract import CoSimAuthority,CoSimPair,audit_pair
    c=CoSimAuthority(Q(1,10),'CARLA','SUMO','SUMO','a'*64)
    p=CoSimPair(0,100,Q(0),Q(0),None)
    q=CoSimPair(1,101,Q(1,10),Q(1,10),Q(0))
    assert audit_pair(c,p,q).startswith('FRAME_STEP_CONSISTENCY')
    assert audit_pair(c,p,replace(q,sumo_time=Q(1,5)))=='UNKNOWN_TIME_DRIFT'
    assert audit_pair(c,p,replace(q,carla_frame=105))=='UNKNOWN_FRAME_DROP'
    assert audit_pair(c,p,replace(q,delivered_sensor_time=Q(1,5)))=='UNKNOWN_SENSOR_TIME_FROM_FUTURE'
    with pytest.raises(ValueError):CoSimAuthority(Q(1,10),'CARLA','CARLA','SUMO','a'*64)


def test_turning_reference_matches_analytic_constant_curvature_arc():
    """Independent RK4 *numerical* arc reference; not proof-grade enclosure."""
    from math import tan,sin,cos
    from rampd_core.a57_motion import bicycle_reference
    v,delta,L,h=7.,.18,2.8,1.25
    omega=v*tan(delta)/L
    r=bicycle_reference((0,0,0,v,0,delta),(0,0),h,L,100)
    assert r[0]==pytest.approx(v*sin(omega*h)/omega,abs=1e-9)
    assert r[1]==pytest.approx(v*(1-cos(omega*h))/omega,abs=1e-9)
    assert r[2]==pytest.approx(omega*h,abs=1e-9)


def test_turning_jerk_steer_rate_reference_converges_but_not_certified():
    from rampd_core.a57_motion import bicycle_reference,nominal_control_screen
    state=(0,0,.2,8,-.3,.03);control=(-.8,.05);h=1.5
    p1=bicycle_reference(state,control,h,2.8,50)
    p2=bicycle_reference(state,control,h,2.8,100)
    p3=bicycle_reference(state,control,h,2.8,200)
    e12=max(abs(a-b) for a,b in zip(p1,p2))
    e23=max(abs(a-b) for a,b in zip(p2,p3))
    assert e23<e12 and e23<1e-6
    screen=nominal_control_screen(state,control,h,wheelbase=2.8,mu=.8,
        a_min=-5,a_max=3,jerk_max=2,steering_max=.5,steering_rate_max=.2,v_max=30)
    assert screen['screen_pass'] and not screen['certificate']
