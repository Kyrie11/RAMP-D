"""Validated analytic enclosures for integrator chains in the bicycle ODE.

These are independent outer bounds, intersected with an already sound Picard
endpoint/tube. No native integrator or Picard witness is changed. Every call
starts at the supplied ``initial`` and uses a duration measured from that
initial state; the functions do not infer global times or segment offsets.

The endpoint function encloses time h. The tube function encloses every time
in [0, h]. A caller may intersect that full tube with a Picard enclosure for
a contained subinterval, provided it keeps the same initial state, bounded
input signals, disturbances and model. The tighter interval remains a
conditional enclosure, not a complete protocol/safety certificate.

Inputs are finite binary64 constants/intervals, not exact decimal literals.
Formula arithmetic uses the existing MPFR interval API. Velocity-tube extrema
are additionally evaluated as exact rational quadratic bounds and converted
outward to binary64; no epsilon or velocity clipping is used.
"""
from __future__ import annotations

import math
from fractions import Fraction
from typing import Iterable

from .interval import Interval, square
from .model import BicycleParameters, ControlBounds, StateBounds, STATE_ORDER


def _inputs(initial: StateBounds, control: ControlBounds,
            params: BicycleParameters, disturbance: Iterable[Interval] | None,
            duration_s: float, base: StateBounds):
    if not isinstance(initial, StateBounds) or not isinstance(base, StateBounds):
        raise TypeError("initial and base enclosure must be StateBounds")
    if not isinstance(control, ControlBounds):
        raise TypeError("control must be ControlBounds")
    if not isinstance(params, BicycleParameters):
        raise TypeError("params must be BicycleParameters")
    # The chain formulas do not depend on wheelbase. Its positive, finite
    # validation still belongs to the same model contract as the Picard tube.
    if isinstance(duration_s, bool):
        raise ValueError("duration_s must be finite and positive")
    h = float(duration_s)
    if not math.isfinite(h) or h <= 0.0:
        raise ValueError("duration_s must be finite and positive")
    if isinstance(duration_s, (Fraction, int)) and Fraction.from_float(h) != duration_s:
        raise ValueError("duration_s must be exactly representable in binary64; "
                         "do not round an exact cumulative segment time")
    w = ((Interval.point(0.0),) * 6 if disturbance is None
         else tuple(disturbance))
    if len(w) != 6 or not all(isinstance(value, Interval) for value in w):
        raise ValueError("disturbance must contain six Interval objects")
    return w, h


def _is_zero(value: Interval) -> bool:
    # No tolerance: even the smallest nonzero steering or yaw-rate input
    # invalidates the straight-line identity.
    return value.lo == 0.0 and value.hi == 0.0


def _intersect(base: StateBounds, bounds: tuple[Interval, ...]) -> StateBounds:
    tightened = []
    for name, original, analytic in zip(STATE_ORDER, base.as_tuple(), bounds):
        lo, hi = max(original.lo, analytic.lo), min(original.hi, analytic.hi)
        if lo > hi:
            raise ValueError(
                f"empty {name} intersection between base and analytic enclosure; "
                "check initial state, duration, controls and disturbance provenance")
        tightened.append(Interval(lo, hi))
    return StateBounds(*tightened)


def _rational_outward(value: Fraction, *, upper: bool) -> float:
    """Round an exact rational outward by comparing the actual float value."""
    result = float(value)
    if not math.isfinite(result):
        raise ValueError("nonfinite analytic quadratic bound")
    represented = Fraction.from_float(result)
    if upper and represented < value:
        result = math.nextafter(result, math.inf)
    elif not upper and represented > value:
        result = math.nextafter(result, -math.inf)
    if not math.isfinite(result):
        raise ValueError("analytic quadratic bound cannot fit a finite interval")
    return result


def _velocity_tube(v0: Interval, linear: Interval, rate: Interval,
                   duration_s: float) -> Interval:
    """Sharp range of lower/upper quadratic envelopes on [0,h].

    For every t>=0, the nonnegative integration kernels imply
      v0.lo + linear.lo*t + rate.lo*t^2/2 <= v(t)
      v(t) <= v0.hi + linear.hi*t + rate.hi*t^2/2.
    This remains true for arbitrary measurable control/disturbance signals.
    Their two quadratics have extrema at endpoints and possibly t=-A/J.
    Exact rational arithmetic avoids any rounding of the vertex or its value.
    """
    horizon = Fraction.from_float(duration_s)

    def extrema(start, slope, accel_rate, *, minimum):
        v, a, j = map(Fraction.from_float, (start, slope, accel_rate))
        values = [v, v + a*horizon + j*horizon*horizon/2]
        # A convex quadratic can have an interior minimum; a concave one
        # can have an interior maximum. Linear/constant cases use endpoints.
        if (minimum and j > 0) or (not minimum and j < 0):
            vertex = -a / j
            if 0 <= vertex <= horizon:
                values.append(v + a*vertex + j*vertex*vertex/2)
        return min(values) if minimum else max(values)

    lower = extrema(v0.lo, linear.lo, rate.lo, minimum=True)
    upper = extrema(v0.hi, linear.hi, rate.hi, minimum=False)
    return Interval(_rational_outward(lower, upper=False),
                    _rational_outward(upper, upper=True))


def _analytic(initial: StateBounds, control: ControlBounds,
              w: tuple[Interval, ...], elapsed: Interval,
              base: StateBounds, *, whole_interval: bool = False) -> StateBounds:
    # t, t^2/2 and t^3/6 are nonnegative on the represented interval.
    # Bounded measurable signals can therefore be integrated against the
    # respective nonnegative kernels without assuming constant disturbances.
    acceleration_rate = control.jerk + w[4]
    steering_rate = control.steering_rate + w[5]
    t2_over_2 = square(elapsed) / 2.0

    bounds = list(base.as_tuple())
    bounds[4] = initial.a + elapsed * acceleration_rate
    linear = initial.a + w[3]
    if whole_interval:
        bounds[3] = _velocity_tube(initial.v, linear, acceleration_rate, elapsed.hi)
    else:
        bounds[3] = initial.v + elapsed * linear + t2_over_2 * acceleration_rate
    bounds[5] = initial.delta + elapsed * steering_rate

    straight = (all(_is_zero(x) for x in (initial.psi, initial.delta,
                                         control.steering_rate,
                                         w[1], w[2], w[5])))
    if straight:
        # delta(t)=psi(t)=0, hence px'=v+w_px and py'=0 exactly.
        # This remains valid for signed velocity, including reverse motion.
        t3_over_6 = (square(elapsed) * elapsed) / 6.0
        bounds[0] = (initial.px + elapsed * (initial.v + w[0])
                     + t2_over_2 * (initial.a + w[3])
                     + t3_over_6 * acceleration_rate)
        bounds[1] = initial.py
        bounds[2] = initial.psi
        bounds[5] = initial.delta
    return _intersect(base, tuple(bounds))


def sound_tightening(initial: StateBounds, control: ControlBounds,
                     params: BicycleParameters,
                     disturbance: Iterable[Interval] | None,
                     duration_s: float, base_endpoint: StateBounds) -> StateBounds:
    """Intersect a sound endpoint enclosure with analytic bounds at time h.

    ``initial`` is the source at time zero for this call, not implicitly a
    previous Picard segment. The base endpoint must enclose the same model at
    the same h. The input and disturbance boxes must bound their signals over
    the complete [0, h]. For curved motion, px/py/psi retain their base bounds.
    An empty intersection raises ValueError; no clipping or epsilon is used.
    """
    w, h = _inputs(initial, control, params, disturbance, duration_s, base_endpoint)
    return _analytic(initial, control, w, Interval.point(h), base_endpoint)


def analytic_tube(initial: StateBounds, control: ControlBounds,
                  params: BicycleParameters,
                  disturbance: Iterable[Interval] | None,
                  duration_s: float, base_tube: StateBounds) -> StateBounds:
    """Intersect a sound tube with analytic bounds for every t in [0, h].

    Replacing h with [0, h] encloses every intermediate state. The velocity
    chain is sharpened using exact extrema of its quadratic lower/upper
    envelopes, so a true zero-speed minimum need not acquire a spurious
    negative bound merely from repeated interval time factors. Position still
    uses natural interval evaluation. This is not endpoint interpolation.
    The base tube and analytic formulas must use the same model/input envelope.
    """
    w, h = _inputs(initial, control, params, disturbance, duration_s, base_tube)
    return _analytic(initial, control, w, Interval(0.0, h), base_tube,
                     whole_interval=True)
