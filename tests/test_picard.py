from dataclasses import replace
from fractions import Fraction as Q
import math
import mpmath as mp
import pytest
from rampd_core import *
from rampd_core.certificate import to_dict

P = BicycleParameters(2.8,.9)
U = ControlBounds.point(0,0)
X = StateBounds.point([0,0,0,8,0,0])

def require_valid(result):
    assert result.status == TubeStatus.VALIDATED, (result.reason,result.stats)
    assert result.endpoint is not None
    assert result.validated_until == Q(result.requested_horizon_s)
    assert all(check_witness(s.witness,result.control,result.params,result.disturbance) for s in result.segments)
    assert replay_certificate(to_dict(result)).ok

@pytest.mark.parametrize("h", [.001, .1, .125, 1.0])
def test_constant_velocity_exact_rational_at_all_sampled_subtimes(h):
    r = integrate(X,U,P,h)
    require_valid(r)
    for seg in r.segments:
        for k in range(33):
            t = seg.start_time + Q(seg.witness.duration_s)*k/32
            exact = [8*t,Q(0),Q(0),Q(8),Q(0),Q(0)]
            for a,v in zip(seg.witness.tube.as_tuple(),exact): assert Q(a.lo) <= v <= Q(a.hi)
        for a,v in zip(seg.witness.endpoint.as_tuple(),[8*seg.end_time,0,0,8,0,0]):
            assert Q(a.lo) <= v <= Q(a.hi)

@pytest.mark.parametrize("jerk", [-2.0,0.0,1.5])
def test_constant_jerk_exact_rational(jerk):
    x = StateBounds.point([1,0,0,5,.25,0]); u = ControlBounds.point(jerk,0)
    r = integrate(x,u,P,1.25); require_valid(r)
    def solution(t):
        return [Q(1)+5*t+Q(1,8)*t*t+Q(jerk)*t**3/6,0,0,
                Q(5)+Q(1,4)*t+Q(jerk)*t*t/2,Q(1,4)+Q(jerk)*t,0]
    for s in r.segments:
        for k in range(17):
            exact = solution(s.start_time+Q(s.witness.duration_s)*k/16)
            for a,v in zip(s.witness.tube.as_tuple(),exact): assert Q(a.lo)<=v<=Q(a.hi)
        for a,v in zip(s.witness.endpoint.as_tuple(),solution(s.end_time)): assert Q(a.lo)<=v<=Q(a.hi)

@pytest.mark.parametrize("steering", [-.2,.2])
def test_constant_steering_circle_high_precision_audit(steering):
    x = StateBounds.point([1,2,.3,7,0,steering]); r = integrate(x,U,P,1.0); require_valid(r)
    with mp.workdps(100):
        psi0,v,L,d = map(mp.mpf,(.3,7,P.wheelbase_m,steering))
        om = v*mp.tan(d)/L
        for s in r.segments:
            for k in range(17):
                t = s.start_time + Q(s.witness.duration_s)*k/16
                tt = mp.mpf(t.numerator)/t.denominator
                psi=psi0+om*tt
                vals=[1+v/om*(mp.sin(psi)-mp.sin(psi0)),
                      2-v/om*(mp.cos(psi)-mp.cos(psi0)),psi,v,mp.mpf(0),d]
                for a,value in zip(s.witness.tube.as_tuple(),vals):
                    assert mp.mpf(a.lo)<=value<=mp.mpf(a.hi)
            for a,value in zip(s.witness.endpoint.as_tuple(),vals):
                assert mp.mpf(a.lo)<=value<=mp.mpf(a.hi)

def test_interval_initial_state_and_control_corners():
    x = StateBounds(Interval(-.1,.1),Interval(0,0),Interval(0,0),Interval(4,5),Interval(-.2,.3),Interval(0,0))
    u = ControlBounds(Interval(-1,1),Interval(0,0))
    r = integrate(x,u,P,.5); require_valid(r)
    for pos in [-.1,.1]:
        for v in [4,5]:
            for a in [-.2,.3]:
                for j in [-1,1]:
                    for s in r.segments:
                        t=s.end_time
                        vals=[Q(pos)+Q(v)*t+Q(a)*t*t/2+Q(j)*t**3/6,0,0,
                              Q(v)+Q(a)*t+Q(j)*t*t/2,Q(a)+Q(j)*t,0]
                        for b,q in zip(s.witness.endpoint.as_tuple(),vals): assert Q(b.lo)<=q<=Q(b.hi)

def test_time_varying_disturbance_exact_piecewise_solution():
    w = (Interval(0,0),)*4 + (Interval(-.5,.5),Interval(0,0))
    r = integrate(X,U,P,1.,derivative_disturbance=w); require_valid(r)
    # Alternating bounded derivative disturbance on acceleration: exact chain.
    pos,vel,acc = Q(0),Q(8),Q(0)
    for i,s in enumerate(r.segments):
        dt=Q(s.witness.duration_s); j=Q(1,2) if i%2 else Q(-1,2)
        for k in range(17):
            t=dt*k/16
            vals=[pos+vel*t+acc*t*t/2+j*t**3/6,0,0,vel+acc*t+j*t*t/2,acc+j*t,0]
            for b,q in zip(s.witness.tube.as_tuple(),vals): assert Q(b.lo)<=q<=Q(b.hi)
        pos,vel,acc=vals[0],vals[3],vals[4]
        for b,q in zip(s.witness.endpoint.as_tuple(),vals): assert Q(b.lo)<=q<=Q(b.hi)

def test_unknown_iteration_limit_no_endpoint_or_witness():
    opts = PicardOptions(max_iterations=1,max_depth=0,max_step_s=1)
    step = picard_step(X,U,P,.1,opts)
    assert step.status==TubeStatus.UNKNOWN and step.witness is None
    result = integrate(X,U,P,.1,opts)
    assert result.status==TubeStatus.UNKNOWN and result.endpoint is None and not result.segments
    assert not replay_certificate(to_dict(result)).ok

def test_unknown_budget_retains_only_prefix():
    r = integrate(X,U,P,1.,PicardOptions(max_steps=2))
    assert r.status==TubeStatus.UNKNOWN and r.reason=="STEP_BUDGET"
    assert len(r.segments)==2 and r.endpoint is None and 0<r.validated_until<Q(1)
    assert r.prefix_endpoint==r.segments[-1].witness.endpoint
    assert not replay_certificate(to_dict(r)).ok

@pytest.mark.parametrize("options,reason", [
    (PicardOptions(max_attempts=1),"ATTEMPT_BUDGET"),
    (PicardOptions(time_limit_s=1e-15),"TIME_BUDGET"),
    (PicardOptions(max_depth=0),"DEPTH_LIMIT:MAX_STEP"),
    (PicardOptions(min_step_s=1.),"MIN_STEP:MAX_STEP")])
def test_budget_failure_is_not_success(options,reason):
    r=integrate(X,U,P,1.,options)
    assert r.status==TubeStatus.UNKNOWN and r.endpoint is None and r.reason==reason

def test_domain_crossing_is_unknown_not_counterexample():
    x=StateBounds.point([0,0,0,1,0,1.5]);u=ControlBounds.point(0,1)
    r=integrate(x,u,P,.125,PicardOptions(max_depth=8))
    assert r.status==TubeStatus.UNKNOWN and r.endpoint is None
    assert "MODEL_DOMAIN" in r.reason
    assert all(check_witness(s.witness,u,P) for s in r.segments)

def test_successful_failure_bisection():
    # A long straight step with tightly limited local retries fails; halves
    # succeed. This specifically exercises failure bisection, not max_step.
    opts=PicardOptions(max_step_s=1.,max_iterations=3,max_depth=12)
    x=StateBounds.point([0,0,0,8,0,0]);u=ControlBounds.point(2,0)
    assert picard_step(x,u,P,1.,opts).status == TubeStatus.UNKNOWN
    r=integrate(x,u,P,1.,opts)
    require_valid(r)
    assert r.stats['failure_subdivisions']>0

def test_exact_time_grid_no_float_accumulation_gaps():
    r=integrate(X,U,P,.1,PicardOptions(max_step_s=.007));require_valid(r)
    t=Q(0)
    for s in r.segments:
        assert s.start_time==t
        t=s.end_time
    assert t==Q(.1)

def test_stationary_and_negative_speed_no_silent_clipping():
    x=StateBounds.point([0,0,0,0,0,0]);r=integrate(x,U,P,.1);require_valid(r)
    assert r.endpoint.contains([0,0,0,0,0,0])
    x=StateBounds.point([0,0,0,-2,0,0]);r=integrate(x,U,P,.25);require_valid(r)
    assert r.endpoint.px.contains(-.5)

def test_validation_does_not_imply_friction_or_collision_safety():
    x=StateBounds.point([0,0,0,2,20,0]);r=integrate(x,U,P,.01);require_valid(r)
    assert not prove_friction_feasible(x,P)
    assert to_dict(r)['full_support_safety_verified'] is False

@pytest.mark.parametrize("h", [0,-1,math.inf,math.nan])
def test_bad_horizons_rejected(h):
    with pytest.raises(ValueError): integrate(X,U,P,h)

@pytest.mark.parametrize("kwargs", [dict(max_iterations=0),dict(max_depth=-1),dict(max_steps=0),
                                    dict(absolute_inflation=(0,)*6),dict(relative_inflation=-1),
                                    dict(max_step_s=math.nan),dict(max_depth=1.5)])
def test_bad_options_rejected(kwargs):
    with pytest.raises(ValueError): PicardOptions(**kwargs)

def test_certificate_round_trip_and_tampering(tmp_path):
    r=integrate(X,U,P,.1);require_valid(r)
    path=tmp_path/'certificate.json';r.save(path)
    assert replay_certificate(path).ok
    d=to_dict(r);d['segments'][0]['tube'][0]=[0,0]
    assert not replay_certificate(d).ok
    d=to_dict(r);d['segments'][0]['end_time_exact']=['1','1']
    assert not replay_certificate(d).ok
    d=to_dict(r);d['segments'][0]['field'][0]=[0,0]
    assert not replay_certificate(d).ok
    d=to_dict(r);d['full_support_safety_verified']=True
    assert not replay_certificate(d).ok


def test_too_few_local_iterations_fail_closed_for_jerk_chain():
    opts=PicardOptions(max_step_s=1.,max_iterations=2,max_depth=4)
    r=integrate(X,ControlBounds.point(2,0),P,1.,opts)
    assert r.status==TubeStatus.UNKNOWN and r.endpoint is None
    assert r.reason=="DEPTH_LIMIT:ITERATION_LIMIT"
