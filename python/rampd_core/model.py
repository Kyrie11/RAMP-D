"""Paper-faithful kinematic bicycle model and physical admissibility checks."""
from dataclasses import dataclass
from .interval import Interval, bicycle_rhs, friction_lhs

STATE_ORDER = ("px", "py", "psi", "v", "a", "delta")
CONTROL_ORDER = ("jerk", "steering_rate")

@dataclass(frozen=True)
class BicycleParameters:
    wheelbase_m: float
    friction_coefficient: float
    gravity_mps2: float = 9.80665
    def __post_init__(self):
        if self.wheelbase_m <= 0 or self.friction_coefficient <= 0 or self.gravity_mps2 <= 0:
            raise ValueError("wheelbase, friction coefficient and gravity must be positive")

@dataclass(frozen=True)
class StateBounds:
    px: Interval; py: Interval; psi: Interval
    v: Interval; a: Interval; delta: Interval
    def as_tuple(self): return (self.px,self.py,self.psi,self.v,self.a,self.delta)

@dataclass(frozen=True)
class ControlBounds:
    jerk: Interval; steering_rate: Interval
    def as_tuple(self): return (self.jerk,self.steering_rate)

def rhs(state: StateBounds, control: ControlBounds, params: BicycleParameters,
        derivative_disturbance=None):
    return bicycle_rhs(state.as_tuple(), control.as_tuple(), params.wheelbase_m, derivative_disturbance)

def friction_value_enclosure(state: StateBounds, params: BicycleParameters) -> Interval:
    return friction_lhs(state.as_tuple(), params.wheelbase_m,
                        params.friction_coefficient, params.gravity_mps2)

def prove_friction_feasible(state: StateBounds, params: BicycleParameters) -> bool:
    """True only if the interval upper bound proves the entire box feasible."""
    return friction_value_enclosure(state, params).hi <= 1.0
