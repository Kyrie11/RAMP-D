"""RAMP-D verified-numerics development core, Phase 1D (not a vehicle controller)."""
from .interval import (Interval, IntervalError, backend_name, build_info, add, sub,
                       mul, div, square, sqrt, sin, cos, tan, pi_interval, bicycle_rhs, friction_lhs)
from .model import (BicycleParameters, StateBounds, ControlBounds, rhs,
                    friction_value_enclosure, prove_friction_feasible)
from .reachability import (TubeStatus, PicardOptions, StepWitness, StepResult,
                           TubeSegment, TubeResult, picard_step, integrate, check_witness,
                           state_box_widths)
from .certificate import replay_certificate, save_certificate
from .footprint import (VehicleGeometry, Projection, AABB, SweptFootprint,
                        SeparationStatus, SeparationWitness, SeparationResult, SegmentPairResult,
                        SequenceSeparationResult, candidate_axes, separate_swept_footprints,
                        separate_tube_sequences, separate_tube_results,
                        save_separation_certificate, replay_separation_certificate)
__version__ = "0.4.0"
__all__ = ["Interval", "IntervalError", "backend_name", "build_info", "add", "sub", "mul",
           "div", "square", "sqrt", "sin", "cos", "tan", "pi_interval", "bicycle_rhs", "friction_lhs",
           "BicycleParameters", "StateBounds", "ControlBounds", "rhs", "friction_value_enclosure",
           "prove_friction_feasible", "TubeStatus", "PicardOptions", "StepWitness", "StepResult",
           "TubeSegment", "TubeResult", "picard_step", "integrate", "check_witness",
           "state_box_widths",
           "replay_certificate", "save_certificate", "VehicleGeometry", "Projection", "AABB",
           "SweptFootprint", "SeparationStatus", "SeparationWitness", "SeparationResult", "SegmentPairResult",
           "SequenceSeparationResult", "candidate_axes", "separate_swept_footprints",
           "separate_tube_sequences", "separate_tube_results", "save_separation_certificate",
           "replay_separation_certificate"]
