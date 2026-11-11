"""RAMP-D verified numerics and public sampled-data backup core, Phase 3."""
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
from .vehicle import VehicleModelParameters, commonroad_bmw_320i_benchmark
from .belief import BeliefCell, SupportAtom
from .invariant import (EvidenceVerdict, ObservationSuccessors, AtomTransition,
                        ActionWitness, SafeDomain, CellDecision, InvariantResult,
                        ReplayResult, support_subset_cell, compute_information_invariant,
                        save_invariant_certificate, replay_invariant_certificate,
                        EvidenceContext, evidence_context_payload, evidence_context_digest)
from .refinement import split_support_atom
from .control import (RecoveryKind, SampledFeedbackLaw, recovery_candidates,
                      ZERO_ERROR, ZERO_GAIN)
from .analytic_bounds import sound_tightening, analytic_tube
from .backup import (BackupContract, StaticObstacle, StepCheck, LocalEvidenceStore,
                     BackupChoice, BackupSynthesis, validate_feedback_step,
                     inspect_step_proof, synthesize_backup)
from .backup_graph import (BackupNode, BackupPolicyGraph, BackupExecutor,
                           BackupExecutionError, build_backup_graph,
                           save_backup_graph, load_backup_graph)

__version__ = "0.6.0"
__all__ = [name for name in globals() if not name.startswith("_")]
