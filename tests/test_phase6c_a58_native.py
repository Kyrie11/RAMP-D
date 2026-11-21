"""Server-side native/Picard proof obligations for A58. Requires MPFR .so."""
from fractions import Fraction as Q
from rampd_core.a58_native_safety import PhysicalLimits, guarded_physical_post
from rampd_core.a57_native_guard import NativeParent
from rampd_core.a53b_actor_envelope import ActorEnvelope
from rampd_core.belief import SupportAtom
from rampd_core.model import StateBounds,ControlBounds,BicycleParameters
from rampd_core.interval import Interval
from rampd_core.footprint import VehicleGeometry
from rampd_core.resources import ResourceRegion
from test_phase6c_a56 import controller

LIM=PhysicalLimits(30,-8,3,.5,3,.2)
def args(actor=None,initial=(0,0,0,1,0,0),resource_start=10):
    other=() if actor is None else tuple(zip(actor.keys,(Interval.point(1.5),Interval.point(0),Interval.point(0),Interval.point(0),Interval.point(0))))
    p=NativeParent(SupportAtom('e',StateBounds.point(initial),other),controller(),() if actor is None else (actor,),readiness=(True,))
    return dict(parents=(p,),control=ControlBounds.point(0,0),params=BicycleParameters(2.8,.9),
        ego_geometry=VehicleGeometry(2,1),disturbance=(Interval.point(0),)*6,
        resource=ResourceRegion('r',Interval(resource_start,resource_start+10),Interval(-2,2)),
        queue_a=ResourceRegion('qa',Interval(-3,3),Interval(-2,2)),
        queue_b=ResourceRegion('qb',Interval(-3,3),Interval(4,8)),limits=LIM)


def test_a58_declared_safe_disjoint_but_not_task_winning():
    status,post,tubes,a=guarded_physical_post(**args())
    assert a.status=='CONDITIONAL_EGO_AVOIDANCE_PASS'
    assert a.parent_audits[0].slabs_checked>0 and not a.safe_continuation_certified
    assert not a.full_real_world_support_certified and not a.task_complete
    assert 'silence' in post


def test_a58_resource_entry_must_be_unknown_without_topology():
    x=args(initial=(14,0,0,1,0,0))
    _,_,_,a=guarded_physical_post(**x)
    assert a.status=='UNKNOWN' and 'UNKNOWN_RESOURCE_ENTRY_EXIT_OR_PERMISSION' in a.parent_audits[0].reasons


def test_a58_actor_collision_not_silently_certified():
    actor=ActorEnvelope('f',VehicleGeometry(2,1),Interval.point(0),Interval.point(0),Interval.point(0),'test')
    x=args(actor=actor)
    _,_,_,a=guarded_physical_post(**x)
    assert a.status=='UNKNOWN' and any('UNKNOWN_EGO_ACTOR_COLLISION' in s for s in a.parent_audits[0].reasons)


def test_a58_control_actuator_limit_fails_closed():
    x=args();x['control']=ControlBounds.point(4,0)
    _,_,_,a=guarded_physical_post(**x)
    assert a.status=='UNKNOWN' and 'CONTROL_OR_DISTURBANCE_OUTSIDE_ACTUATOR_LIMITS' in a.parent_audits[0].reasons


def test_a58_disturbance_jerk_rate_is_checked_not_just_command():
    x=args()
    x['disturbance']=(Interval.point(0),)*4+(Interval.point(4),Interval.point(0))
    _,_,_,a=guarded_physical_post(**x)
    assert a.status=='UNKNOWN'
    assert 'CONTROL_OR_DISTURBANCE_OUTSIDE_ACTUATOR_LIMITS' in a.parent_audits[0].reasons


def test_a58_support_budget_unknown_not_partial_success():
    x=args()
    from dataclasses import replace
    x['parents']=(replace(x['parents'][0],readiness=(False,True)),)
    x['max_cases']=1
    status,post,tubes,a=guarded_physical_post(**x)
    assert status=='UNKNOWN' and post=={} and tubes=={}
    assert a.status=='UNKNOWN' and not a.safe_continuation_certified
    assert 'UNKNOWN_NATIVE_POST_OR_SUPPORT_BUDGET' in a.parent_audits[0].reasons
