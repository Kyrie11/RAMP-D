"""Independent arithmetic and information-interface checks for public feedback.

Exact Fraction extrema provide an oracle independent of the MPFR path.  These
tests concern controller images/execution, not protocol or road-law safety.
"""
from dataclasses import replace
from fractions import Fraction
from itertools import product
import math
import random
import sys

import pytest

from rampd_core.control import (
    RecoveryKind,
    SampledFeedbackLaw,
    ZERO_ERROR,
    ZERO_GAIN,
    recovery_candidates,
)
from rampd_core.interval import Interval
from rampd_core.model import ControlBounds, StateBounds


F = Fraction.from_float


def _law(**changes):
    values = dict(
        name="nonzero-public-feedback",
        kind=RecoveryKind.CLEAR_MERGE,
        bias=(0.125, -0.0625),
        gain=((0.25, -0.5, 0.125, -1.0, -0.75, 0.0),
              (0.0, -0.125, -0.5, 0.0, 0.0, -1.25)),
        reference=(0.5, -0.25, 0.125, 2.0, 0.0, 0.0),
        limits=ControlBounds(Interval(-8.0, 6.0), Interval(-1.0, 1.0)),
    )
    values.update(changes)
    return SampledFeedbackLaw(**values)


def _exact_extrema(law, state, errors=ZERO_ERROR):
    """Extrema of a saturated affine map over independent rational boxes."""
    outputs = []
    for bias, gain, limit in zip(law.bias, law.gain, law.limits.as_tuple()):
        lo = hi = F(bias)
        for k, x, e, r in zip(gain, state.as_tuple(), errors, law.reference):
            a = F(x.lo) + F(e.lo) - F(r)
            b = F(x.hi) + F(e.hi) - F(r)
            p, q = F(k) * a, F(k) * b
            lo += min(p, q)
            hi += max(p, q)
        clamp = lambda v: min(F(limit.hi), max(F(limit.lo), v))
        outputs.append((clamp(lo), clamp(hi)))
    return outputs


def _assert_encloses_exact(image, expected):
    for bound, (lo, hi) in zip(image.as_tuple(), expected):
        assert F(bound.lo) <= lo <= hi <= F(bound.hi)


def test_nonzero_gain_and_asymmetric_measurement_error_have_exact_enclosures():
    law = _law()
    state = StateBounds(
        Interval(0.25, 0.75), Interval(-0.5, 0.25),
        Interval(0.0, 0.25), Interval(1.75, 2.25),
        Interval(-0.25, 0.5), Interval(-0.125, 0.25),
    )
    errors = (Interval(-0.0625, 0.125), Interval(-0.125, 0.0625),
              Interval(-0.03125, 0.015625), Interval(-0.125, 0.25),
              Interval(-0.0625, 0.125), Interval(-0.015625, 0.03125))
    image = law.image(state, errors)
    _assert_encloses_exact(image, _exact_extrema(law, state, errors))
    for exact_error_bound, no_error_bound in zip(image.as_tuple(), law.image(state).as_tuple()):
        assert exact_error_bound.contains(no_error_bound)
    assert image.jerk.lo > law.limits.jerk.lo
    assert image.jerk.hi < law.limits.jerk.hi

    # Dyadic inputs make these measurement corners exactly representable.
    measured_bounds = [(x.lo + e.lo, x.hi + e.hi)
                       for x, e in zip(state.as_tuple(), errors)]
    for measured in product(*measured_bounds):
        point_image = law.image(StateBounds.point(measured))
        command = law.command(measured)
        for outer, point, actual in zip(image.as_tuple(), point_image.as_tuple(), command):
            assert outer.contains(point)
            assert point.contains(actual)


def test_random_affine_box_images_include_exact_fraction_extrema():
    # No Monte Carlo proof claim: each case's independent oracle computes the
    # analytical extrema of the entire six-dimensional affine input box.
    rng = random.Random(731)
    for _ in range(40):
        intervals = []
        errors = []
        for _ in range(6):
            x = rng.uniform(-3.0, 3.0)
            intervals.append(Interval(x, x + rng.uniform(0.0, 1.0)))
            errors.append(Interval(-rng.random() / 10, rng.random() / 10))
        law = _law(
            bias=tuple(rng.uniform(-1.0, 1.0) for _ in range(2)),
            gain=tuple(tuple(rng.uniform(-1.0, 1.0) for _ in range(6)) for _ in range(2)),
            reference=tuple(rng.uniform(-1.0, 1.0) for _ in range(6)),
        )
        state = StateBounds(*intervals)
        _assert_encloses_exact(law.image(state, errors), _exact_extrema(law, state, errors))


@pytest.mark.parametrize("x_bounds, expected", [
    ((-10.0, -2.0), ((-1.0, -1.0), (0.5, 0.5))),
    ((2.0, 10.0), ((2.0, 2.0), (-0.25, -0.25))),
    ((-1.0, 1.0), ((-1.0, 2.0), (-0.25, 0.5))),
    ((-0.5, 1.0), ((-1.0, 2.0), (-0.25, 0.5))),
])
def test_saturation_clips_both_endpoints_and_preserves_boundary_commands(x_bounds, expected):
    law = _law(
        bias=(0.0, 0.0),
        gain=((2.0, 0, 0, 0, 0, 0), (-3.0, 0, 0, 0, 0, 0)),
        reference=(0.0,) * 6,
        limits=ControlBounds(Interval(-1.0, 2.0), Interval(-0.25, 0.5)),
    )
    state = StateBounds(Interval(*x_bounds), *(Interval.point(0.0) for _ in range(5)))
    assert tuple((x.lo, x.hi) for x in law.image(state).as_tuple()) == expected
    for x in x_bounds:
        command = law.command((x, 0, 0, 0, 0, 0))
        assert command == (min(2.0, max(-1.0, 2.0*x)),
                           min(0.5, max(-0.25, -3.0*x)))


@pytest.mark.parametrize("measured", [
    (0.1, -0.2, 0.3, 1.0 / 3.0, 0.7, -0.11),
    (2.0**52, -2.0**52, 0.1, -0.1, 0.3, -0.3),
    (math.nextafter(1.0, math.inf), 1.0, -1.0, 0.1, 0.2, 0.3),
])
def test_executed_binary64_command_is_inside_directed_point_image(measured):
    law = _law(
        gain=((0.1, 0.1, 0.3, -0.7, 0.9, -0.2),
              (-0.2, -0.2, 0.1, 0.3, -0.1, 0.7)),
    )
    point = StateBounds.point(measured)
    image = law.image(point)
    _assert_encloses_exact(image, _exact_extrema(law, point))
    for actual, outer, limit in zip(law.command(measured), image.as_tuple(), law.limits.as_tuple()):
        assert isinstance(actual, float) and math.isfinite(actual)
        assert outer.contains(actual)
        assert limit.contains(actual)


@pytest.mark.parametrize("value", [math.ulp(0.0), -math.ulp(0.0), sys.float_info.max])
def test_midpoint_execution_handles_underflow_and_large_finite_limits(value):
    limits = ControlBounds.point(value, value)
    law = _law(bias=(value, value), gain=ZERO_GAIN, reference=(0.0,) * 6, limits=limits)
    # Halving a minimum subnormal rounds to zero.  The final clamp must still
    # return the singleton legal command, not a point outside the image.
    assert law.command((0.0,) * 6) == (value, value)


def test_command_has_no_hidden_mode_or_future_observation_argument_and_is_stateless():
    law = _law()
    measured = (1.0, 0.0, 0.125, 2.0, -0.25, 0.0)
    first = law.command(measured)
    before = law.digest
    for forbidden in ("protocol_mode", "atom_id", "future_observation"):
        with pytest.raises(TypeError):
            law.command(measured, **{forbidden: "hidden"})
    law.command((100.0,) * 6)
    assert law.command(measured) == first
    assert law.digest == before


def test_recovery_templates_preserve_semantics_without_artificially_distinct_brake_yield_gains():
    limits = ControlBounds(Interval(-10, 10), Interval(-1, 1))
    references = {
        RecoveryKind.BRAKE_TO_STOP: (0, 0, 0, 0, 0, 0),
        RecoveryKind.HOLD_BEFORE_GATE: (10, 0, 0, 0, 0, 0),
        RecoveryKind.YIELD: (0, 0, 0, 2, 0, 0),
        RecoveryKind.CLEAR_MERGE: (0, 3, 0, 4, 0, 0),
    }
    selected = {}
    for kind, reference in references.items():
        candidates = recovery_candidates(kind, reference, limits, gain_scales=(1.0,))
        assert len(candidates) == 2
        assert candidates[0].gain == ZERO_GAIN
        selected[kind] = candidates[1]
        assert selected[kind].kind is kind
        assert selected[kind].gain != ZERO_GAIN
        assert candidates == recovery_candidates(kind, reference, limits, gain_scales=(1.0,))
    brake = selected[RecoveryKind.BRAKE_TO_STOP]
    hold = selected[RecoveryKind.HOLD_BEFORE_GATE]
    yielding = selected[RecoveryKind.YIELD]
    clear = selected[RecoveryKind.CLEAR_MERGE]
    assert brake.gain == yielding.gain  # Same stabilizing structure, different target.
    assert hold.gain[0][0] < 0.0  # Position feedback only for hold.
    assert clear.gain[1][1] < 0.0  # Lateral goal feedback for clear/merge.
    measured = (8, 0, 0.2, 3, 0, 0)
    commands = [law.command(measured) for law in selected.values()]
    assert len(set(commands)) == 4
    assert brake.command(measured)[0] < yielding.command(measured)[0] < 0
    assert clear.command(measured)[0] > 0


def test_finite_candidate_grid_and_digest_are_reproducible_and_round_trip():
    args = (RecoveryKind.CLEAR_MERGE, (0, 1, 0, 3, 0, 0),
            ControlBounds(Interval(-5, 5), Interval(-0.5, 0.5)))
    options = dict(jerk_biases=(-0.5, 0.5), steering_biases=(-0.125, 0.125),
                   gain_scales=(0.5, 1.0))
    first = recovery_candidates(*args, **options)
    second = recovery_candidates(*args, **options)
    assert len(first) == 12
    assert [law.digest for law in first] == [law.digest for law in second]
    assert len({law.digest for law in first}) == len(first)
    for law in first:
        restored = SampledFeedbackLaw.from_dict(law.to_dict())
        assert restored == law
        assert restored.digest == law.digest
        assert restored.command((0, 0, 0, 2, 0, 0)) == law.command((0, 0, 0, 2, 0, 0))


@pytest.mark.parametrize("change", [
    {"bias": (0.25, -0.0625)},
    {"gain": ((0.5, -0.5, 0.125, -1.0, -0.75, 0.0), (0.0, -0.125, -0.5, 0.0, 0.0, -1.25))},
    {"reference": (0.75, -0.25, 0.125, 2.0, 0.0, 0.0)},
    {"limits": ControlBounds(Interval(-7.0, 6.0), Interval(-1.0, 1.0))},
    {"kind": RecoveryKind.YIELD},
])
def test_digest_binds_feedback_bias_gain_reference_limits_and_template(change):
    law = _law()
    assert replace(law, **change).digest != law.digest


@pytest.mark.parametrize("change", [
    {"name": ""},
    {"kind": "hidden_oracle"},
    {"bias": (0.0,)},
    {"bias": (float("nan"), 0.0)},
    {"bias": (float("inf"), 0.0)},
    {"gain": ((0.0,) * 6,)},
    {"gain": ((0.0,) * 5, (0.0,) * 6)},
    {"gain": ((float("nan"),) * 6, (0.0,) * 6)},
    {"reference": (0.0,) * 5},
    {"reference": (0.0, 0.0, 0.0, float("inf"), 0.0, 0.0)},
])
def test_invalid_law_parameters_are_rejected(change):
    with pytest.raises(ValueError):
        _law(**change)


def test_wrong_limit_type_is_rejected():
    with pytest.raises(TypeError):
        _law(limits=((-1, 1), (-1, 1)))


@pytest.mark.parametrize("measured", [
    (0.0,) * 5,
    (0.0,) * 7,
    (0.0, 0.0, 0.0, float("nan"), 0.0, 0.0),
    (0.0, 0.0, 0.0, float("inf"), 0.0, 0.0),
])
def test_invalid_measurement_vector_is_rejected(measured):
    with pytest.raises(ValueError):
        _law().command(measured)


@pytest.mark.parametrize("errors", [ZERO_ERROR[:-1], ZERO_ERROR + ZERO_ERROR[:1], (0.0,) * 6])
def test_invalid_measurement_error_shape_or_type_is_rejected(errors):
    with pytest.raises(ValueError):
        _law().image(StateBounds.point((0.0,) * 6), errors)


@pytest.mark.parametrize("options", [
    {"jerk_biases": ()}, {"steering_biases": ()},
    {"jerk_biases": (float("nan"),)},
    {"steering_biases": (float("inf"),)},
    {"gain_scales": (0.0,)}, {"gain_scales": (-1.0,)},
    {"gain_scales": (float("nan"),)}, {"gain_scales": (float("inf"),)},
])
def test_invalid_candidate_search_grid_is_rejected(options):
    with pytest.raises(ValueError):
        recovery_candidates(RecoveryKind.BRAKE_TO_STOP, (0.0,) * 6,
                            ControlBounds(Interval(-5, 5), Interval(-1, 1)), **options)
