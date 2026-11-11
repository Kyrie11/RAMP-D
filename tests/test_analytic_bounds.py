"""Independent rational oracles for the analytic/Picard intersections."""
from dataclasses import replace
from fractions import Fraction as Q
import itertools
import math

import pytest

from rampd_core.analytic_bounds import analytic_tube, sound_tightening
from rampd_core.interval import Interval
from rampd_core.model import BicycleParameters, ControlBounds, StateBounds
from rampd_core.reachability import PicardOptions, TubeStatus, integrate


PARAMS = BicycleParameters(2.5789128, 0.9)
ZERO_W = (Interval.point(0.0),) * 6
WIDE = StateBounds(*(Interval(-10000.0, 10000.0) for _ in range(6)))


def contains_exact(box, values):
    return all(Q(bound.lo) <= exact <= Q(bound.hi)
               for bound, exact in zip(box.as_tuple(), values))


def chain_step(x, dt, jerk, wpx=Q(0), wv=Q(0), wa=Q(0),
               steering_rate=Q(0), wdelta=Q(0)):
    """Exact rational solution on one constant-signal straight interval."""
    px, py, psi, v, a, delta = x
    return (
        px + (v + wpx) * dt + (a + wv) * dt**2 / 2
        + (jerk + wa) * dt**3 / 6,
        py, psi,
        v + (a + wv) * dt + (jerk + wa) * dt**2 / 2,
        a + (jerk + wa) * dt,
        delta + (steering_rate + wdelta) * dt,
    )


@pytest.mark.parametrize("jerk", [-2.0, 0.0, 1.5])
@pytest.mark.parametrize("h", [0.1, 0.125, 1.25])
def test_constant_jerk_endpoint_and_whole_time_match_exact_rationals(jerk, h):
    x = StateBounds.point([1, 2, 0, 5, 0.25, 0])
    u = ControlBounds.point(jerk, 0)
    endpoint = sound_tightening(x, u, PARAMS, ZERO_W, h, WIDE)
    tube = analytic_tube(x, u, PARAMS, ZERO_W, h, WIDE)
    initial_exact = tuple(map(Q, (1, 2, 0, 5, 0.25, 0)))
    assert contains_exact(endpoint, chain_step(initial_exact, Q(h), Q(jerk)))
    for k in range(65):
        assert contains_exact(tube, chain_step(initial_exact, Q(h) * k / 64, Q(jerk)))
    assert endpoint.py == tube.py == Interval.point(2)
    assert endpoint.psi == endpoint.delta == Interval.point(0)


def test_interval_initials_and_bounded_saturated_jerk_cover_all_corners():
    # Such a jerk image can come from saturation of an affine feedback law;
    # the analytic module receives the already bounded control image.
    x = StateBounds(Interval(-0.25, 0.5), Interval(-1, 1), Interval(0, 0),
                    Interval(3, 4), Interval(-0.5, 0.25), Interval(0, 0))
    u = ControlBounds(Interval(-2, 1), Interval(0, 0))
    w = (Interval(-0.125, 0.25), Interval(0, 0), Interval(0, 0),
         Interval(-0.25, 0.125), Interval(-0.5, 0.25), Interval(0, 0))
    h = 0.75
    endpoint = sound_tightening(x, u, PARAMS, w, h, WIDE)
    tube = analytic_tube(x, u, PARAMS, w, h, WIDE)
    for px, v, a, j, wp, wv, wa in itertools.product(
            (-0.25, 0.5), (3, 4), (-0.5, 0.25), (-2, 1),
            (-0.125, 0.25), (-0.25, 0.125), (-0.5, 0.25)):
        exact0 = tuple(map(Q, (px, 0, 0, v, a, 0)))
        exact = chain_step(exact0, Q(h), Q(j), Q(wp), Q(wv), Q(wa))
        assert contains_exact(endpoint, exact)
        for fraction in (Q(0), Q(1, 4), Q(1, 2), Q(3, 4), Q(1)):
            assert contains_exact(tube, chain_step(
                exact0, Q(h) * fraction, Q(j), Q(wp), Q(wv), Q(wa)))


def test_nonnegative_kernels_cover_piecewise_time_varying_inputs_and_disturbance():
    x = StateBounds.point([1, -2, 0, 4, 0.5, 0])
    u = ControlBounds(Interval(-2, 2), Interval(0, 0))
    w = (Interval(-0.25, 0.25), Interval(0, 0), Interval(0, 0),
         Interval(-0.5, 0.5), Interval(-1, 1), Interval(0, 0))
    endpoint = sound_tightening(x, u, PARAMS, w, 1.0, WIDE)
    tube = analytic_tube(x, u, PARAMS, w, 1.0, WIDE)
    exact = tuple(map(Q, (1, -2, 0, 4, 0.5, 0)))
    # Switching signals are independently integrated, rather than pretending
    # they are constant or averaging them before the nonuniform kernels.
    pieces = [
        (Q(1, 8), Q(2), Q(-1, 4), Q(1, 2), Q(-1)),
        (Q(3, 8), Q(-2), Q(1, 4), Q(-1, 2), Q(1)),
        (Q(1, 4), Q(1), Q(-1, 4), Q(1, 2), Q(1)),
        (Q(1, 4), Q(-1), Q(1, 4), Q(-1, 2), Q(-1)),
    ]
    for dt, j, wp, wv, wa in pieces:
        for k in range(17):
            assert contains_exact(tube, chain_step(exact, dt * k / 16, j, wp, wv, wa))
        exact = chain_step(exact, dt, j, wp, wv, wa)
    assert contains_exact(endpoint, exact)


@pytest.mark.parametrize("changed", ["psi", "delta", "steering_rate", "wpy", "wpsi", "wdelta"])
def test_every_straight_line_precondition_is_required_exactly(changed):
    x = StateBounds.point([1, 2, 0, 3, 0, 0])
    u = ControlBounds.point(0, 0)
    w = list(ZERO_W)
    # A small nonzero value must not be replaced by zero via a tolerance.
    small = math.ulp(1.0)
    if changed in ("psi", "delta"):
        x = replace(x, **{changed: Interval.point(small)})
    elif changed == "steering_rate":
        u = ControlBounds.point(0, small)
    else:
        w[{"wpy": 1, "wpsi": 2, "wdelta": 5}[changed]] = Interval.point(small)
    for fn in (sound_tightening, analytic_tube):
        box = fn(x, u, PARAMS, w, 0.5, WIDE)
        assert box.px == WIDE.px
        assert box.py == WIDE.py
        assert box.psi == WIDE.psi
        assert box.a != WIDE.a
        assert box.v != WIDE.v
        assert box.delta != WIDE.delta


def test_curved_model_retains_base_geometry_but_tightens_integrator_chains():
    x = StateBounds.point([1, 2, 0.2, 3, -0.5, 0.1])
    u = ControlBounds(Interval(-1, 2), Interval(-0.25, 0.5))
    w = (Interval(-1, 1),) * 6
    endpoint = sound_tightening(x, u, PARAMS, w, 0.25, WIDE)
    assert endpoint.as_tuple()[:3] == WIDE.as_tuple()[:3]
    for j, wa, wv, wd, steer in itertools.product((-1, 2), (-1, 1), (-1, 1), (-1, 1), (-0.25, 0.5)):
        t = Q(1, 4)
        values = (Q(3) + (Q(-0.5) + wv) * t + (j + wa) * t*t / 2,
                  Q(-0.5) + (j + wa) * t,
                  Q(0.1) + (Q(steer) + wd) * t)
        assert all(Q(b.lo) <= v <= Q(b.hi)
                   for b, v in zip(endpoint.as_tuple()[3:], values))


def test_zero_speed_with_negative_acceleration_is_not_clamped_or_held():
    x = StateBounds.point([0, 0, 0, 0, -1, 0])
    u = ControlBounds.point(0, 0)
    endpoint = sound_tightening(x, u, PARAMS, ZERO_W, 1.0, WIDE)
    assert endpoint.v == Interval.point(-1)
    assert endpoint.px == Interval.point(-0.5)
    assert endpoint.a == Interval.point(-1)
    tube = analytic_tube(x, u, PARAMS, ZERO_W, 1.0, WIDE)
    assert tube.v == Interval(-1, 0)
    assert tube.px == Interval(-0.5, 0)


def test_picard_stationary_enclosure_tightens_to_exact_self_loop():
    x = StateBounds.point([1, 2, 0, 0, 0, 0])
    u = ControlBounds.point(0, 0)
    result = integrate(x, u, PARAMS, 0.5)
    assert result.status is TubeStatus.VALIDATED
    assert sound_tightening(x, u, PARAMS, ZERO_W, 0.5, result.endpoint) == x
    for segment in result.segments:
        # Using the original source and elapsed segment end bounds [0,end],
        # whose enclosure can soundly be intersected with a contained segment.
        end = float(segment.end_time)
        assert analytic_tube(x, u, PARAMS, ZERO_W, end, segment.witness.tube) == x


def test_four_mps_jerk_s_profile_has_zero_terminal_speed_and_acceleration():
    x = StateBounds.point([0, 0, 0, 4, 0, 0])
    # Two seconds of -1 jerk, then two seconds of +1 jerk. Both exact
    # durations and v/a terminal coordinates are binary representable.
    for jerk in (-1.0, 1.0):
        u = ControlBounds.point(jerk, 0)
        result = integrate(x, u, PARAMS, 2.0,
                           PicardOptions(max_step_s=0.03125))
        assert result.status is TubeStatus.VALIDATED
        x = sound_tightening(x, u, PARAMS, ZERO_W, 2.0, result.endpoint)
    assert x.v == Interval.point(0)
    assert x.a == Interval.point(0)
    assert x.px.contains(8)
    assert x.psi == x.delta == Interval.point(0)
    # Interval px uncertainty remains a stationary interval under zero input.
    result = integrate(x, ControlBounds.point(0, 0), PARAMS, 0.25)
    assert result.status is TubeStatus.VALIDATED
    assert sound_tightening(x, ControlBounds.point(0, 0), PARAMS,
                            ZERO_W, 0.25, result.endpoint) == x


def test_tube_is_not_just_hull_of_initial_and_endpoint():
    # v(t)=t-t^2 has v(0)=v(1)=0 but v(1/2)=1/4.
    x = StateBounds.point([0, 0, 0, 0, 1, 0])
    u = ControlBounds.point(-2, 0)
    endpoint = sound_tightening(x, u, PARAMS, ZERO_W, 1.0, WIDE)
    tube = analytic_tube(x, u, PARAMS, ZERO_W, 1.0, WIDE)
    assert endpoint.v == Interval.point(0)
    assert tube.v.contains(0.25)


def test_intersection_only_narrows_base_and_does_not_widen_it():
    x = StateBounds.point([0, 0, 0, 2, 0, 0])
    u = ControlBounds.point(0, 0)
    base = StateBounds(Interval(0, 1), Interval(0, 0), Interval(0, 0),
                       Interval(1.9, 2.1), Interval(-0.01, 0.01), Interval(0, 0))
    for fn in (sound_tightening, analytic_tube):
        assert base.contains(fn(x, u, PARAMS, ZERO_W, 0.5, base))


def test_disjoint_base_and_analytic_enclosure_is_rejected():
    x = StateBounds.point([0, 0, 0, 2, 0, 0])
    u = ControlBounds.point(0, 0)
    incompatible = replace(WIDE, v=Interval(8, 9))
    for fn in (sound_tightening, analytic_tube):
        with pytest.raises(ValueError, match="empty v intersection"):
            fn(x, u, PARAMS, ZERO_W, 0.5, incompatible)


@pytest.mark.parametrize("h", [0.0, -0.1, math.inf, math.nan, True])
def test_invalid_durations_fail_closed(h):
    x = StateBounds.point([0, 0, 0, 0, 0, 0])
    for fn in (sound_tightening, analytic_tube):
        with pytest.raises(ValueError, match="finite and positive"):
            fn(x, ControlBounds.point(0, 0), PARAMS, ZERO_W, h, WIDE)


def test_disturbance_shape_and_types_are_checked():
    x = StateBounds.point([0, 0, 0, 0, 0, 0])
    u = ControlBounds.point(0, 0)
    for wrong in (ZERO_W[:5], ZERO_W + (Interval(0, 0),), (0.0,) * 6):
        with pytest.raises(ValueError, match="six Interval"):
            sound_tightening(x, u, PARAMS, wrong, 0.5, WIDE)
    assert sound_tightening(x, u, PARAMS, None, 0.5, WIDE) == x


def test_nonrepresentable_exact_cumulative_time_is_not_silently_rounded():
    x = StateBounds.point([0, 0, 0, 1, 0, 0])
    u = ControlBounds.point(0, 0)
    cumulative = Q(0.1) * 3 / 8
    assert Q(float(cumulative)) != cumulative
    for fn in (sound_tightening, analytic_tube):
        with pytest.raises(ValueError, match="exactly representable"):
            fn(x, u, PARAMS, ZERO_W, cumulative, WIDE)
    assert sound_tightening(x, u, PARAMS, ZERO_W, Q(1, 8), WIDE).px == Interval.point(0.125)


def test_quadratic_stop_reaches_zero_without_spurious_negative_velocity_bound():
    # v(t)=2*(t-1/4)^2, a(t)=-1+4t on [0,1/4]. The exact
    # minimum is zero, not a tolerance-clipped small negative value.
    x = StateBounds.point([0, 0, 0, 0.125, -1, 0])
    u = ControlBounds.point(4, 0)
    tube = analytic_tube(x, u, PARAMS, ZERO_W, 0.25, WIDE)
    endpoint = sound_tightening(x, u, PARAMS, ZERO_W, 0.25, WIDE)
    assert tube.v == Interval(0, 0.125)
    assert endpoint.v == endpoint.a == Interval.point(0)


def test_quadratic_interior_minimum_and_concave_maximum_are_both_enclosed_sharply():
    # Convex: (t-1)^2; concave: 1-(t-1)^2, both on [0,2].
    convex = StateBounds.point([0, 0, 0, 1, -2, 0])
    concave = StateBounds.point([0, 0, 0, 0, 2, 0])
    assert analytic_tube(convex, ControlBounds.point(2, 0), PARAMS,
                         ZERO_W, 2, WIDE).v == Interval(0, 1)
    assert analytic_tube(concave, ControlBounds.point(-2, 0), PARAMS,
                         ZERO_W, 2, WIDE).v == Interval(0, 1)


def test_quadratic_vertex_outside_horizon_is_not_used():
    x = StateBounds.point([0, 0, 0, 4, -1, 0])
    # Vertex t=1 is outside [0,.25]; the lower endpoint at .25 is 121/32.
    result = analytic_tube(x, ControlBounds.point(1, 0), PARAMS, ZERO_W, 0.25, WIDE)
    assert result.v == Interval(121/32, 4)


def test_linear_velocity_tube_uses_both_endpoints_without_vertex_division():
    x = StateBounds.point([0, 0, 0, 1, -2, 0])
    result = analytic_tube(x, ControlBounds.point(0, 0), PARAMS, ZERO_W, 0.75, WIDE)
    assert result.v == Interval(-0.5, 1)


def test_uncertain_quadratic_coefficients_use_separate_lower_and_upper_envelopes():
    x = StateBounds(Interval(0, 0), Interval(0, 0), Interval(0, 0),
                    Interval(0.25, 0.5), Interval(-1, -0.5), Interval(0, 0))
    u = ControlBounds(Interval(2, 4), Interval(0, 0))
    w = list(ZERO_W)
    w[3], w[4] = Interval(-0.25, 0.25), Interval(-0.5, 0.5)
    result = analytic_tube(x, u, PARAMS, w, 1, WIDE)
    # Lower: 1/4-5t/4+3t^2/4, with min -13/48 at t=5/6.
    # Upper: 1/2-t/4+9t^2/4, with max 5/2 at t=1.
    assert Q(result.v.lo) <= Q(-13, 48) < Q(math.nextafter(result.v.lo, math.inf))
    assert result.v.hi == 2.5
    for v, a, j, wv, wa in itertools.product((0.25, 0.5), (-1, -0.5),
                                            (2, 4), (-0.25, 0.25), (-0.5, 0.5)):
        for k in range(65):
            t = Q(k, 64)
            exact = Q(v) + (Q(a)+Q(wv))*t + (Q(j)+Q(wa))*t*t/2
            assert Q(result.v.lo) <= exact <= Q(result.v.hi)


def test_nonbinary_quadratic_vertex_value_is_rounded_outward_against_exact_rational():
    x = StateBounds.point([0, 0, 0, 0.2, -0.1, 0])
    u = ControlBounds.point(0.3, 0)
    result = analytic_tube(x, u, PARAMS, ZERO_W, 1, WIDE)
    # Completing the square gives the exact binary-input minimum; this is
    # independent of any rounded numeric root-search or sampled time grid.
    exact_min = Q(0.2) - Q(-0.1)**2 / (2*Q(0.3))
    assert Q(result.v.lo) <= exact_min < Q(math.nextafter(result.v.lo, math.inf))
    exact_max = Q(0.2) + Q(-0.1) + Q(0.3)/2
    assert Q(math.nextafter(result.v.hi, -math.inf)) < exact_max <= Q(result.v.hi)


def test_subnormal_quadratic_minimum_rounds_down_without_clamping_to_zero():
    tiny = math.nextafter(0.0, math.inf)
    x = StateBounds.point([0, 0, 0, 0, -tiny, 0])
    result = analytic_tube(x, ControlBounds.point(tiny, 0), PARAMS, ZERO_W, 1, WIDE)
    exact_min = -Q(tiny)/2
    assert result.v.lo == -tiny
    assert Q(result.v.lo) <= exact_min < Q(0)
    assert result.v.hi == 0


def test_disturbed_stopping_case_keeps_true_negative_lower_velocity():
    x = StateBounds.point([0, 0, 0, 0.125, -1, 0])
    w = list(ZERO_W)
    w[3] = Interval(-0.01, 0.01)
    result = analytic_tube(x, ControlBounds.point(4, 0), PARAMS, w, 0.25, WIDE)
    exact_negative = -Q(0.01)/4
    assert Q(result.v.lo) <= exact_negative < 0
    assert result.v.lo < 0.0  # A real disturbance violation must not disappear.
