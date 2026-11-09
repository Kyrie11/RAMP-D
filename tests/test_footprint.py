from fractions import Fraction
import json
import math
import random
from pathlib import Path

import mpmath as mp
import pytest

from rampd_core import Interval, StateBounds, ControlBounds, BicycleParameters, PicardOptions, integrate
from rampd_core.footprint import (
    VehicleGeometry, SweptFootprint, SeparationStatus,
    separate_swept_footprints, save_separation_certificate,
    replay_separation_certificate,
)


def point_state(px=0.0, py=0.0, psi=0.0, v=0.0):
    return StateBounds.point((px, py, psi, v, 0.0, 0.0))


def fp(state, geom=None, vehicle="v", start=Fraction(0), end=Fraction(1)):
    return SweptFootprint(state, geom or VehicleGeometry(4.0, 2.0), start, end, vehicle)


def test_sqrt_interval_api_and_domain():
    from rampd_core.interval import sqrt
    assert sqrt(Interval(4.0, 9.0)).contains(2.0)
    assert sqrt(Interval(-1.0, 4.0)).lo == 0.0
    with pytest.raises(Exception):
        sqrt(Interval(-4.0, -1.0))


def test_axis_aligned_footprint_aabb_exact_point_pose():
    f = fp(point_state(3.0, -2.0, 0.0), VehicleGeometry(4.0, 2.0))
    assert f.aabb.x.lo <= 1.0 and f.aabb.x.hi >= 5.0
    assert f.aabb.y.lo <= -3.0 and f.aabb.y.hi >= -1.0


def test_quarter_turn_swaps_aabb_half_extents():
    f = fp(point_state(0.0, 0.0, math.pi / 2), VehicleGeometry(4.0, 2.0))
    assert f.aabb.x.lo <= -1.0 and f.aabb.x.hi >= 1.0
    assert f.aabb.y.lo <= -2.0 and f.aabb.y.hi >= 2.0


def test_body_center_offset_is_applied_in_body_frame():
    g = VehicleGeometry(2.0, 2.0, center_offset_x_m=1.0, center_offset_y_m=0.5)
    f = fp(point_state(), g)
    assert f.aabb.x.lo <= 0.0 and f.aabb.x.hi >= 2.0
    assert f.aabb.y.lo <= -0.5 and f.aabb.y.hi >= 1.5


def test_rotated_offset_is_rotated_with_vehicle():
    g = VehicleGeometry(2.0, 2.0, center_offset_x_m=1.0)
    f = fp(point_state(0.0, 0.0, math.pi / 2), g)
    assert f.aabb.x.lo <= -1.0 and f.aabb.x.hi >= 1.0
    assert f.aabb.y.lo <= 0.0 and f.aabb.y.hi >= 2.0


def test_diagonal_oriented_axis_separates_when_aabbs_overlap():
    theta = math.pi / 4
    nx, ny = -math.sin(theta), math.cos(theta)
    a = fp(point_state(0.0, 0.0, theta), VehicleGeometry(4.0, 0.2), "A")
    b = fp(point_state(1.5 * nx, 1.5 * ny, theta), VehicleGeometry(4.0, 0.2), "B")
    aa, bb = a.aabb, b.aabb
    assert aa.x.lo < bb.x.hi and bb.x.lo < aa.x.hi
    assert aa.y.lo < bb.y.hi and bb.y.lo < aa.y.hi
    result = separate_swept_footprints(a, b)
    assert result.status is SeparationStatus.SEPARATED
    assert result.witness is not None
    assert result.witness.clearance_lower_m > 1.29


def test_axis_aligned_far_apart_vehicles_separate():
    a = fp(point_state(0.0, 0.0), VehicleGeometry(4.0, 2.0), "A")
    b = fp(point_state(10.0, 0.0), VehicleGeometry(4.0, 2.0), "B")
    r = separate_swept_footprints(a, b)
    assert r.status is SeparationStatus.SEPARATED
    assert r.witness.clearance_lower_m > 5.99


def test_exact_touch_is_not_strict_separation():
    a = fp(point_state(0.0, 0.0), VehicleGeometry(2.0, 2.0), "A")
    b = fp(point_state(2.0, 0.0), VehicleGeometry(2.0, 2.0), "B")
    r = separate_swept_footprints(a, b)
    assert r.status is SeparationStatus.UNKNOWN
    assert r.witness is None


def test_overlap_returns_unknown_not_collision():
    a = fp(point_state(0.0, 0.0), VehicleGeometry(4.0, 2.0), "A")
    b = fp(point_state(0.5, 0.0), VehicleGeometry(4.0, 2.0), "B")
    r = separate_swept_footprints(a, b)
    assert r.status is SeparationStatus.UNKNOWN
    assert not hasattr(r.status, "COLLISION")


def test_wide_heading_box_can_only_reduce_certification_power():
    s = StateBounds(Interval.point(0), Interval.point(0), Interval(-math.pi, math.pi),
                    Interval.point(0), Interval.point(0), Interval.point(0))
    a = fp(s, VehicleGeometry(4.0, 2.0), "A")
    b = fp(point_state(3.0, 0.0), VehicleGeometry(4.0, 2.0), "B")
    assert separate_swept_footprints(a, b).status is SeparationStatus.UNKNOWN


def test_time_interval_must_match_exactly():
    a = fp(point_state(), vehicle="A", start=Fraction(0), end=Fraction(1))
    b = fp(point_state(10, 0), vehicle="B", start=Fraction(0), end=Fraction(2))
    with pytest.raises(ValueError, match="same exact time interval"):
        separate_swept_footprints(a, b)


def test_invalid_geometry_and_axis_rejected():
    with pytest.raises(ValueError): VehicleGeometry(0.0, 2.0)
    a = fp(point_state())
    b = fp(point_state(10, 0), vehicle="B")
    with pytest.raises(ValueError): separate_swept_footprints(a, b, axes=[(0.0, 0.0)])


def test_certificate_roundtrip_and_tamper_rejection(tmp_path):
    a = fp(point_state(0, 0, math.pi / 4), VehicleGeometry(4.0, 0.2), "A")
    nx, ny = -math.sin(math.pi / 4), math.cos(math.pi / 4)
    b = fp(point_state(1.5 * nx, 1.5 * ny, math.pi / 4), VehicleGeometry(4.0, 0.2), "B")
    r = separate_swept_footprints(a, b)
    assert r.status is SeparationStatus.SEPARATED
    p = tmp_path / "separation.json"
    save_separation_certificate(a, b, r, p)
    assert replay_separation_certificate(p).ok
    d = json.loads(p.read_text())
    d["clearance_lower_m"] *= 2.0
    p.write_text(json.dumps(d))
    assert not replay_separation_certificate(p).ok


def test_certificate_rejects_claim_of_full_safety(tmp_path):
    a = fp(point_state(0, 0), vehicle="A")
    b = fp(point_state(10, 0), vehicle="B")
    r = separate_swept_footprints(a, b)
    p = tmp_path / "separation.json"
    save_separation_certificate(a, b, r, p)
    d = json.loads(p.read_text())
    d["full_support_safety_verified"] = True
    p.write_text(json.dumps(d))
    assert not replay_separation_certificate(p).ok


def test_interval_support_contains_high_precision_random_corners():
    mp.mp.dps = 90
    state = StateBounds(Interval(-1.0, 1.0), Interval(-0.5, 0.5),
                        Interval(-0.3, 0.4), Interval.point(0),
                        Interval.point(0), Interval.point(0))
    geom = VehicleGeometry(4.0, 2.0, 0.2, -0.1)
    f = fp(state, geom)
    rng = random.Random(24019)
    axes = ((1.0, 0.0), (0.0, 1.0), (0.37, -0.91), (-0.8, -0.6))
    def exact_float(x):
        n, d = float(x).as_integer_ratio()
        return mp.mpf(n) / d
    for _ in range(500):
        px = rng.uniform(-1.0, 1.0); py = rng.uniform(-0.5, 0.5)
        psi = rng.uniform(-0.3, 0.4)
        c, s = mp.cos(exact_float(psi)), mp.sin(exact_float(psi))
        cx = exact_float(px) + c * exact_float(0.2) - s * exact_float(-0.1)
        cy = exact_float(py) + s * exact_float(0.2) + c * exact_float(-0.1)
        for xi in (-2.0, 2.0):
            for eta in (-1.0, 1.0):
                x = cx + c * exact_float(xi) - s * exact_float(eta)
                y = cy + s * exact_float(xi) + c * exact_float(eta)
                for axis in axes:
                    proj = exact_float(axis[0]) * x + exact_float(axis[1]) * y
                    enclosure = f.projection(axis)
                    assert exact_float(enclosure.lo) <= proj <= exact_float(enclosure.hi)


def test_swept_footprints_from_validated_picard_segments():
    params = BicycleParameters(2.8, 0.9)
    ctrl = ControlBounds.point(0.0, 0.0)
    opts = PicardOptions(max_step_s=0.1)
    a0 = point_state(0.0, 0.0, 0.0, 5.0)
    b0 = point_state(0.0, 4.0, 0.0, 5.0)
    ra = integrate(a0, ctrl, params, 0.1, opts)
    rb = integrate(b0, ctrl, params, 0.1, opts)
    assert ra.status.value == rb.status.value == "VALIDATED"
    fa = SweptFootprint.from_segment(ra.segments[0], VehicleGeometry(4.5, 1.9), "ego")
    fb = SweptFootprint.from_segment(rb.segments[0], VehicleGeometry(4.5, 1.9), "agent")
    result = separate_swept_footprints(fa, fb)
    assert result.status is SeparationStatus.SEPARATED
    assert result.witness.clearance_lower_m > 2.0


def test_tube_box_is_whole_substep_not_just_endpoint():
    # Large psi interval widens the swept footprint even though px/py are points.
    s = StateBounds(Interval.point(0), Interval.point(0), Interval(-0.5, 0.5),
                    Interval.point(0), Interval.point(0), Interval.point(0))
    f = fp(s, VehicleGeometry(4.0, 0.2))
    assert f.aabb.x.hi - f.aabb.x.lo > 2.0


def test_metric_clearance_is_normalized_for_nonunit_axis():
    a = fp(point_state(0, 0), VehicleGeometry(2.0, 2.0), "A")
    b = fp(point_state(10, 0), VehicleGeometry(2.0, 2.0), "B")
    r = separate_swept_footprints(a, b, axes=[(2.0, 0.0)])
    assert r.status is SeparationStatus.SEPARATED
    assert 7.99 < r.witness.clearance_lower_m < 8.01


def test_different_adaptive_segment_partitions_are_compared_on_common_refinement():
    from types import SimpleNamespace
    from rampd_core.footprint import separate_tube_sequences
    def seg(start, end, state):
        return SimpleNamespace(start_time=Fraction(start), end_time=Fraction(end),
                               witness=SimpleNamespace(tube=state))
    a = [seg(0, 1, point_state(0, 0))]
    b = [seg(0, Fraction(1, 2), point_state(10, 0)),
         seg(Fraction(1, 2), 1, point_state(10, 0))]
    result = separate_tube_sequences(a, VehicleGeometry(2, 2),
                                     b, VehicleGeometry(2, 2))
    assert result.status is SeparationStatus.SEPARATED
    assert len(result.pairs) == 2
    assert all(p.result.status is SeparationStatus.SEPARATED for p in result.pairs)


def test_sequence_comparison_fails_closed_if_one_subinterval_is_unresolved():
    from types import SimpleNamespace
    from rampd_core.footprint import separate_tube_sequences
    def seg(start, end, state):
        return SimpleNamespace(start_time=Fraction(start), end_time=Fraction(end),
                               witness=SimpleNamespace(tube=state))
    a = [seg(0, 1, point_state(0, 0))]
    b = [seg(0, Fraction(1, 2), point_state(10, 0)),
         seg(Fraction(1, 2), 1, point_state(0.5, 0))]
    result = separate_tube_sequences(a, VehicleGeometry(2, 2),
                                     b, VehicleGeometry(2, 2))
    assert result.status is SeparationStatus.UNKNOWN
    assert result.pairs[-1].result.status is SeparationStatus.UNKNOWN


def test_sequence_comparison_rejects_gaps_or_different_total_horizons():
    from types import SimpleNamespace
    from rampd_core.footprint import separate_tube_sequences
    def seg(start, end, state):
        return SimpleNamespace(start_time=Fraction(start), end_time=Fraction(end),
                               witness=SimpleNamespace(tube=state))
    a = [seg(0, Fraction(1, 2), point_state(0, 0)),
         seg(Fraction(1, 2), 1, point_state(0, 0))]
    b = [seg(0, 1, point_state(10, 0))]
    assert separate_tube_sequences(a, VehicleGeometry(2, 2),
                                   b, VehicleGeometry(2, 2)).status is SeparationStatus.SEPARATED
    bad = [seg(0, Fraction(1, 3), point_state(0, 0)),
           seg(Fraction(1, 2), 1, point_state(0, 0))]
    with pytest.raises(ValueError, match="contiguous"):
        separate_tube_sequences(bad, VehicleGeometry(2, 2),
                                b, VehicleGeometry(2, 2))


def test_high_level_pair_api_rejects_incomplete_unknown_tube():
    from rampd_core.footprint import separate_tube_results
    params = BicycleParameters(2.8, 0.9)
    ctrl = ControlBounds.point(0.0, 0.0)
    # An initially over-wide support is UNKNOWN under this width policy.
    bad = StateBounds(Interval(-10, 10), Interval.point(0), Interval.point(0),
                      Interval.point(0), Interval.point(0), Interval.point(0))
    unknown = integrate(bad, ctrl, params, 0.1,
                        PicardOptions(max_tube_widths=(1,1,1,1,1,1)))
    good = integrate(point_state(10,0), ctrl, params, 0.1)
    assert unknown.status.value == "UNKNOWN"
    with pytest.raises(ValueError, match="not a complete VALIDATED"):
        separate_tube_results(unknown, VehicleGeometry(4,2),
                              good, VehicleGeometry(4,2))


def test_numerically_unrepresentable_axis_fails_closed_to_unknown():
    a = fp(point_state(0, 0), VehicleGeometry(4, 2), "A")
    b = fp(point_state(10, 0), VehicleGeometry(4, 2), "B")
    result = separate_swept_footprints(a, b, axes=[(1e308, 0.0)])
    assert result.status is SeparationStatus.UNKNOWN
    assert result.witness is None


def test_mpfr_sqrt_interval_contains_high_precision_values():
    from rampd_core.interval import sqrt
    mp.mp.dps = 100
    for lo, hi in ((2.0, 3.0), (0.1, 100.0), (1e-200, 1e200)):
        q = sqrt(Interval(lo, hi))
        assert exact_mp(q.lo) <= mp.sqrt(exact_mp(lo))
        assert exact_mp(q.hi) >= mp.sqrt(exact_mp(hi))

def exact_mp(x):
    n, d = float(x).as_integer_ratio()
    return mp.mpf(n) / d


def test_high_level_pair_api_checks_exact_full_horizon_and_endpoint_linkage():
    from dataclasses import replace
    from rampd_core.footprint import separate_tube_results
    params = BicycleParameters(2.8, 0.9)
    good = integrate(point_state(0, 0), ControlBounds.point(0, 0),
                     params, 0.1, PicardOptions(max_step_s=0.1))
    other = integrate(point_state(10, 0), ControlBounds.point(0, 0),
                      params, 0.1, PicardOptions(max_step_s=0.1))
    bad_horizon = replace(good, requested_horizon_s=0.2)
    with pytest.raises(ValueError, match="exact full horizon"):
        separate_tube_results(bad_horizon, VehicleGeometry(4, 2),
                              other, VehicleGeometry(4, 2))
    bad_endpoint = replace(good, endpoint=point_state(99, 0))
    with pytest.raises(ValueError, match="endpoint does not match"):
        separate_tube_results(bad_endpoint, VehicleGeometry(4, 2),
                              other, VehicleGeometry(4, 2))


def test_high_level_pair_api_replays_source_dynamics_witnesses():
    from dataclasses import replace
    from rampd_core.footprint import separate_tube_results
    params = BicycleParameters(2.8, 0.9)
    good = integrate(point_state(0, 0), ControlBounds.point(0, 0), params, 0.1)
    other = integrate(point_state(10, 0), ControlBounds.point(0, 0), params, 0.1)
    seg = good.segments[0]
    forged_witness = replace(seg.witness, tube=point_state(123, 0))
    forged_segment = replace(seg, witness=forged_witness)
    forged = replace(good, segments=(forged_segment,) + good.segments[1:])
    with pytest.raises(ValueError, match="dynamics witness replay failed"):
        separate_tube_results(forged, VehicleGeometry(4, 2),
                              other, VehicleGeometry(4, 2))
