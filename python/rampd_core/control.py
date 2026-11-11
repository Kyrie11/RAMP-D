"""Public sampled-data recovery laws (no hidden-mode input).

One law is evaluated from the measured ego state once per decision interval.
Its command is held until the next decision.  Interval images include the
declared measurement error; the tube backend encloses every signal in that
image, a conservative superset of these zero-order-held commands.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import hashlib
import json
import math

from .interval import Interval
from .model import StateBounds, ControlBounds


class RecoveryKind(str, Enum):
    BRAKE_TO_STOP = "brake_to_stop"
    HOLD_BEFORE_GATE = "hold_before_gate"
    YIELD = "yield"
    CLEAR_MERGE = "clear_merge"


ZERO_ERROR = (Interval(0.0, 0.0),) * 6
ZERO_GAIN = ((0.0,) * 6,) * 2


def _finite(values, count, name):
    result = tuple(float(x) for x in values)
    if len(result) != count or not all(math.isfinite(x) for x in result):
        raise ValueError(f"{name} needs {count} finite values")
    return result


def _saturate(value: Interval, limits: Interval) -> Interval:
    # Saturation is monotone; clipping BOTH endpoints is its exact set image.
    return Interval(min(limits.hi, max(limits.lo, value.lo)),
                    min(limits.hi, max(limits.lo, value.hi)))


@dataclass(frozen=True)
class SampledFeedbackLaw:
    name: str
    kind: RecoveryKind
    bias: tuple[float, float]
    gain: tuple[tuple[float, ...], tuple[float, ...]]
    reference: tuple[float, ...]
    limits: ControlBounds

    def __post_init__(self):
        if not isinstance(self.name, str) or not self.name:
            raise ValueError("law name must be nonempty")
        object.__setattr__(self, "kind", RecoveryKind(self.kind))
        object.__setattr__(self, "bias", _finite(self.bias, 2, "bias"))
        gain = tuple(_finite(row, 6, "gain row") for row in self.gain)
        if len(gain) != 2:
            raise ValueError("gain must have shape (2,6)")
        object.__setattr__(self, "gain", gain)
        object.__setattr__(self, "reference", _finite(self.reference, 6, "reference"))
        if not isinstance(self.limits, ControlBounds):
            raise TypeError("limits must be ControlBounds")

    def image(self, state: StateBounds, measurement_error=ZERO_ERROR) -> ControlBounds:
        error = tuple(measurement_error)
        if len(error) != 6 or not all(isinstance(e, Interval) for e in error):
            raise ValueError("measurement error must have six intervals")
        measured = tuple(x + e for x, e in zip(state.as_tuple(), error))
        result = []
        for bias, row, limit in zip(self.bias, self.gain, self.limits.as_tuple()):
            value = Interval.point(bias)
            for k, x, ref in zip(row, measured, self.reference):
                value = value + Interval.point(k) * (x - Interval.point(ref))
            result.append(_saturate(value, limit))
        return ControlBounds(*result)

    def command(self, measured_state) -> tuple[float, float]:
        """Return a binary64 command inside the directed point-evaluation image.

        No protocol mode, atom identifier, or future observation is accepted.
        Using the midpoint of the MPFR evaluation interval also bounds the
        execution rounding, rather than silently using an unchecked float dot.
        """
        values = _finite(measured_state, 6, "measured state")
        image = self.image(StateBounds.point(values))
        return tuple(min(v.hi, max(v.lo, v.lo / 2.0 + v.hi / 2.0))
                     for v in image.as_tuple())

    def to_dict(self):
        return {"name": self.name, "kind": self.kind.value,
                "bias": list(self.bias), "gain": [list(r) for r in self.gain],
                "reference": list(self.reference),
                "limits": [[x.lo, x.hi] for x in self.limits.as_tuple()]}

    @classmethod
    def from_dict(cls, d):
        return cls(d["name"], RecoveryKind(d["kind"]), tuple(d["bias"]),
                   tuple(tuple(r) for r in d["gain"]), tuple(d["reference"]),
                   ControlBounds(*(Interval(*x) for x in d["limits"])))

    @property
    def digest(self):
        payload = json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":"),
                             allow_nan=False).encode()
        return "law-sha256:" + hashlib.sha256(payload).hexdigest()


def recovery_candidates(kind, reference, limits, *, jerk_biases=(0.0,),
                        steering_biases=(0.0,), gain_scales=(0.5, 1.0)):
    """Finite affine-template search library; no continuous/global optimum claim.

    The gains are candidate initializations only.  Longitudinal velocity and
    acceleration feedback is used for brake/yield/clear; hold adds position
    feedback.  Clear/merge adds lateral-position and heading feedback.  Every
    resulting law, including saturation, requires independent validation.
    """
    kind = RecoveryKind(kind)
    reference = _finite(reference, 6, "reference")
    biases_j = tuple(float(x) for x in jerk_biases)
    biases_w = tuple(float(x) for x in steering_biases)
    if not biases_j or not biases_w:
        raise ValueError("candidate bias grids must be nonempty")
    scales = tuple(float(x) for x in gain_scales)
    if any(not math.isfinite(s) or s <= 0 for s in scales):
        raise ValueError("gain scales must be finite and positive")
    gains = [ZERO_GAIN]
    for s in scales:
        if kind is RecoveryKind.HOLD_BEFORE_GATE:
            longitudinal = (-s**3, 0.0, 0.0, -3.0*s*s, -3.0*s, 0.0)
        else:
            longitudinal = (0.0, 0.0, 0.0, -s*s, -2.0*s, 0.0)
        lateral = ((0.0, -0.15*s, -0.6*s, 0.0, 0.0, -1.5*s)
                   if kind is RecoveryKind.CLEAR_MERGE
                   else (0.0, 0.0, -0.4*s, 0.0, 0.0, -1.5*s))
        gains.append((longitudinal, lateral))
    result = []
    for j in biases_j:
        for w in biases_w:
            for gain in gains:
                result.append(SampledFeedbackLaw(
                    f"{kind.value}:{len(result):03d}", kind, (j, w), gain,
                    reference, limits))
    return tuple(result)
