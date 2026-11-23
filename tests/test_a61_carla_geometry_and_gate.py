"""A59/1b-0 falsification: CARLA physical evidence, clock branches and conflicts."""
from __future__ import annotations
from fractions import Fraction as Q
from pathlib import Path
from types import SimpleNamespace as NS
import copy, importlib.util, json, sys
import pytest
from rampd_core.a61_carla_calibration import reconstruct_actor_geometry,describe_control_trials
from rampd_core.a60_clock_resource import ClockEvent
from rampd_core.a61_hybrid_partition import ClockWorld, partition_clock_worlds, audit_multiresource_conflicts
from rampd_core.interval import Interval
from rampd_core.resources import ResourceRegion
from rampd_core.footprint import SweptFootprint,VehicleGeometry
from rampd_core.model import StateBounds

ROOT=Path(__file__).resolve().parents[1]
CARLA=ROOT/'scripts'/'a60_carla_actor_trials.py'
spec=importlib.util.spec_from_file_location('a61_carla_capture',CARLA)
script=importlib.util.module_from_spec(spec);spec.loader.exec_module(script)

def synthetic_meta():
    # Actor + wheel world coordinates in centimeters; heading 0.
    wheel=lambda x,y,angle:{'position_raw':{'x':100*x,'y':100*y,'z':0},
       'max_steer_angle_deg_raw':angle}
    return {'physics':{'actor_type':'vehicle.tesla.model3',
        'body_transform':{'location':{'x':100,'y':5,'z':0},
                          'rotation':{'yaw_deg':0}},
        'wheels':[wheel(101.5,5.8,70),wheel(101.5,4.2,70),wheel(98.5,5.8,0),wheel(98.5,4.2,0)],
        'bounding_box':{'location_local':{'x':0,'y':0},'extent':{'x':2.4,'y':1.1},
                        'rotation_local':{'yaw_deg':0}}}}


def test_world_centimeter_wheel_geometry_requires_pose_and_correct_front_rear():
    p=reconstruct_actor_geometry(synthetic_meta())
    assert p['status']=='DESCRIPTIVE_CARLA_ACTOR_GEOMETRY_RECONSTRUCTED'
    assert p['wheel_position_unit_hypothesis']=='world_cm'
    assert p['wheelbase_from_axle_centroids_m']==pytest.approx(3.0)
    assert p['rear_axle_to_bbox_center_x_m']==pytest.approx(1.5)
    assert p['front_overhang_m']==pytest.approx(.9)
    assert p['rear_overhang_m']==pytest.approx(.9)
    assert p['certified_physical_geometry'] is False


def test_pre_tick_zero_actor_pose_does_not_get_silently_used():
    d=synthetic_meta();d['physics']['body_transform']['location']['x']=0
    assert 'NO_VALID_ACTOR_OR_REQUESTED_SPAWN_POSE_FOR_AXLE_OFFSET' in reconstruct_actor_geometry(d)['reasons']
    d['site_audit']={'chosen_waypoint':{'x_m':100.,'y_m':5.,'yaw_deg':0.}}
    assert reconstruct_actor_geometry(d)['pose_source']=='requested_spawn_waypoint'


def test_wrong_raw_scale_and_reversed_axles_fail_closed():
    p=synthetic_meta()
    for w in p['physics']['wheels']:w['position_raw']['x']*=10
    assert reconstruct_actor_geometry(p)['status']=='REVIEW'
    q=synthetic_meta()
    for w in q['physics']['wheels']:w['max_steer_angle_deg_raw']=70-w['max_steer_angle_deg_raw']
    assert reconstruct_actor_geometry(q)['status']=='REVIEW'


def test_actor_angle_reader_uses_actual_0916_enum_names(monkeypatch):
    class Vehicle:
        def get_transform(self):return NS(location=NS(x=0.,y=0.,z=0.),rotation=NS(yaw=0.))
        def get_velocity(self):return NS(x=4.,y=0.,z=0.)
        def get_acceleration(self):return NS(x=1.,y=0.,z=0.)
        def get_angular_velocity(self):return NS(z=0.)
        def get_control(self):return NS(throttle=0.,brake=.2,steer=.08)
        def get_wheel_steer_angle(self,w):return {'FL_Wheel':3.0,'FR_Wheel':3.2}[w]
    monkeypatch.setitem(sys.modules,'carla',NS(VehicleWheelLocation=NS(FL_Wheel='FL_Wheel',FR_Wheel='FR_Wheel')))
    sample=script.observe(Vehicle(),None,NS(frame=1,timestamp=NS(elapsed_seconds=.05)),
                         NS(throttle=0.,brake=.2,steer=.08),0.)
    assert sample['wheel_steer_deg_front_left_raw']==3.0
    assert sample['wheel_steer_deg_front_right_raw']==3.2
    assert sample['wheel_steer_query_error'] is None


def test_wheel_angle_api_errors_are_recorded_not_silently_zero(monkeypatch):
    class Vehicle:
        def get_transform(self):return NS(location=NS(x=0.,y=0.,z=0.),rotation=NS(yaw=0.))
        def get_velocity(self):return NS(x=4.,y=0.,z=0.)
        def get_acceleration(self):return NS(x=1.,y=0.,z=0.)
        def get_angular_velocity(self):return NS(z=0.)
        def get_control(self):return NS(throttle=0.,brake=.2,steer=.08)
        def get_wheel_steer_angle(self,w):raise RuntimeError('wheel not supported')
    monkeypatch.setitem(sys.modules,'carla',NS(VehicleWheelLocation=NS(FL_Wheel='FL_Wheel',FR_Wheel='FR_Wheel')))
    sample=script.observe(Vehicle(),None,NS(frame=1,timestamp=NS(elapsed_seconds=.05)),
                         NS(throttle=0.,brake=.2,steer=.08),0.)
    assert sample['wheel_steer_deg_front_left_raw'] is None
    assert 'wheel not supported' in sample['wheel_steer_query_error']


def e(eid,kind,t,domain='EXACT_MODEL',corr=''):
    return ClockEvent(eid,kind,Q(t),'synthetic',corr,domain)


def test_hidden_rule_changes_are_not_public_observations():
    a=ClockWorld('hidden_A',(e('a','RULE_EFFECTIVE',Q(1,2)),),declared_complete=True,public_history_id='h0')
    b=ClockWorld('hidden_B',(),declared_complete=True,public_history_id='h0')
    out=partition_clock_worlds((a,b),start=Q(0),end=Q(1))
    assert out.status=='CONDITIONAL_EXACT_MODEL_HYBRID_PARTITION_READY'
    assert [(s.start,s.end) for s in out.slabs]==[(Q(0),Q(1,2)),(Q(1,2),Q(1))]
    assert out.posterior_worlds==(((),('hidden_A','hidden_B')),)
    assert out.certified is False


def test_public_receipt_splits_belief_only_when_token_explicit_and_issue_precedes():
    ev=(e('msg','ISSUE',Q(1,4),corr='c'),e('msg','RECEIPT',Q(3,4),corr='c'))
    x=ClockWorld('received',ev,(('msg','payload_seen'),),True,'h0')
    y=ClockWorld('silent',(),(),True,'h0')
    out=partition_clock_worlds((x,y),start=Q(0),end=Q(1))
    assert out.status=='CONDITIONAL_EXACT_MODEL_HYBRID_PARTITION_READY'
    assert len(out.posterior_worlds)==2
    no_token=partition_clock_worlds((ClockWorld('received',ev,(),True,'h0'),y),start=Q(0),end=Q(1))
    assert no_token.status=='UNKNOWN'
    assert any('PUBLIC_EVENT_WITHOUT_OBSERVATION_TOKEN' in r for r in no_token.reasons)


def test_external_report_and_unacknowledged_command_cannot_prove_hybrid_clock():
    ext=ClockWorld('ext',(e('incident','RULE_EFFECTIVE',Q(1,2),'EXTERNAL_REPORT'),),(),True,'h0')
    out=partition_clock_worlds((ext,),start=Q(0),end=Q(1))
    assert out.status=='UNKNOWN'
    cmd=ClockWorld('cmd',(e('sig','COMMAND',Q(1,2)),),(),True,'h0')
    out=partition_clock_worlds((cmd,),start=Q(0),end=Q(1))
    assert 'cmd:MISSING_ACTUATION_ACK:sig' in out.reasons


def test_clock_support_completeness_is_explicit_not_inferred_from_empty_world():
    out=partition_clock_worlds((ClockWorld('unknown',(),(),False,'h0'),),start=Q(0),end=Q(1))
    assert out.status=='UNKNOWN'
    assert any('INCOMPLETE_CLOCK_EVENT_SUPPORT' in r for r in out.reasons)


def footprint(x,y,lo=Q(0),hi=Q(1)):
    return SweptFootprint(StateBounds(Interval.point(x),Interval.point(y),Interval.point(0),
             Interval.point(0),Interval.point(0),Interval.point(0)),VehicleGeometry(1,1),lo,hi,'actor')


def test_multiresource_conflict_between_different_actors_is_unknown():
    regions={'a':ResourceRegion('a',Interval(0,2),Interval(0,2)),
             'b':ResourceRegion('b',Interval(10,12),Interval(0,2))}
    slabs=[(Q(0),Q(1),{'ego':footprint(1,1),'other':footprint(11,1)})]
    out=audit_multiresource_conflicts(regions=regions,conflict_pairs=(('a','b'),),
            actor_slices=slabs,complete_resource_graph=True,complete_actor_roster=True)
    assert out['status']=='UNKNOWN'
    assert any('POSSIBLE_CONFLICTING_DISTINCT_ACTORS' in x for x in out['reasons'])
    free=audit_multiresource_conflicts(regions=regions,conflict_pairs=(('a','b'),),
            actor_slices=[(Q(0),Q(1),{'ego':footprint(100,100),'other':footprint(101,101)})],
            complete_resource_graph=True,complete_actor_roster=True)
    assert free['status']=='CONDITIONAL_DECLARED_RECTANGULAR_CONFLICT_SCREEN_PASS'
    assert not free['certified']


def test_unproven_graph_or_actor_roster_fails_closed():
    r={'a':ResourceRegion('a',Interval(0,2),Interval(0,2))}
    out=audit_multiresource_conflicts(regions=r,conflict_pairs=(),
        actor_slices=[(Q(0),Q(1),{'ego':footprint(100,100)})],
        complete_resource_graph=False,complete_actor_roster=False)
    assert out['status']=='UNKNOWN'


def test_no_actual_carla_required_for_diagnostic_and_no_guarantee(tmp_path):
    p=synthetic_meta();g=reconstruct_actor_geometry(p)
    assert not g['certified_physical_geometry']
    assert describe_control_trials({'schema':'wrong'})['status']=='REVIEW'


def test_initial_public_history_mismatch_cannot_merge_hidden_worlds():
    a=ClockWorld('a',(),(),True,'history_a')
    b=ClockWorld('b',(),(),True,'history_b')
    z=partition_clock_worlds((a,b),start=Q(0),end=Q(1))
    assert z.status=='UNKNOWN'
    assert 'INCOMPATIBLE_INITIAL_PUBLIC_HISTORIES' in z.reasons
    q=partition_clock_worlds((ClockWorld('unset',(),(),True),),start=Q(0),end=Q(1))
    assert 'MISSING_INITIAL_PUBLIC_HISTORY_ID' in q.reasons


def test_future_receipt_cannot_split_control_before_its_timestamp():
    x=ClockWorld('x',(e('msg','ISSUE',Q(1,4),corr='c'),
                      e('msg','RECEIPT',Q(3,4),corr='c')),
                 (('msg','visible_update'),),True,'h0')
    y=ClockWorld('y',(),(),True,'h0')
    result=partition_clock_worlds((x,y),start=Q(0),end=Q(1))
    assert result.status=='CONDITIONAL_EXACT_MODEL_HYBRID_PARTITION_READY'
    # Even though final histories differ, control through the third quarter is public-common.
    for lo,hi,groups in result.posterior_worlds_by_slab:
        if lo<Q(3,4):
            assert groups==(((),('x','y')),)
        else:
            assert len(groups)==2
    assert not result.certified


def test_async_capture_waits_for_live_actor_pose_not_initial_zero():
    class World:
        count=0
        def wait_for_tick(self,timeout):
            self.count+=1
            assert timeout>0
            return NS(frame=500+self.count)
    class Actor:
        def __init__(self,w):self.w=w
        def get_transform(self):
            return NS(location=NS(x=0.,y=0.) if self.w.count<2 else NS(x=100.,y=20.))
    w=World();pose=NS(location=NS(x=100.,y=20.))
    assert script.await_async_actor_pose(w,Actor(w),pose)==502
    assert w.count==2
    class StaleActor:
        def get_transform(self):return NS(location=NS(x=0.,y=0.))
    with pytest.raises(RuntimeError,match='REVIEW_STALE_ASYNC_ACTOR_TRANSFORM'):
        script.await_async_actor_pose(w,StaleActor(),pose,max_frames=2)
