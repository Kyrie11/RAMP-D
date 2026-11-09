"""The paper's six-state bicycle model; no implicit clipping or saturation."""
from __future__ import annotations
from dataclasses import dataclass
import math
from .interval import Interval, bicycle_rhs, friction_lhs
STATE_ORDER = ("px", "py", "psi", "v", "a", "delta")
CONTROL_ORDER = ("jerk", "steering_rate")

@dataclass(frozen=True)
class BicycleParameters:
    wheelbase_m: float
    friction_coefficient: float
    gravity_mps2: float = 9.80665
    def __post_init__(self):
        for name in ("wheelbase_m", "friction_coefficient", "gravity_mps2"):
            value = float(getattr(self, name))
            if not math.isfinite(value) or value <= 0:
                raise ValueError(f"{name} must be finite and positive")
            object.__setattr__(self, name, value)

@dataclass(frozen=True)
class StateBounds:
    px: Interval; py: Interval; psi: Interval
    v: Interval; a: Interval; delta: Interval
    def __post_init__(self):
        if not all(isinstance(v, Interval) for v in self.as_tuple()):
            raise TypeError("StateBounds fields must be Interval objects")
    def as_tuple(self):
        return (self.px, self.py, self.psi, self.v, self.a, self.delta)
    @classmethod
    def point(cls, values):
        values = tuple(values)
        if len(values) != 6: raise ValueError("six state values required")
        return cls(*(Interval.point(v) for v in values))
    def contains(self, values):
        xs = values.as_tuple() if isinstance(values, StateBounds) else tuple(values)
        return len(xs) == 6 and all(a.contains(b) for a, b in zip(self.as_tuple(), xs))

@dataclass(frozen=True)
class ControlBounds:
    jerk: Interval; steering_rate: Interval
    def __post_init__(self):
        if not all(isinstance(v, Interval) for v in self.as_tuple()):
            raise TypeError("ControlBounds fields must be Interval objects")
    def as_tuple(self): return (self.jerk, self.steering_rate)
    @classmethod
    def point(cls, jerk, steering_rate):
        return cls(Interval.point(jerk), Interval.point(steering_rate))

def rhs(state, control, params, derivative_disturbance=None):
    return bicycle_rhs(state.as_tuple(), control.as_tuple(), params.wheelbase_m, derivative_disturbance)

def friction_value_enclosure(state, params):
    return friction_lhs(state.as_tuple(), params.wheelbase_m,
                        params.friction_coefficient, params.gravity_mps2)

def prove_friction_feasible(state, params):
    return friction_value_enclosure(state, params).hi <= 1.0
