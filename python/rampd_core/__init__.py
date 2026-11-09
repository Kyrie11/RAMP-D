"""RAMP-D verified-numerics development core, Phase 1B (not a vehicle controller)."""
from .interval import (Interval, IntervalError, backend_name, build_info, add, sub,
                       mul, div, square, sin, cos, tan, pi_interval, bicycle_rhs, friction_lhs)
from .model import (BicycleParameters, StateBounds, ControlBounds, rhs,
                    friction_value_enclosure, prove_friction_feasible)
from .reachability import (TubeStatus, PicardOptions, StepWitness, StepResult,
                           TubeSegment, TubeResult, picard_step, integrate, check_witness)
from .certificate import replay_certificate, save_certificate
__version__ = "0.2.0"
__all__ = ["Interval", "IntervalError", "backend_name", "build_info", "add", "sub", "mul",
           "div", "square", "sin", "cos", "tan", "pi_interval", "bicycle_rhs", "friction_lhs",
           "BicycleParameters", "StateBounds", "ControlBounds", "rhs", "friction_value_enclosure",
           "prove_friction_feasible", "TubeStatus", "PicardOptions", "StepWitness", "StepResult",
           "TubeSegment", "TubeResult", "picard_step", "integrate", "check_witness",
           "replay_certificate", "save_certificate"]
