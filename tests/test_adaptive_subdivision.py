from dataclasses import replace
from fractions import Fraction as Q
import math
import pytest
from rampd_core import *
from rampd_core.certificate import to_dict, SCHEMA

P = BicycleParameters(2.8, .9)
U0 = ControlBounds.point(0, 0)
X0 = StateBounds.point([0, 0, 0, 8, 0, 0])


def _assert_complete(r):
    assert r.status == TubeStatus.VALIDATED, (r.reason, r.stats)
    assert r.endpoint is not None
    assert r.validated_until == Q(r.requested_horizon_s)
    assert len(r.segments) == r.stats["accepted_steps"]


def test_width_metric_uses_outward_interval_subtraction():
    box = StateBounds(Interval(-1.1, 2.2), Interval(-3.0, -2.0),
                      Interval(.1, .2), Interval(4, 5),
                      Interval(-.5, .5), Interval(-.1, .1))
    widths = state_box_widths(box)
    assert len(widths) == 6
    for q, w in zip(box.as_tuple(), widths):
        assert w == Q.from_float(q.hi) - Q.from_float(q.lo)
        assert w >= 0


def test_no_width_policy_preserves_phase1b_behavior():
    a = integrate(X0, U0, P, .2, PicardOptions(max_step_s=.05))
    b = integrate(X0, U0, P, .2, PicardOptions(max_step_s=.05, max_tube_widths=None))
    _assert_complete(a); _assert_complete(b)
    assert [(s.start_time, s.end_time) for s in a.segments] == [
        (s.start_time, s.end_time) for s in b.segments]
    assert b.stats["width_subdivisions"] == 0


def test_initial_support_wider_than_cap_fails_closed_without_attempts():
    x = StateBounds(Interval(-.1, .1), *X0.as_tuple()[1:])
    caps = (.1, .1, .1, .1, .1, .1)
    r = integrate(x, U0, P, .1, PicardOptions(max_tube_widths=caps))
    assert r.status == TubeStatus.UNKNOWN
    assert r.reason == "INITIAL_WIDTH_LIMIT"
    assert not r.segments and r.endpoint is None
    assert r.stats["attempts"] == 0
    assert r.stats["max_width_ratio"] == 2.0


def test_width_split_budget_zero_returns_unknown_not_validated():
    caps = (.01, .01, .01, .01, .01, .01)
    r = integrate(X0, U0, P, .5, PicardOptions(max_step_s=.5,
        max_tube_widths=caps, max_width_subdivisions=0))
    assert r.status == TubeStatus.UNKNOWN
    assert r.reason == "WIDTH_SPLIT_BUDGET"
    assert r.endpoint is None and not r.segments
    assert r.stats["width_rejections"] == 1
    assert r.stats["width_subdivisions"] == 0


def test_width_policy_configuration_validation():
    with pytest.raises(ValueError): PicardOptions(max_tube_widths=(1.,) * 5)
    with pytest.raises(ValueError): PicardOptions(max_tube_widths=(1., 1., 1., 1., 1., 0.))
    with pytest.raises(ValueError): PicardOptions(max_tube_widths=(1., 1., 1., 1., 1., math.inf))
    with pytest.raises(ValueError): PicardOptions(max_width_subdivisions=-1)


def test_width_certificate_v2_replay_and_metadata_tamper():
    r = integrate(X0, U0, P, .1, PicardOptions(max_step_s=.05,
        max_tube_widths=(.1, .1, .1, .1, .1, .1)))
    _assert_complete(r)
    d = to_dict(r)
    assert d["schema"] == SCHEMA
    assert replay_certificate(d).ok
    d2 = to_dict(r)
    d2["segments"][0]["width_exact"][0] = [0, 1]
    assert not replay_certificate(d2).ok


def test_width_certificate_replay_enforces_configured_limit():
    # Generate a complete tube with a generous width limit, then forge the
    # option metadata to a smaller cap. Replay must independently recompute it.
    r = integrate(X0, U0, P, .05, PicardOptions(max_tube_widths=(1.,) * 6))
    _assert_complete(r)
    d = to_dict(r)
    d["options"]["max_tube_widths"] = [1e-15] * 6
    assert not replay_certificate(d).ok


def test_width_driven_split_reduces_local_enclosure_width():
    x = StateBounds(Interval(0, 0), Interval(0, 0), Interval(-.03, .03),
                    Interval(7.9, 8.1), Interval(0, 0), Interval(0, 0))
    caps = (2.2, .8, .1, .3, .1, .01)
    coarse = integrate(x, U0, P, .8, PicardOptions(max_step_s=.4))
    adaptive = integrate(x, U0, P, .8, PicardOptions(max_step_s=.4,
        max_tube_widths=caps, max_depth=16, max_steps=10000))
    _assert_complete(coarse); _assert_complete(adaptive)
    assert adaptive.stats["width_subdivisions"] > 0
    assert adaptive.stats["width_rejections"] > 0
    assert adaptive.stats["accepted_steps"] > coarse.stats["accepted_steps"]
    assert adaptive.stats["max_accepted_width_ratio"] <= 1.0
    assert adaptive.stats["max_accepted_tube_widths"][0] < coarse.stats["max_accepted_tube_widths"][0]
    for seg in adaptive.segments:
        assert all(w <= cap for w, cap in zip(state_box_widths(seg.witness.tube), caps))
    assert replay_certificate(to_dict(adaptive)).ok


def test_unknown_partial_prefix_never_gets_terminal_endpoint_under_width_budget():
    caps = (.02, .02, .02, .02, .02, .02)
    r = integrate(X0, U0, P, 1.0, PicardOptions(max_step_s=.5,
        max_tube_widths=caps, max_width_subdivisions=1, max_depth=12))
    if r.status == TubeStatus.UNKNOWN:
        assert r.endpoint is None
        assert r.validated_until < Q(1.0)
        assert not replay_certificate(to_dict(r)).ok
    else:
        _assert_complete(r)


def test_legacy_phase1b_certificate_schema_remains_readable():
    r = integrate(X0, U0, P, .05)
    _assert_complete(r)
    d = to_dict(r)
    d["schema"] = "rampd.picard-tube.v1"
    for seg in d["segments"]:
        seg.pop("width_exact", None)
    assert replay_certificate(d).ok


def test_exact_width_metric_does_not_overflow_for_finite_endpoints():
    import json
    huge = StateBounds(Interval(-1e308, 1e308), *X0.as_tuple()[1:])
    widths = state_box_widths(huge)
    assert widths[0] == Q.from_float(1e308) - Q.from_float(-1e308)
    caps = (1.0, 1.0, 1.0, 1.0, 1.0, 1.0)
    r = integrate(huge, U0, P, .1, PicardOptions(max_tube_widths=caps))
    assert r.status == TubeStatus.UNKNOWN and r.reason == "INITIAL_WIDTH_LIMIT"
    # Even a width too large for binary64's numeric report is represented
    # safely as a string there; exact rational width remains available.
    json.dumps(to_dict(r), allow_nan=False)


def test_width_limit_depth_and_min_step_fail_closed():
    caps = (.01, .01, .01, .01, .01, .01)
    depth_limited = integrate(X0, U0, P, .5, PicardOptions(
        max_step_s=.5, max_tube_widths=caps, max_depth=0))
    assert depth_limited.status == TubeStatus.UNKNOWN
    assert depth_limited.reason == "DEPTH_LIMIT:WIDTH_LIMIT"
    assert depth_limited.endpoint is None

    min_step_limited = integrate(X0, U0, P, .5, PicardOptions(
        max_step_s=.5, max_tube_widths=caps, min_step_s=.3))
    assert min_step_limited.status == TubeStatus.UNKNOWN
    assert min_step_limited.reason == "MIN_STEP:WIDTH_LIMIT"
    assert min_step_limited.endpoint is None
