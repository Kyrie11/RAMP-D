"""Public backup-controller synthesis and execution for RAMP-D Phase 3.

Phase 3 deliberately synthesizes the validated, constant public-control
subclass of the paper's backup policy.  A controller node is selected from a
complete Phase 2 belief support and applies exactly one control to every
hidden atom in that support.  Observation labels may route execution to a
child node, but they may never select a control using a hidden atom id.

The module does not claim a concrete protocol/resource safety certificate.
Tube execution is an adapter around the already validated Phase 1 Picard
integrator; full protocol branches, resource monitors, and agent support are
Phase 4 responsibilities.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import json
from pathlib import Path
from typing import Callable, Iterable, Mapping, Sequence

from .belief import BeliefCell
from .invariant import ActionWitness, InvariantResult
from .model import BicycleParameters, ControlBounds, StateBounds
from .reachability import PicardOptions, TubeResult, TubeStatus, integrate


class BackupMode(str, Enum):
    BRAKE_TO_STOP = "brake_to_stop"
    HOLD_BEFORE_GATE = "hold_before_gate"
    YIELD = "yield"
    CLEAR_MERGE = "clear_merge"


class BackupControllerError(ValueError):
    """Raised when a public policy graph cannot be synthesized or executed."""


@dataclass(frozen=True)
class BackupControlLimits:
    """Actuator and decision-period contract for the public controller.

    The state bounds are retained as metadata for the execution adapter.  The
    controller itself only emits jerk and steering-rate controls; it does not
    silently clip state or dynamics variables.
    """

    jerk_min: float
    jerk_max: float
    steering_rate_min: float
    steering_rate_max: float
    decision_period_s: float
    velocity_min: float = 0.0
    velocity_max: float = 60.0
    acceleration_min: float = -12.0
    acceleration_max: float = 6.0
    steering_angle_min: float = -0.7
    steering_angle_max: float = 0.7

    def __post_init__(self) -> None:
        import math

        fields = (
            "jerk_min", "jerk_max", "steering_rate_min",
            "steering_rate_max", "decision_period_s", "velocity_min",
            "velocity_max", "acceleration_min", "acceleration_max",
            "steering_angle_min", "steering_angle_max",
        )
        for name in fields:
            value = float(getattr(self, name))
            if not math.isfinite(value):
                raise BackupControllerError(f"{name} must be finite")
            object.__setattr__(self, name, value)
        if self.jerk_min > self.jerk_max:
            raise BackupControllerError("jerk_min must not exceed jerk_max")
        if self.steering_rate_min > self.steering_rate_max:
            raise BackupControllerError(
                "steering_rate_min must not exceed steering_rate_max")
        if self.decision_period_s <= 0.0:
            raise BackupControllerError("decision_period_s must be positive")
        if self.velocity_min > self.velocity_max:
            raise BackupControllerError("invalid velocity bounds")
        if self.acceleration_min > self.acceleration_max:
            raise BackupControllerError("invalid acceleration bounds")
        if self.steering_angle_min > self.steering_angle_max:
            raise BackupControllerError("invalid steering-angle bounds")

    def contains_control(self, control: Sequence[float]) -> bool:
        if len(control) != 2:
            return False
        j, omega = float(control[0]), float(control[1])
        import math
        return (math.isfinite(j) and math.isfinite(omega) and
                self.jerk_min <= j <= self.jerk_max and
                self.steering_rate_min <= omega <= self.steering_rate_max)

    def clamp_control(self, control: Sequence[float]) -> tuple[float, float]:
        if len(control) != 2:
            raise BackupControllerError("public control must be (jerk, steering_rate)")
        j, omega = float(control[0]), float(control[1])
        import math
        if not math.isfinite(j) or not math.isfinite(omega):
            raise BackupControllerError("public control must be finite")
        return (
            min(self.jerk_max, max(self.jerk_min, j)),
            min(self.steering_rate_max, max(self.steering_rate_min, omega)),
        )


def default_backup_limits() -> BackupControlLimits:
    """Deterministic benchmark limits used by the Phase 3 synthetic fixture."""

    return BackupControlLimits(
        jerk_min=-6.0, jerk_max=4.0,
        steering_rate_min=-0.6, steering_rate_max=0.6,
        decision_period_s=0.1,
    )


@dataclass(frozen=True)
class BackupTemplate:
    """Semantic label for a public constant-control backup action.

    ``control`` is the one common action already accepted by the Phase 2
    information predecessor.  The template name gives that action its
    recovery meaning; it does not itself prove the meaning safe.
    """

    mode: BackupMode
    control: tuple[float, float]
    description: str = ""
    # Phase 3 exposes the feedback slot but accepts only K_B=0.  A nonzero
    # public gain requires interval image propagation and is intentionally a
    # Phase 4 extension.
    feedback_gain: tuple[tuple[float, ...], ...] = (
        (0.0, 0.0, 0.0, 0.0, 0.0, 0.0),
        (0.0, 0.0, 0.0, 0.0, 0.0, 0.0),
    )

    def __post_init__(self) -> None:
        if not isinstance(self.mode, BackupMode):
            object.__setattr__(self, "mode", BackupMode(self.mode))
        control = tuple(float(x) for x in self.control)
        if len(control) != 2:
            raise BackupControllerError("backup template control must have two components")
        import math
        if any(not math.isfinite(x) for x in control):
            raise BackupControllerError("backup template control must be finite")
        gain = tuple(tuple(float(x) for x in row) for row in self.feedback_gain)
        if len(gain) != 2 or any(len(row) != 6 for row in gain):
            raise BackupControllerError("feedback_gain must be a 2x6 matrix")
        if any(not math.isfinite(x) for row in gain for x in row):
            raise BackupControllerError("feedback_gain must be finite")
        if any(x != 0.0 for row in gain for x in row):
            raise BackupControllerError(
                "nonzero public feedback gain is deferred until Phase 4 interval verification")
        object.__setattr__(self, "control", control)
        object.__setattr__(self, "feedback_gain", gain)


@dataclass(frozen=True)
class BackupNode:
    """One executable public policy node."""

    node_id: str
    cell_id: str
    template: BackupTemplate
    action_id: str
    observation_children: tuple[tuple[str, str], ...]
    assurance_scope: str = "PUBLIC_CONTROLLER_SYNTHESIS_ONLY"
    certified: bool = False

    def __post_init__(self) -> None:
        if not self.node_id or not self.cell_id or not self.action_id:
            raise BackupControllerError("node, cell, and action ids must be nonempty")
        if not isinstance(self.template, BackupTemplate):
            raise BackupControllerError("backup node requires a BackupTemplate")
        children = tuple((str(obs), str(child)) for obs, child in self.observation_children)
        if any(not obs or not child for obs, child in children):
            raise BackupControllerError("observation and child ids must be nonempty")
        if len({obs for obs, _ in children}) != len(children):
            raise BackupControllerError("duplicate observation branch in backup node")
        if self.certified or self.assurance_scope != "PUBLIC_CONTROLLER_SYNTHESIS_ONLY":
            raise BackupControllerError(
                "Phase 3 cannot claim a concrete safety certificate")
        object.__setattr__(self, "observation_children", children)

    @property
    def control(self) -> tuple[float, float]:
        return self.template.control

    @property
    def child_map(self) -> dict[str, str]:
        return dict(self.observation_children)


@dataclass(frozen=True)
class ExecutionStep:
    node_id: str
    control: tuple[float, float]
    observation: str | None = None
    child_node_id: str | None = None


@dataclass(frozen=True)
class TubeExecution:
    node_id: str
    status: TubeStatus
    tube: TubeResult
    control: tuple[float, float]


@dataclass(frozen=True)
class BackupPolicyGraph:
    """Deterministic policy graph with public observation routing only."""

    nodes: tuple[BackupNode, ...]
    retained_cell_ids: tuple[str, ...]
    roots: tuple[str, ...]
    decision_period_s: float = 0.1
    schema: str = "rampd.public-backup.v1"
    assurance_scope: str = "PUBLIC_CONTROLLER_SYNTHESIS_ONLY"
    certified: bool = False

    def __post_init__(self) -> None:
        import math

        if self.schema != "rampd.public-backup.v1":
            raise BackupControllerError("unsupported public-backup schema")
        if self.certified or self.assurance_scope != "PUBLIC_CONTROLLER_SYNTHESIS_ONLY":
            raise BackupControllerError("invalid Phase 3 assurance claim")
        decision_period = float(self.decision_period_s)
        if not math.isfinite(decision_period) or decision_period <= 0.0:
            raise BackupControllerError("decision_period_s must be finite and positive")
        object.__setattr__(self, "decision_period_s", decision_period)
        nodes = tuple(self.nodes)
        if not nodes:
            raise BackupControllerError("backup policy graph must contain at least one node")
        if len({n.node_id for n in nodes}) != len(nodes):
            raise BackupControllerError("backup node ids must be unique")
        if len({n.cell_id for n in nodes}) != len(nodes):
            raise BackupControllerError("one public node is required per retained cell")
        ids = {n.node_id for n in nodes}
        if not self.roots:
            raise BackupControllerError("backup policy graph must have at least one root")
        if set(self.retained_cell_ids) != {n.cell_id for n in nodes}:
            raise BackupControllerError("retained-cell ids do not match graph nodes")
        if any(root not in ids for root in self.roots):
            raise BackupControllerError("root node is missing from graph")
        if any(child not in ids for n in nodes for _, child in n.observation_children):
            raise BackupControllerError("child node is missing from graph")
        object.__setattr__(self, "nodes", nodes)
        object.__setattr__(self, "retained_cell_ids", tuple(self.retained_cell_ids))
        object.__setattr__(self, "roots", tuple(self.roots))

    @property
    def node_map(self) -> dict[str, BackupNode]:
        return {n.node_id: n for n in self.nodes}

    def node_for_cell(self, cell_id: str) -> BackupNode:
        for node in self.nodes:
            if node.cell_id == cell_id:
                return node
        raise BackupControllerError(f"unknown belief cell: {cell_id}")

    def control(self, node_id: str) -> tuple[float, float]:
        """Return the one public control for a node.

        There is intentionally no hidden atom argument.  Adding one would
        make it possible to implement an anticipative policy by construction.
        """

        try:
            return self.node_map[node_id].control
        except KeyError as exc:
            raise BackupControllerError(f"unknown backup node: {node_id}") from exc

    def route(self, node_id: str, observation: str) -> str:
        try:
            node = self.node_map[node_id]
        except KeyError as exc:
            raise BackupControllerError(f"unknown backup node: {node_id}") from exc
        try:
            return node.child_map[observation]
        except KeyError as exc:
            raise BackupControllerError(
                f"UNKNOWN_OBSERVATION:{node_id}:{observation}") from exc

    def step(self, node_id: str, observation: str | None = None) -> ExecutionStep:
        control = self.control(node_id)
        if observation is None:
            return ExecutionStep(node_id, control)
        return ExecutionStep(node_id, control, observation, self.route(node_id, observation))

    def execute_tube(
        self,
        node_id: str,
        initial_state: StateBounds,
        params: BicycleParameters,
        horizon_s: float | None = None,
        options: PicardOptions | None = None,
    ) -> TubeExecution:
        """Run one public constant action through the Phase 1 validator."""

        if not isinstance(initial_state, StateBounds):
            raise BackupControllerError("initial_state must be StateBounds")
        node = self.node_map.get(node_id)
        if node is None:
            raise BackupControllerError(f"unknown backup node: {node_id}")
        horizon = self.decision_period_s if horizon_s is None else float(horizon_s)
        import math
        if not math.isfinite(horizon) or horizon <= 0.0:
            raise BackupControllerError("horizon_s must be finite and positive")
        control = ControlBounds.point(*node.control)
        result = integrate(initial_state, control, params, horizon,
                           options or PicardOptions(max_step_s=min(horizon, 0.05)))
        return TubeExecution(node_id, result.status, result, node.control)

@dataclass(frozen=True)
class BackupSynthesisResult:
    status: str
    graph: BackupPolicyGraph | None
    reasons: tuple[str, ...] = ()
    executable_nodes: int = 0
    common_control_violations: int = 0
    all_children_retained: bool = False
    assurance_scope: str = "PUBLIC_CONTROLLER_SYNTHESIS_ONLY"
    certified: bool = False


def _mode_from_action(action_id: str, template_library: Mapping[str, BackupTemplate] | None,
                      control: tuple[float, float]) -> BackupTemplate:
    if template_library and action_id in template_library:
        template = template_library[action_id]
        if tuple(template.control) != tuple(control):
            raise BackupControllerError(
                f"template control does not match Phase 2 witness: {action_id}")
        return template
    name = action_id.lower()
    if any(token in name for token in ("brake", "stop")):
        mode = BackupMode.BRAKE_TO_STOP
    elif any(token in name for token in ("hold", "gate")):
        mode = BackupMode.HOLD_BEFORE_GATE
    elif "yield" in name:
        mode = BackupMode.YIELD
    elif any(token in name for token in ("clear", "merge")):
        mode = BackupMode.CLEAR_MERGE
    else:
        raise BackupControllerError(
            f"no public backup template for action id {action_id!r}")
    return BackupTemplate(mode, control, description=f"inferred from action {action_id}")


def _decision_map(result: InvariantResult) -> dict[str, object]:
    return {d.cell_id: d for d in result.decisions if d.retained}


def synthesize_public_backup(
    cells: Iterable[BeliefCell],
    invariant_result: InvariantResult,
    template_library: Mapping[str, BackupTemplate] | None = None,
    control_limits: BackupControlLimits | None = None,
) -> BackupSynthesisResult:
    """Compile retained Phase 2 witnesses into an executable public graph.

    Every accepted node has exactly the Phase 2 witness control, so the
    synthesis cannot accidentally replace a common action with one chosen per
    hidden atom.  The result is executable but intentionally uncertified.
    """

    # Convenience for callers that pass the limits as the third positional
    # argument: synthesize_public_backup(cells, result, limits).
    if isinstance(template_library, BackupControlLimits) and control_limits is None:
        control_limits = template_library
        template_library = None
    if invariant_result.status != "FIXPOINT_CONVERGED":
        return BackupSynthesisResult("UNKNOWN", None,
                                     ("INVARIANT_NOT_CONVERGED",))
    if invariant_result.certified or invariant_result.assurance_scope != "FINITE_ABSTRACTION_ONLY":
        return BackupSynthesisResult("UNKNOWN", None,
                                     ("INVALID_PHASE2_ASSURANCE_SCOPE",))
    cells = tuple(cells)
    if len({c.cell_id for c in cells}) != len(cells):
        return BackupSynthesisResult("UNKNOWN", None, ("DUPLICATE_CELL_ID",))
    by_id = {c.cell_id: c for c in cells}
    retained = tuple(invariant_result.retained_cell_ids)
    if not retained:
        return BackupSynthesisResult("UNKNOWN", None, ("NO_RETAINED_CELLS",))
    decisions = _decision_map(invariant_result)
    reasons: list[str] = []
    nodes: list[BackupNode] = []
    violations = 0
    limits = control_limits
    for cell_id in retained:
        cell = by_id.get(cell_id)
        decision = decisions.get(cell_id)
        if cell is None:
            reasons.append(f"MISSING_CELL:{cell_id}")
            continue
        if decision is None or decision.selected_action_id is None or decision.control is None:
            reasons.append(f"MISSING_SELECTED_WITNESS:{cell_id}")
            continue
        actions = {getattr(a, "action_id", None): a for a in cell.actions}
        action = actions.get(decision.selected_action_id)
        if not isinstance(action, ActionWitness):
            reasons.append(f"MISSING_ACTION_WITNESS:{cell_id}:{decision.selected_action_id}")
            continue
        if tuple(action.control) != tuple(decision.control):
            reasons.append(f"ACTION_CONTROL_MISMATCH:{cell_id}")
            continue
        if {t.source_atom_id for t in action.transitions} != {a.atom_id for a in cell.atoms}:
            reasons.append(f"INCOMPLETE_SOURCE_COVERAGE:{cell_id}")
            continue
        control = tuple(float(x) for x in decision.control)
        if limits is not None and not limits.contains_control(control):
            violations += 1
            reasons.append(f"CONTROL_OUTSIDE_LIMITS:{cell_id}")
            continue
        try:
            template = _mode_from_action(decision.selected_action_id,
                                         template_library, control)
        except (BackupControllerError, ValueError) as exc:
            reasons.append(f"TEMPLATE_ERROR:{cell_id}:{exc}")
            continue
        children = tuple(decision.observation_children)
        action_observations = tuple(sorted({b.observation for t in action.transitions
                                            for b in t.branches}))
        decision_observations = tuple(sorted(obs for obs, _ in children))
        if action_observations != decision_observations:
            reasons.append(f"OBSERVATION_BRANCH_MISMATCH:{cell_id}")
            continue
        if any(child not in retained for _, child in children):
            reasons.append(f"CHILD_OUTSIDE_RETAINED:{cell_id}")
            continue
        try:
            nodes.append(BackupNode(
                node_id=f"backup:{cell_id}", cell_id=cell_id,
                template=template, action_id=decision.selected_action_id,
                observation_children=tuple((obs, f"backup:{child}")
                                           for obs, child in children)))
        except BackupControllerError as exc:
            reasons.append(f"NODE_ERROR:{cell_id}:{exc}")
    if reasons:
        return BackupSynthesisResult(
            "UNKNOWN", None, tuple(sorted(reasons)), len(nodes), violations,
            False)
    node_ids = {n.node_id for n in nodes}
    if len(nodes) != len(retained):
        return BackupSynthesisResult("UNKNOWN", None,
                                     ("INCOMPLETE_NODE_COVERAGE",), len(nodes),
                                     violations, False)
    if any(child not in node_ids for n in nodes for _, child in n.observation_children):
        return BackupSynthesisResult("UNKNOWN", None,
                                     ("CHILD_NODE_MISSING",), len(nodes),
                                     violations, False)
    graph = BackupPolicyGraph(
        tuple(sorted(nodes, key=lambda n: n.node_id)), retained,
        tuple(sorted(node_ids)),
        limits.decision_period_s if limits is not None else 0.1)
    return BackupSynthesisResult(
        "BACKUP_GRAPH_SYNTHESIZED", graph, (), len(nodes), violations, True)


def save_backup_graph(path: str | Path, graph: BackupPolicyGraph) -> None:
    payload = {
        "schema": graph.schema,
        "assurance_scope": graph.assurance_scope,
        "certified": graph.certified,
        "retained_cell_ids": list(graph.retained_cell_ids),
        "roots": list(graph.roots),
        "decision_period_s": graph.decision_period_s,
        "nodes": [{
            "node_id": n.node_id,
            "cell_id": n.cell_id,
            "action_id": n.action_id,
            "mode": n.template.mode.value,
            "control": list(n.control),
            "description": n.template.description,
            "feedback_gain": [list(row) for row in n.template.feedback_gain],
            "observation_children": [list(x) for x in n.observation_children],
            "assurance_scope": n.assurance_scope,
            "certified": n.certified,
        } for n in graph.nodes],
    }
    Path(path).write_text(json.dumps(payload, sort_keys=True, indent=2) + "\n")


def replay_backup_graph(path: str | Path,
                        control_limits: BackupControlLimits | None = None) -> tuple[bool, str]:
    """Replay structural and control-limit claims in a Phase 3 graph."""

    try:
        d = json.loads(Path(path).read_text())
        if d.get("schema") != "rampd.public-backup.v1":
            return False, "unsupported schema"
        if d.get("certified") is not False or d.get("assurance_scope") != "PUBLIC_CONTROLLER_SYNTHESIS_ONLY":
            return False, "invalid assurance claim"
        nodes = []
        for raw in d.get("nodes", []):
            mode = BackupMode(raw["mode"])
            control = tuple(float(x) for x in raw["control"])
            if len(control) != 2:
                return False, "invalid control dimension"
            if control_limits and not control_limits.contains_control(control):
                return False, "control outside limits"
            children = tuple((str(a), str(b)) for a, b in raw["observation_children"])
            nodes.append(BackupNode(raw["node_id"], raw["cell_id"],
                                    BackupTemplate(mode, control, raw.get("description", ""),
                                                   tuple(tuple(row) for row in raw.get(
                                                       "feedback_gain", ((0.0,) * 6, (0.0,) * 6)))),
                                    raw["action_id"], children,
                                    raw.get("assurance_scope", "PUBLIC_CONTROLLER_SYNTHESIS_ONLY"),
                                    raw.get("certified", False)))
        graph = BackupPolicyGraph(tuple(nodes), tuple(d["retained_cell_ids"]),
                                 tuple(d["roots"]), float(d.get("decision_period_s", 0.1)))
        ids = set(graph.node_map)
        if any(child not in ids for n in graph.nodes for _, child in n.observation_children):
            return False, "child node missing"
        if set(graph.retained_cell_ids) != {n.cell_id for n in graph.nodes}:
            return False, "retained-cell mismatch"
        return True, "public backup graph replayed; concrete safety remains uncertified"
    except Exception as exc:
        return False, f"replay failed: {type(exc).__name__}: {exc}"


__all__ = [
    "BackupMode", "BackupControllerError", "BackupControlLimits",
    "default_backup_limits", "BackupTemplate", "BackupNode",
    "ExecutionStep", "TubeExecution", "BackupPolicyGraph",
    "BackupSynthesisResult", "synthesize_public_backup",
    "save_backup_graph", "replay_backup_graph",
]
