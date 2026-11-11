"""Phase 3 finite public-law synthesis and independently replayed local evidence.

Scope: the six-state bicycle, bounded derivative/measurement errors, frozen
discrete modes, a static road corridor/gate/obstacle scene, and an explicitly
supplied finite observation cover.  This is NOT the Phase 4 protocol verifier.
No learned probability or solver success flag is accepted as safety evidence.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict, replace
from fractions import Fraction
import hashlib
import json
import math
from pathlib import Path
import time

from .interval import Interval
from .model import StateBounds, ControlBounds, BicycleParameters, prove_friction_feasible
from .belief import SupportAtom, BeliefCell
from .control import SampledFeedbackLaw, ZERO_ERROR
from .reachability import PicardOptions, TubeStatus, integrate
from .certificate import to_dict as tube_to_dict, replay_certificate
from .footprint import (VehicleGeometry, SweptFootprint, SeparationStatus,
                        separate_swept_footprints, candidate_axes)
from .invariant import (SafeDomain, EvidenceVerdict, ObservationSuccessors,
                        AtomTransition, ActionWitness, EvidenceContext,
                        evidence_context_digest, support_subset_cell,
                        _domain, _domain_from)
from .analytic_bounds import sound_tightening, analytic_tube


ASSURANCE_SCOPE = "LOCAL_BICYCLE_STATIC_SCENE_DECLARED_OBSERVATIONS"


def _hash(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                    allow_nan=False).encode()).hexdigest()


def _box(value):
    return [[x.lo, x.hi] for x in value.as_tuple()]


def _state(value):
    if len(value) != 6:
        raise ValueError("six state intervals required")
    return StateBounds(*(Interval(*x) for x in value))


def _controls(value):
    if len(value) != 2:
        raise ValueError("two control intervals required")
    return ControlBounds(*(Interval(*x) for x in value))


@dataclass(frozen=True)
class StaticObstacle:
    obstacle_id: str
    state: StateBounds
    geometry: VehicleGeometry

    def __post_init__(self):
        if not self.obstacle_id:
            raise ValueError("obstacle id required")
        if not isinstance(self.state, StateBounds) or not isinstance(self.geometry, VehicleGeometry):
            raise TypeError("obstacle needs a state box and calibrated geometry")


@dataclass(frozen=True)
class BackupContract:
    contract_id: str
    domain: SafeDomain
    params: BicycleParameters
    control_limits: ControlBounds
    geometry: VehicleGeometry
    decision_period_s: float
    road_x: Interval
    road_y: Interval
    derivative_disturbance: tuple[Interval, ...] = ZERO_ERROR
    measurement_error: tuple[Interval, ...] = ZERO_ERROR
    gate_front_x: float | None = None
    minimum_clearance_m: float = 0.05
    clearance_scale_m: float = 1.0
    obstacles: tuple[StaticObstacle, ...] = ()
    options: PicardOptions = PicardOptions(max_step_s=0.03125)

    def __post_init__(self):
        if not isinstance(self.contract_id, str) or not self.contract_id:
            raise ValueError("contract id required")
        for name in ("decision_period_s", "clearance_scale_m"):
            value = float(getattr(self, name))
            if not math.isfinite(value) or value <= 0:
                raise ValueError(f"{name} must be finite and positive")
            object.__setattr__(self, name, value)
        value = float(self.minimum_clearance_m)
        if not math.isfinite(value) or value < 0:
            raise ValueError("minimum clearance must be finite and nonnegative")
        object.__setattr__(self, "minimum_clearance_m", value)
        if self.gate_front_x is not None:
            value = float(self.gate_front_x)
            if not math.isfinite(value):
                raise ValueError("gate coordinate must be finite")
            object.__setattr__(self, "gate_front_x", value)
        for name in ("derivative_disturbance", "measurement_error"):
            values = tuple(getattr(self, name))
            if len(values) != 6 or not all(isinstance(v, Interval) for v in values):
                raise ValueError(f"{name} needs six finite intervals")
            object.__setattr__(self, name, values)
        if self.domain.friction is not None and self.domain.friction != self.params:
            raise ValueError("safe-domain friction and propagation parameters must agree")
        if not isinstance(self.options, PicardOptions):
            raise TypeError("PicardOptions required")
        obstacles = tuple(self.obstacles)
        if any(not isinstance(o, StaticObstacle) for o in obstacles):
            raise TypeError("static obstacles required")
        if len({o.obstacle_id for o in obstacles}) != len(obstacles):
            raise ValueError("obstacle ids must be unique")
        object.__setattr__(self, "obstacles", obstacles)

    def to_dict(self):
        return {"contract_id": self.contract_id, "scope": ASSURANCE_SCOPE,
                "domain": _domain(self.domain), "params": asdict(self.params),
                "control_limits": _box(self.control_limits),
                "geometry": asdict(self.geometry), "decision_period_s": self.decision_period_s,
                "road_x": [self.road_x.lo, self.road_x.hi],
                "road_y": [self.road_y.lo, self.road_y.hi],
                "derivative_disturbance": [[v.lo, v.hi] for v in self.derivative_disturbance],
                "measurement_error": [[v.lo, v.hi] for v in self.measurement_error],
                "gate_front_x": self.gate_front_x,
                "minimum_clearance_m": self.minimum_clearance_m,
                "clearance_scale_m": self.clearance_scale_m,
                "obstacles": [{"obstacle_id": o.obstacle_id, "state": _box(o.state),
                               "geometry": asdict(o.geometry)} for o in self.obstacles],
                "options": asdict(self.options)}

    @classmethod
    def from_dict(cls, d):
        if d.get("scope") != ASSURANCE_SCOPE:
            raise ValueError("unsupported local evidence scope")
        return cls(d["contract_id"], _domain_from(d["domain"]),
                   BicycleParameters(**d["params"]), _controls(d["control_limits"]),
                   VehicleGeometry(**d["geometry"]), d["decision_period_s"],
                   Interval(*d["road_x"]), Interval(*d["road_y"]),
                   tuple(Interval(*v) for v in d["derivative_disturbance"]),
                   tuple(Interval(*v) for v in d["measurement_error"]),
                   d["gate_front_x"], d["minimum_clearance_m"], d["clearance_scale_m"],
                   tuple(StaticObstacle(o["obstacle_id"], _state(o["state"]),
                                        VehicleGeometry(**o["geometry"])) for o in d["obstacles"]),
                   PicardOptions(**d["options"]))

    @property
    def digest(self):
        return "contract-sha256:" + _hash(self.to_dict())


@dataclass(frozen=True)
class StepCheck:
    status: str
    reason: str
    endpoint: StateBounds | None = None
    control_image: ControlBounds | None = None
    reserve_lower: float | None = None
    margins_m: tuple[tuple[str, float], ...] = ()
    proof: dict | None = None
    checked_segments: int = 0


def _check_spatial_box(box, source, contract, start, end):
    atom = SupportAtom(source.atom_id, box, source.other, source.mode)
    okay, reason = contract.domain.contains_atom(atom)
    if not okay:
        return None, reason
    if not prove_friction_feasible(box, contract.params):
        return None, "FRICTION_NOT_PROVED"
    ego = SweptFootprint(box, contract.geometry, start, end, "ego")
    aabb = ego.aabb
    margins = {
        "road_x_lower": (Interval.point(aabb.x.lo) - contract.road_x.lo).lo,
        "road_x_upper": (Interval.point(contract.road_x.hi) - aabb.x.hi).lo,
        "road_y_lower": (Interval.point(aabb.y.lo) - contract.road_y.lo).lo,
        "road_y_upper": (Interval.point(contract.road_y.hi) - aabb.y.hi).lo,
    }
    if contract.gate_front_x is not None:
        margins["gate_front"] = (Interval.point(contract.gate_front_x) - aabb.x.hi).lo
    for obstacle in contract.obstacles:
        other = SweptFootprint(obstacle.state, obstacle.geometry, start, end, obstacle.obstacle_id)
        # The first separating axis proves nonintersection but may have a
        # weak distance lower bound. Use the best proved axis for clearance;
        # the maximum of valid lower bounds is still a valid lower bound.
        separations = [separate_swept_footprints(ego, other, axes=(axis,))
                       for axis in candidate_axes(ego, other)]
        clearances = [r.witness.clearance_lower_m for r in separations
                      if r.status is SeparationStatus.SEPARATED]
        if not clearances:
            return None, "STATIC_OBSTACLE_SEPARATION_UNKNOWN:" + obstacle.obstacle_id
        margins["obstacle:" + obstacle.obstacle_id] = max(clearances)
    if any(v < contract.minimum_clearance_m for v in margins.values()):
        return None, "SPATIAL_CLEARANCE_NOT_PROVED"
    return margins, "LOCAL_HARD_CONSTRAINTS_PROVED"


def inspect_step_proof(source: SupportAtom, law: SampledFeedbackLaw,
                       contract: BackupContract, proof: dict) -> StepCheck:
    """Replay inclusion inequalities and hard constraints without candidate search."""
    try:
        if source.other:
            return StepCheck("UNKNOWN", "OTHER_AGENT_DYNAMICS_REQUIRE_PHASE4")
        if not all(bound.contains(lim) for bound, lim in
                   zip(contract.control_limits.as_tuple(), law.limits.as_tuple())):
            return StepCheck("UNKNOWN", "CONTROL_LIMITS_MISMATCH")
        image = law.image(source.ego, contract.measurement_error)
        if (_state(proof["initial"]) != source.ego or _controls(proof["control"]) != image or
                BicycleParameters(**proof["params"]) != contract.params or
                tuple(Interval(*x) for x in proof["derivative_disturbance"]) != contract.derivative_disturbance or
                float.fromhex(proof["horizon_hex"]) != contract.decision_period_s or
                PicardOptions(**proof["options"]) != contract.options):
            return StepCheck("UNKNOWN", "DYNAMICS_CONTEXT_MISMATCH")
        replay = replay_certificate(proof)
        if not replay.ok:
            return StepCheck("UNKNOWN", "PICARD_REPLAY_FAILED:" + replay.reason)
        margins = {}
        for segment in proof["segments"]:
            start = Fraction(*map(int, segment["start_time_exact"]))
            end = Fraction(*map(int, segment["end_time_exact"]))
            # Enclose [0,end] from the original source, retaining exact
            # integrator identities across Picard segments. A cumulative
            # rational end need not fit binary64: round it UP, explicitly.
            # The analytic time interval [0,upper] then contains this segment;
            # it does not assert a point-time endpoint at the rounded value.
            upper = float(end)
            if Fraction.from_float(upper) < end:
                upper = math.nextafter(upper, math.inf)
            if not math.isfinite(upper) or Fraction.from_float(upper) < end:
                return StepCheck("UNKNOWN", "ANALYTIC_TIME_ENCLOSURE_FAILED")
            box = analytic_tube(source.ego, image, contract.params,
                                contract.derivative_disturbance, upper,
                                _state(segment["tube"]))
            current, reason = _check_spatial_box(box, source, contract, start, end)
            if current is None:
                return StepCheck("UNKNOWN", reason, control_image=image)
            for key, value in current.items():
                margins[key] = min(margins.get(key, value), value)
        endpoint = sound_tightening(source.ego, image, contract.params,
                                    contract.derivative_disturbance,
                                    contract.decision_period_s, _state(proof["endpoint"]))
        reserve = min(1.0, min(((Interval.point(value) - contract.minimum_clearance_m) /
                               Interval.point(contract.clearance_scale_m)).lo
                              for value in margins.values()))
        return StepCheck("VALIDATED_LOCAL", "ALL_LOCAL_TUBE_CONSTRAINTS_REPLAYED", endpoint,
                         image, reserve, tuple(sorted(margins.items())), proof, replay.checked_segments)
    except (KeyError, ValueError, TypeError, RuntimeError, OverflowError, ZeroDivisionError) as exc:
        return StepCheck("UNKNOWN", f"PROOF_UNRESOLVED:{type(exc).__name__}:{exc}")


def validate_feedback_step(source, law, contract):
    """Generate a Picard witness, then use the separate replay path to accept it."""
    if source.other:
        return StepCheck("UNKNOWN", "OTHER_AGENT_DYNAMICS_REQUIRE_PHASE4")
    try:
        control = law.image(source.ego, contract.measurement_error)
        tube = integrate(source.ego, control, contract.params, contract.decision_period_s,
                         contract.options, contract.derivative_disturbance)
        if tube.status is not TubeStatus.VALIDATED:
            return StepCheck("UNKNOWN", "DYNAMICS_" + tube.reason, control_image=control)
        return inspect_step_proof(source, law, contract, tube_to_dict(tube))
    except (ValueError, TypeError, RuntimeError, OverflowError) as exc:
        return StepCheck("UNKNOWN", f"DYNAMICS_UNRESOLVED:{type(exc).__name__}:{exc}")


class LocalEvidenceStore:
    """Content-addressed, context-bound local proofs; no reference-only approvals."""
    def __init__(self, contract: BackupContract):
        self.contract = contract
        self.records: dict[str, dict] = {}
        self.laws: dict[str, SampledFeedbackLaw] = {}

    def register(self, cell, law, checks, cover, action_id):
        if set(checks) != {a.atom_id for a in cell.atoms}:
            raise ValueError("complete source evidence required")
        transitions = []
        for atom in cell.atoms:
            check = checks[atom.atom_id]
            if check.status != "VALIDATED_LOCAL":
                raise ValueError("cannot register unresolved evidence")
            successor = SupportAtom(atom.atom_id + ":post", check.endpoint, atom.other, atom.mode)
            branches = tuple(ObservationSuccessors(label, (successor,)) for label in cover[atom.atom_id])
            transitions.append(AtomTransition(atom.atom_id, EvidenceVerdict.PROVED, "pending", branches))
        draft = ActionWitness(action_id, law.bias, tuple(transitions), law.digest)
        finalized = []
        for atom, transition in zip(cell.atoms, transitions):
            check = checks[atom.atom_id]
            context = EvidenceContext(cell, atom, draft, transition)
            record = {"context_digest": evidence_context_digest(context),
                      "contract_digest": self.contract.digest, "controller_ref": law.digest,
                      "endpoint": _box(check.endpoint), "reserve_lower": check.reserve_lower,
                      "proof": check.proof}
            ref = "backup-evidence-sha256:" + _hash(record)
            self.records[ref] = record
            finalized.append(replace(transition, evidence_ref=ref))
        self.laws[law.digest] = law
        return replace(draft, transitions=tuple(finalized))

    def verify(self, context: EvidenceContext) -> bool:
        try:
            record = self.records[context.evidence_ref]
            if context.evidence_ref != "backup-evidence-sha256:" + _hash(record):
                return False
            if record["context_digest"] != evidence_context_digest(context):
                return False
            if record["contract_digest"] != self.contract.digest:
                return False
            law = self.laws[record["controller_ref"]]
            if (law.digest != record["controller_ref"] or
                    context.action.controller_ref != law.digest or context.action.control != law.bias):
                return False
            checked = inspect_step_proof(context.source_atom, law, self.contract, record["proof"])
            if checked.status != "VALIDATED_LOCAL" or _box(checked.endpoint) != record["endpoint"]:
                return False
            if checked.reserve_lower != record["reserve_lower"]:
                return False
            expected = SupportAtom(context.source_atom.atom_id + ":post", checked.endpoint,
                                   context.source_atom.other, context.source_atom.mode)
            return all(branch.atoms == (expected,) for branch in context.transition.branches)
        except (KeyError, ValueError, TypeError, RuntimeError, OverflowError):
            return False

    def to_dict(self):
        return {"schema": "rampd.backup-evidence.v1", "assurance_scope": ASSURANCE_SCOPE,
                "full_support_certified": False, "contract": self.contract.to_dict(),
                "laws": {key: value.to_dict() for key, value in sorted(self.laws.items())},
                "records": self.records}

    @classmethod
    def from_dict(cls, d):
        if (d.get("schema") != "rampd.backup-evidence.v1" or
                d.get("assurance_scope") != ASSURANCE_SCOPE or d.get("full_support_certified") is not False):
            raise ValueError("invalid local evidence schema/claim")
        result = cls(BackupContract.from_dict(d["contract"]))
        result.laws = {key: SampledFeedbackLaw.from_dict(value) for key, value in d["laws"].items()}
        if any(key != law.digest for key, law in result.laws.items()):
            raise ValueError("law digest mismatch")
        result.records = d["records"]
        return result


@dataclass(frozen=True)
class BackupChoice:
    action: ActionWitness
    law: SampledFeedbackLaw
    observation_children: tuple[tuple[str, str], ...]
    reserve_lower: float


@dataclass(frozen=True)
class BackupSynthesis:
    status: str
    choices: tuple[BackupChoice, ...]
    attempts: tuple[dict, ...]
    elapsed_s: float
    scope: str = ASSURANCE_SCOPE
    full_support_certified: bool = False

    @property
    def selected(self):
        return self.choices[0] if self.choices else None

    @property
    def actions(self):
        return tuple(c.action for c in self.choices)


def _observation_cover(cell, cover):
    if cover is None:
        cover = {a.atom_id: ("silence",) for a in cell.atoms}
    if set(cover) != {a.atom_id for a in cell.atoms}:
        raise ValueError("observation cover must enumerate exactly every source atom")
    result = {}
    for source, labels in cover.items():
        if isinstance(labels, str):
            raise ValueError("observation labels must be a tuple, not a string")
        labels = tuple(labels)
        if not labels or any(not isinstance(v, str) or not v for v in labels):
            raise ValueError("each source needs nonempty possible observation labels")
        if len(set(labels)) != len(labels):
            raise ValueError("duplicate observation label")
        result[source] = tuple(sorted(labels))
    return result


def synthesize_backup(cell: BeliefCell, candidates, targets, store: LocalEvidenceStore,
                      observation_cover=None, *, max_candidates=256, time_limit_s=None):
    """Maximize a verified clearance lower bound over a finite common-law library.

    Nonempty posterior unions must each fit ONE target information cell.  All
    feasible choices are retained in reserve order so the Phase 2 fixed point
    can remove a preferred child and still try another public continuation.
    Budget exhaustion is reported explicitly; no infeasibility/global optimum
    claim is made.  Observation coverage remains a declared Phase 3 contract.
    """
    if isinstance(max_candidates, bool) or not isinstance(max_candidates, int) or max_candidates < 1:
        raise ValueError("max_candidates must be a positive integer")
    if time_limit_s is not None and (not math.isfinite(time_limit_s) or time_limit_s <= 0):
        raise ValueError("time_limit_s must be finite and positive")
    targets = tuple(targets)
    if not targets or len({c.cell_id for c in targets}) != len(targets):
        raise ValueError("nonempty unique target cells required")
    cover = _observation_cover(cell, observation_cover)
    begin = time.perf_counter()
    accepted, attempts = [], []
    exhausted = False
    for index, law in enumerate(candidates):
        if index >= max_candidates or (time_limit_s is not None and time.perf_counter()-begin >= time_limit_s):
            exhausted = True
            break
        if not isinstance(law, SampledFeedbackLaw):
            raise TypeError("candidate must be one common SampledFeedbackLaw")
        checks = {a.atom_id: validate_feedback_step(a, law, store.contract) for a in cell.atoms}
        failures = sorted({v.reason for v in checks.values() if v.status != "VALIDATED_LOCAL"})
        children = []
        if not failures:
            posterior = {}
            for atom in cell.atoms:
                successor = SupportAtom(atom.atom_id + ":post", checks[atom.atom_id].endpoint,
                                        atom.other, atom.mode)
                for label in cover[atom.atom_id]:
                    posterior.setdefault(label, []).append(successor)
            for label, support in sorted(posterior.items()):
                valid = [target for target in targets
                         if all(store.contract.domain.contains_atom(a)[0] for a in target.atoms)
                         and support_subset_cell(support, target)]
                if not valid:
                    failures.append("POSTERIOR_NOT_IN_SINGLE_TARGET:" + label)
                    break
                children.append((label, min(valid, key=lambda c: c.cell_id).cell_id))
        if failures:
            attempts.append({"law": law.name, "controller_ref": law.digest, "status": "UNKNOWN",
                             "reason": "|".join(failures)})
        else:
            reserve = min(v.reserve_lower for v in checks.values())
            effort = sum(abs(x) for x in law.bias)  # efficiency tie-break only
            accepted.append((reserve, effort, law, checks, tuple(children)))
            attempts.append({"law": law.name, "controller_ref": law.digest,
                             "status": "VALIDATED_LOCAL", "reserve_lower": reserve})
        # This offline search is nonpreemptive inside one validated candidate.
        # Account for a deadline exceeded even on the last/only candidate.
        if time_limit_s is not None and time.perf_counter()-begin >= time_limit_s:
            exhausted = True
            break
    accepted.sort(key=lambda x: (-x[0], x[1], x[2].digest))
    choices = []
    for rank, (reserve, _, law, checks, children) in enumerate(accepted):
        action = store.register(cell, law, checks, cover, f"backup:{rank:04d}:{law.digest}")
        choices.append(BackupChoice(action, law, children, reserve))
    if exhausted:
        status = "PARTIAL_SEARCH" if choices else "UNKNOWN_BUDGET"
    else:
        status = "SYNTHESIZED_LOCAL" if choices else "UNKNOWN_NO_VALIDATED_CANDIDATE"
    return BackupSynthesis(status, tuple(choices), tuple(attempts), time.perf_counter()-begin)
