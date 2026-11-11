"""Phase 5 counterexample-guided abstraction refinement.

This module deliberately keeps the CEGAR layer separate from the Phase 4
continuous evidence backends.  A Phase 4 ``UNKNOWN`` result is not silently
reinterpreted as a concrete failure: a concrete counterexample requires an
independent replay on the same task, transition, public action and support.
When replay rejects an abstract witness, the witness is *spurious* and a
recorded refinement is required before the verifier is run again.

The implementation is finite and resumable.  Event-time refinements are
exact rational partitions (closed children share their midpoint); support
refinement uses the binary64 interval representation and preserves its
closed-cover invariant.  A split keeps a single observation/policy node
unless distinguishability is explicitly proved, and every contract revision
invalidates evidence and old queue checkpoints.  No learned probability,
sampled trajectory, or tube overlap is accepted as a concrete safety
violation.
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass, replace
from enum import Enum
from fractions import Fraction
import hashlib
import json
import math
from typing import Any, Callable, Iterable, Mapping

from .belief import BeliefCell, SupportAtom
from .full_verifier import (
    FullSupportVerifier,
    FullVerifierContract,
    VerificationResult,
    VerifyStatus,
)
from .interval import Interval
from .protocol import (
    ClockTrace,
    ProtocolAutomaton,
    ProtocolTransition,
    TimeWindow,
)
from .refinement import split_support_atom


PHASE5_SCOPE = "PHASE5_CEGAR_EXPLICIT_PROTOCOL_SUPPORT"
CEGAR_SCHEMA = "rampd.cegar.v1"


class CounterexampleKind(str, Enum):
    CONCRETE = "CONCRETE"
    SPURIOUS = "SPURIOUS"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class ReplayAssessment:
    """Result of independent concrete replay of one abstract witness."""

    kind: CounterexampleKind
    reason: str
    witness: Mapping[str, Any] | None = None

    def __post_init__(self):
        if not isinstance(self.kind, CounterexampleKind):
            object.__setattr__(self, "kind", CounterexampleKind(self.kind))
        if not isinstance(self.reason, str) or not self.reason:
            raise ValueError("replay assessment needs a reason")


def classify_counterexample(
    task: Any,
    transition: Any,
    action: Any,
    branch_check: Any,
    replay: Callable[[Any, Any, Any, Any], bool] | None,
) -> ReplayAssessment:
    """Classify one branch witness without weakening the Phase 4 result.

    ``replay`` must return the strict boolean ``True`` only when the original
    model, protocol clocks, observation history, public action and support
    admit a violating concrete trajectory.  ``False`` means the abstract
    witness is spurious.  Missing callbacks, exceptions and non-boolean
    values remain UNKNOWN.
    """
    status = getattr(branch_check, "status", None)
    if status != VerifyStatus.COUNTEREXAMPLE:
        return ReplayAssessment(CounterexampleKind.UNKNOWN, "NOT_A_COUNTEREXAMPLE")
    if replay is None:
        return ReplayAssessment(CounterexampleKind.UNKNOWN, "COUNTEREXAMPLE_REPLAY_MISSING")
    try:
        outcome = replay(task, transition, action, branch_check)
    except Exception as exc:  # replay is an independent, fail-closed boundary
        return ReplayAssessment(CounterexampleKind.UNKNOWN,
                                "COUNTEREXAMPLE_REPLAY_ERROR:" + type(exc).__name__)
    if type(outcome) is not bool:
        return ReplayAssessment(CounterexampleKind.UNKNOWN,
                                "COUNTEREXAMPLE_REPLAY_NONBOOLEAN")
    if outcome:
        witness = getattr(branch_check, "counterexample", None)
        return ReplayAssessment(CounterexampleKind.CONCRETE,
                                "CONCRETE_COUNTEREXAMPLE_REPLAYED", witness)
    return ReplayAssessment(CounterexampleKind.SPURIOUS,
                            "SPURIOUS_ABSTRACT_COUNTEREXAMPLE")


def _midpoint(window: TimeWindow) -> Fraction:
    if window.lo == window.hi:
        raise ValueError("cannot refine a point time window")
    midpoint = window.lo + (window.hi - window.lo) / 2
    if not window.lo < midpoint < window.hi:
        raise ValueError("time window has no representable rational midpoint")
    return midpoint


def split_time_window(window: TimeWindow) -> tuple[TimeWindow, TimeWindow]:
    """Split a non-point closed time window exactly at a rational midpoint.

    ``TimeWindow`` is closed in the Phase 4 contract.  Consequently the two
    children share the midpoint.  This is intentional: the boundary belongs
    to both conservative children and the verifier must deduplicate any
    duplicate public successor; no event time is dropped.
    """
    if not isinstance(window, TimeWindow):
        raise TypeError("window must be a TimeWindow")
    midpoint = _midpoint(window)
    return TimeWindow(window.lo, midpoint), TimeWindow(midpoint, window.hi)


def _replace_clock(clock: ClockTrace, name: str, value: TimeWindow) -> ClockTrace:
    if name not in {"change", "issue", "receipt", "local"}:
        raise ValueError("unknown protocol clock: " + str(name))
    return replace(clock, **{name: value})


def split_protocol_transition(
    transition: ProtocolTransition,
    clock_name: str = "change",
) -> tuple[ProtocolTransition, ProtocolTransition]:
    """Split one transition clock and preserve all message/clock bindings."""
    if not isinstance(transition, ProtocolTransition):
        raise TypeError("transition must be a ProtocolTransition")
    original = transition.clocks.window(clock_name)
    if original is None:
        raise ValueError(f"transition has no {clock_name} clock window")
    left_window, right_window = split_time_window(original)
    result = []
    for suffix, child_window in (("L", left_window), ("R", right_window)):
        clocks = _replace_clock(transition.clocks, clock_name, child_window)
        message = None if transition.message is None else replace(transition.message, clocks=clocks)
        result.append(replace(transition,
                              transition_id=f"{transition.transition_id}.{suffix}",
                              clocks=clocks, message=message))
    return result[0], result[1]


def refine_automaton_transition(
    automaton: ProtocolAutomaton,
    transition_id: str,
    clock_name: str = "change",
) -> ProtocolAutomaton:
    """Return an automaton with one transition replaced by two children."""
    matches = [t for t in automaton.transitions if t.transition_id == transition_id]
    if len(matches) != 1:
        raise KeyError(f"transition {transition_id!r} not found exactly once")
    children = split_protocol_transition(matches[0], clock_name)
    transitions = []
    for transition in automaton.transitions:
        if transition.transition_id == transition_id:
            transitions.extend(children)
        else:
            transitions.append(transition)
    return ProtocolAutomaton(automaton.states, automaton.initial_state_id,
                             tuple(transitions), automaton.version + "+refined")


class RefinementKind(str, Enum):
    EVENT_TIME = "EVENT_TIME"
    SUPPORT = "SUPPORT"
    OBSERVATION = "OBSERVATION"


def default_refinement_selector(result: VerificationResult) -> "RefinementAction | None":
    """Select only unambiguous event-time obligations by default.

    Support and observation obligations need a caller-supplied atom/predicate;
    guessing those would violate the abstraction contract.  Returning None
    for them is therefore intentional fail-closed behavior.
    """
    for item in getattr(result, "unresolved", ()):
        suffix = ":EVENT_TIME_INTERVAL_REQUIRES_REFINEMENT"
        if item.endswith(suffix):
            transition_id = item[:-len(suffix)]
            if transition_id:
                return RefinementAction(RefinementKind.EVENT_TIME,
                                        item, "change", transition_id,
                                        item, clock_name="change")
    return None


@dataclass(frozen=True)
class RefinementAction:
    """One deterministic refinement request selected from an UNKNOWN result."""

    kind: RefinementKind
    responsibility: str
    axis: str
    target_id: str
    reason: str
    atom_id: str | None = None
    clock_name: str = "change"
    role: str = "initial"
    observation_labels: tuple[str, str] = ("obs-left", "obs-right")
    distinguishability_proved: bool = False

    def __post_init__(self):
        if not isinstance(self.kind, RefinementKind):
            object.__setattr__(self, "kind", RefinementKind(self.kind))
        for name in ("responsibility", "axis", "target_id", "reason"):
            if not isinstance(getattr(self, name), str) or not getattr(self, name):
                raise ValueError(f"{name} must be nonempty")
        if self.atom_id is not None and (not isinstance(self.atom_id, str) or not self.atom_id):
            raise ValueError("atom_id must be a nonempty string when supplied")
        if self.role not in {"initial", "target", "master"}:
            raise ValueError("role must be initial, target, or master")
        if len(self.observation_labels) != 2 or len(set(self.observation_labels)) != 2:
            raise ValueError("observation refinement needs two distinct labels")
        if not all(isinstance(x, str) and x for x in self.observation_labels):
            raise ValueError("observation labels must be nonempty strings")


@dataclass(frozen=True)
class RefinementResult:
    action: RefinementAction
    status: str
    reason: str
    automaton: ProtocolAutomaton | None = None
    initial_support: tuple[SupportAtom, ...] | None = None
    targets: tuple[BeliefCell, ...] = ()
    master_cells: tuple[BeliefCell, ...] = ()
    changed_ids: tuple[str, ...] = ()


def _replace_cell(cells: Iterable[BeliefCell], replacement: Iterable[BeliefCell], cell_id: str):
    replacement = tuple(replacement)
    found = False
    result = []
    for cell in cells:
        if cell.cell_id == cell_id:
            if found:
                raise ValueError("duplicate cell id")
            found = True
            result.extend(replacement)
        else:
            result.append(cell)
    if not found:
        raise KeyError(f"cell {cell_id!r} not found")
    if len({c.cell_id for c in result}) != len(result):
        raise ValueError("refinement produced duplicate cell ids")
    return tuple(result)


def split_observation_cell(
    cell: BeliefCell,
    atom_id: str,
    dimension: str,
    observation_labels: tuple[str, str] = ("obs-left", "obs-right"),
    *,
    distinguishability_proved: bool = False,
) -> tuple[BeliefCell, ...]:
    """Refine a support while enforcing nonanticipativity.

    Without a proof that the two predicates are observationally disjoint,
    the result is one refined cell with the original policy node.  If
    distinguishability is proved, the supported one-atom cell is split into
    two explicitly labelled policy nodes.  Multi-atom cells require a richer
    caller-supplied partition and are rejected rather than silently dropping
    atoms.
    """
    refined = split_support_atom(cell, atom_id, dimension)
    labels = tuple(observation_labels)
    if len(labels) != 2 or len(set(labels)) != 2 or not all(labels):
        raise ValueError("observation labels must be two distinct nonempty strings")
    if not distinguishability_proved:
        return (refined,)
    if len(cell.atoms) != 1:
        raise ValueError("distinguishable observation split needs an explicit partition for every atom")
    children = sorted(refined.atoms, key=lambda a: (tuple((x.lo, x.hi) for x in a.ego.as_tuple()), a.atom_id))
    if len(children) != 2:
        raise ValueError("observation split did not produce two support atoms")
    return tuple(
        BeliefCell(f"{cell.cell_id}|{label}", (atom,), actions=(),
                   policy_node_id=f"{cell.policy_node_id}|{label}")
        for label, atom in zip(labels, children)
    )


def apply_refinement(
    action: RefinementAction,
    *,
    automaton: ProtocolAutomaton,
    initial_support: tuple[SupportAtom, ...],
    targets: tuple[BeliefCell, ...] = (),
    master_cells: tuple[BeliefCell, ...] = (),
) -> RefinementResult:
    """Apply one action and return all changed abstract objects."""
    if action.kind is RefinementKind.EVENT_TIME:
        refined = refine_automaton_transition(automaton, action.target_id, action.clock_name)
        return RefinementResult(action, "REFINED", "EVENT_TIME_SPLIT",
                                automaton=refined, initial_support=initial_support,
                                targets=targets, master_cells=master_cells,
                                changed_ids=(action.target_id,))

    if action.kind is RefinementKind.SUPPORT:
        if action.role == "initial":
            # The initial support is not itself a Phase 4 BeliefCell.  Always
            # prefer this synthetic cell, even if a target happens to reuse
            # the same textual id.
            cell = BeliefCell(action.target_id, tuple(initial_support))
        else:
            pool = master_cells if action.role == "master" else targets
            matches = [c for c in tuple(pool) if c.cell_id == action.target_id]
            if len(matches) != 1:
                raise KeyError(f"support cell {action.target_id!r} not found uniquely")
            cell = matches[0]
        refined = split_support_atom(cell, action.atom_id or action.responsibility, action.axis)
        if action.role == "initial" and cell.cell_id == action.target_id:
            return RefinementResult(action, "REFINED", "SUPPORT_CELL_SPLIT",
                                    automaton=automaton,
                                    initial_support=refined.atoms, targets=targets,
                                    master_cells=master_cells,
                                    changed_ids=(action.target_id,))
        new_targets = _replace_cell(targets, (refined,), action.target_id) if any(
            c.cell_id == action.target_id for c in targets) else targets
        new_master = _replace_cell(master_cells, (refined,), action.target_id) if any(
            c.cell_id == action.target_id for c in master_cells) else master_cells
        return RefinementResult(action, "REFINED", "SUPPORT_CELL_SPLIT",
                                automaton=automaton, initial_support=initial_support,
                                targets=new_targets, master_cells=new_master,
                                changed_ids=(action.target_id,))

    if action.kind is RefinementKind.OBSERVATION:
        pool = master_cells if action.role == "master" else targets
        matches = [c for c in tuple(pool) if c.cell_id == action.target_id]
        if len(matches) != 1:
            raise KeyError(f"observation cell {action.target_id!r} not found uniquely")
        cell = matches[0]
        children = split_observation_cell(
            cell, action.atom_id or action.responsibility, action.axis, action.observation_labels,
            distinguishability_proved=action.distinguishability_proved)
        if len(children) == 1:
            replacement = children
        else:
            replacement = children
        new_targets = _replace_cell(targets, replacement, action.target_id) if any(
            c.cell_id == action.target_id for c in targets) else targets
        new_master = _replace_cell(master_cells, replacement, action.target_id) if any(
            c.cell_id == action.target_id for c in master_cells) else master_cells
        return RefinementResult(action, "REFINED", (
            "OBSERVATION_SPLIT" if len(children) > 1 else "OBSERVATION_SUPPORT_REFINED_NONANTICIPATIVE"),
                                automaton=automaton, initial_support=initial_support,
                                targets=new_targets, master_cells=new_master,
                                changed_ids=tuple(c.cell_id for c in children))

    raise ValueError("unsupported refinement kind")


@dataclass(frozen=True)
class ContractVersion:
    """All semantic digests that can change the meaning of evidence."""

    contract_digest: str
    protocol_digest: str = ""
    resource_digest: str = ""
    observation_digest: str = ""
    model_digest: str = ""
    generation: int = 0

    def __post_init__(self):
        if not self.contract_digest:
            raise ValueError("contract digest is required")
        if int(self.generation) < 0:
            raise ValueError("generation must be nonnegative")
        object.__setattr__(self, "generation", int(self.generation))

    def to_dict(self):
        return {"contract_digest": self.contract_digest,
                "protocol_digest": self.protocol_digest,
                "resource_digest": self.resource_digest,
                "observation_digest": self.observation_digest,
                "model_digest": self.model_digest,
                "generation": self.generation}


@dataclass(frozen=True)
class EvidenceRecord:
    evidence_id: str
    version: ContractVersion
    payload: Mapping[str, Any]
    active: bool = True
    invalid_reason: str = ""


class EvidenceRegistry:
    """Content-addressed evidence registry with automatic stale invalidation."""

    def __init__(self, version: ContractVersion):
        self.version = version
        self.records: dict[str, EvidenceRecord] = {}

    def register(self, payload: Mapping[str, Any], *, evidence_id: str | None = None) -> str:
        raw = json.dumps({"version": self.version.to_dict(), "payload": payload},
                         sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
        ref = evidence_id or "phase5-evidence-sha256:" + hashlib.sha256(raw).hexdigest()
        if ref in self.records:
            raise ValueError("duplicate evidence id")
        self.records[ref] = EvidenceRecord(ref, self.version, dict(payload))
        return ref

    def synchronize(self, version: ContractVersion, reason: str = "CONTRACT_CHANGED") -> int:
        """Invalidate every record when any semantic digest changes."""
        if version == self.version:
            return 0
        count = 0
        for ref, record in tuple(self.records.items()):
            if record.active:
                self.records[ref] = replace(record, active=False, invalid_reason=reason)
                count += 1
        self.version = version
        return count

    def invalidate(self, reason: str = "REFINEMENT_CHANGED_SUPPORT") -> int:
        count = 0
        for ref, record in tuple(self.records.items()):
            if record.active:
                self.records[ref] = replace(record, active=False, invalid_reason=reason)
                count += 1
        return count

    def valid(self, evidence_id: str, *, version: ContractVersion | None = None) -> bool:
        record = self.records.get(evidence_id)
        expected = self.version if version is None else version
        return bool(record and record.active and record.version == expected)

    def reason(self, evidence_id: str) -> str:
        record = self.records.get(evidence_id)
        if record is None:
            return "EVIDENCE_NOT_FOUND"
        return "VALID" if record.active else record.invalid_reason or "EVIDENCE_INVALID"


@dataclass(frozen=True)
class QueueItem:
    task_id: str
    payload: Mapping[str, Any]
    depth: int = 0
    responsibility: str = ""

    def __post_init__(self):
        if not self.task_id:
            raise ValueError("queue task id required")
        if int(self.depth) < 0:
            raise ValueError("queue depth must be nonnegative")
        object.__setattr__(self, "depth", int(self.depth))


class ResumableVerificationQueue:
    """Deterministic queue whose checkpoint is bound to a contract version."""

    def __init__(self, contract_digest: str, *, generation: int = 0):
        if not contract_digest:
            raise ValueError("queue contract digest required")
        self.contract_digest = contract_digest
        self.generation = int(generation)
        if self.generation < 0:
            raise ValueError("queue generation must be nonnegative")
        self._pending: deque[QueueItem] = deque()
        self._queued: set[str] = set()
        self._processed: list[str] = []
        self._inflight: QueueItem | None = None

    def push(self, item: QueueItem):
        if item.task_id in self._queued or item.task_id in self._processed:
            return False
        self._pending.append(item)
        self._queued.add(item.task_id)
        return True

    def pop(self) -> QueueItem | None:
        if self._inflight is not None:
            raise RuntimeError("verification queue already has an in-flight task")
        if not self._pending:
            return None
        item = self._pending.popleft()
        self._queued.discard(item.task_id)
        self._inflight = item
        return item

    def ack(self):
        if self._inflight is None:
            raise RuntimeError("verification queue has no in-flight task")
        self._processed.append(self._inflight.task_id)
        self._inflight = None

    def requeue_inflight(self):
        if self._inflight is None:
            return False
        item = self._inflight
        self._inflight = None
        self._pending.appendleft(item)
        self._queued.add(item.task_id)
        return True

    def clear_for_refinement(self, contract_digest: str, generation: int):
        if not contract_digest:
            raise ValueError("queue contract digest required")
        self.contract_digest = contract_digest
        self.generation = int(generation)
        self._pending.clear()
        self._queued.clear()
        self._processed.clear()
        self._inflight = None

    @property
    def inflight(self):
        return self._inflight

    @property
    def pending(self):
        return tuple(self._pending)

    @property
    def processed(self):
        return tuple(self._processed)

    def checkpoint(self) -> dict:
        return {"schema": CEGAR_SCHEMA + ".queue",
                "contract_digest": self.contract_digest,
                "generation": self.generation,
                "pending": [{"task_id": x.task_id, "payload": dict(x.payload),
                             "depth": x.depth, "responsibility": x.responsibility}
                            for x in self._pending],
                "inflight": None if self._inflight is None else {
                    "task_id": self._inflight.task_id, "payload": dict(self._inflight.payload),
                    "depth": self._inflight.depth, "responsibility": self._inflight.responsibility},
                "processed": list(self._processed)}

    @classmethod
    def from_checkpoint(cls, checkpoint: Mapping[str, Any], *, expected_contract_digest: str,
                        expected_generation: int | None = None):
        if checkpoint.get("schema") != CEGAR_SCHEMA + ".queue":
            raise ValueError("unsupported CEGAR queue schema")
        if checkpoint.get("contract_digest") != expected_contract_digest:
            raise ValueError("queue checkpoint contract digest mismatch")
        generation = int(checkpoint.get("generation", 0))
        if expected_generation is not None and generation != int(expected_generation):
            raise ValueError("queue checkpoint generation mismatch")
        result = cls(expected_contract_digest, generation=generation)
        pending_rows = tuple(checkpoint.get("pending", ()))
        pending_ids = [str(row["task_id"]) for row in pending_rows]
        if len(pending_ids) != len(set(pending_ids)):
            raise ValueError("duplicate pending queue task")
        for row in pending_rows:
            if not result.push(QueueItem(row["task_id"], dict(row["payload"]),
                                         int(row.get("depth", 0)), row.get("responsibility", ""))):
                raise ValueError("duplicate pending queue task")
        result._processed = [str(x) for x in checkpoint.get("processed", ())]
        result._queued = {x.task_id for x in result._pending}
        if len(result._processed) != len(set(result._processed)):
            raise ValueError("duplicate processed queue task")
        if result._queued & set(result._processed):
            raise ValueError("task appears in both pending and processed queue")
        inflight = checkpoint.get("inflight")
        if inflight is not None:
            item = QueueItem(inflight["task_id"], dict(inflight["payload"]),
                             int(inflight.get("depth", 0)), inflight.get("responsibility", ""))
            if item.task_id in result._queued or item.task_id in result._processed:
                raise ValueError("in-flight queue task duplicates another task")
            # A checkpoint taken during a verifier call resumes this task;
            # it is put back at the head rather than being marked complete.
            result._pending.appendleft(item)
            result._queued.add(item.task_id)
        return result


@dataclass(frozen=True)
class MasterProblem:
    """Finite action master updated after every abstract partition change."""

    cells: tuple[BeliefCell, ...]
    contract_digest: str
    blocked_actions: tuple[tuple[str, str, str], ...] = ()
    revision: int = 0

    def __post_init__(self):
        cells = tuple(self.cells)
        if len({c.cell_id for c in cells}) != len(cells):
            raise ValueError("master cells must have unique ids")
        object.__setattr__(self, "cells", cells)
        object.__setattr__(self, "blocked_actions", tuple(sorted(set(self.blocked_actions))))
        if int(self.revision) < 0:
            raise ValueError("master revision must be nonnegative")
        object.__setattr__(self, "revision", int(self.revision))

    def active_actions(self, cell_id: str):
        blocked = {(c, a) for c, a, _ in self.blocked_actions if c == cell_id}
        matches = [c for c in self.cells if c.cell_id == cell_id]
        if len(matches) != 1:
            raise KeyError(f"master cell {cell_id!r} not found uniquely")
        cell = matches[0]
        return tuple(a for a in cell.actions if (cell_id, a.action_id) not in blocked)

    def block(self, cell_id: str, action_id: str, reason: str):
        if not reason:
            raise ValueError("master block reason required")
        return replace(self, blocked_actions=self.blocked_actions + ((cell_id, action_id, reason),),
                       revision=self.revision + 1)

    def update(self, cells: Iterable[BeliefCell], contract_digest: str):
        """Install refined cells and force a new master revision."""
        return MasterProblem(tuple(cells), contract_digest, (), self.revision + 1)

    @property
    def digest(self):
        payload = {"cells": [(c.cell_id, c.policy_node_id,
                              [a.action_id for a in c.actions]) for c in self.cells],
                   "contract_digest": self.contract_digest,
                   "blocked_actions": self.blocked_actions,
                   "revision": self.revision}
        raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
        return "master-sha256:" + hashlib.sha256(raw).hexdigest()


def update_backup_policy_graph(cells: Iterable[BeliefCell], evidence, *,
                               expected_contract_digest: str | None = None):
    """Rebuild the finite backup graph after master/refinement updates.

    The import is local to avoid a module cycle.  ``build_backup_graph``
    independently recomputes the information fixed point and replays evidence;
    a stale graph is never edited in place.  The optional expected digest is a
    caller-owned current-contract guard.
    """
    digest = getattr(getattr(evidence, "contract", None), "digest", None)
    if not digest:
        raise ValueError("evidence store has no contract digest")
    if expected_contract_digest is not None and digest != expected_contract_digest:
        raise ValueError("policy graph evidence contract digest mismatch")
    from .backup_graph import build_backup_graph
    return build_backup_graph(tuple(cells), evidence)


@dataclass(frozen=True)
class RefinementLogEntry:
    iteration: int
    action: RefinementAction
    before_contract_digest: str
    after_contract_digest: str
    evidence_invalidated: int
    queue_reset: bool
    result: str

    def to_dict(self):
        return {"iteration": self.iteration,
                "action": {"kind": self.action.kind.value,
                           "responsibility": self.action.responsibility,
                           "axis": self.action.axis,
                           "target_id": self.action.target_id,
                           "reason": self.action.reason,
                           "atom_id": self.action.atom_id,
                           "clock_name": self.action.clock_name,
                           "role": self.action.role,
                           "observation_labels": list(self.action.observation_labels),
                           "distinguishability_proved": self.action.distinguishability_proved},
                "before_contract_digest": self.before_contract_digest,
                "after_contract_digest": self.after_contract_digest,
                "evidence_invalidated": self.evidence_invalidated,
                "queue_reset": self.queue_reset,
                "result": self.result}


@dataclass(frozen=True)
class CegarResult:
    status: str
    reason: str
    iterations: int
    verification_results: tuple[VerificationResult, ...]
    refinements: tuple[RefinementLogEntry, ...]
    pending_tasks: int
    contract_digest: str
    master_digest: str
    queue_checkpoint: Mapping[str, Any]

    def to_dict(self):
        return {"status": self.status, "reason": self.reason,
                "iterations": self.iterations,
                "verification_results": [x.to_dict() for x in self.verification_results],
                "refinements": [x.to_dict() for x in self.refinements],
                "pending_tasks": self.pending_tasks,
                "contract_digest": self.contract_digest,
                "master_digest": self.master_digest,
                "queue_checkpoint": dict(self.queue_checkpoint)}


class CegarEngine:
    """Run finite CEGAR iterations with explicit refinement responsibility."""

    def __init__(
        self,
        contract: FullVerifierContract,
        verifier_factory: Callable[[FullVerifierContract], FullSupportVerifier],
        *,
        refinement_selector: Callable[[VerificationResult], RefinementAction | None] | None = None,
        master: MasterProblem | None = None,
        registry: EvidenceRegistry | None = None,
        queue: ResumableVerificationQueue | None = None,
        master_cells: tuple[BeliefCell, ...] = (),
        max_iterations: int = 16,
        resource_digest: str = "",
    ):
        if not isinstance(contract, FullVerifierContract):
            raise TypeError("contract must be a FullVerifierContract")
        if not callable(verifier_factory):
            raise TypeError("verifier_factory must be callable")
        if int(max_iterations) <= 0:
            raise ValueError("max_iterations must be positive")
        self.contract = contract
        self.verifier_factory = verifier_factory
        self.refinement_selector = refinement_selector or default_refinement_selector
        self.resource_digest = str(resource_digest)
        self.master_cells = tuple(master_cells)
        self.master = master or MasterProblem(self.master_cells, contract.digest)
        if self.master.contract_digest != contract.digest:
            raise ValueError("master problem contract digest mismatch")
        version = ContractVersion(contract.digest, contract.automaton.digest(),
                                  resource_digest=self.resource_digest,
                                  observation_digest=contract.observation_digest,
                                  model_digest=contract.model_digest)
        self.registry = registry or EvidenceRegistry(version)
        if self.registry.version.contract_digest != contract.digest:
            raise ValueError("evidence registry contract digest mismatch")
        self.queue = queue or ResumableVerificationQueue(contract.digest,
                                                         generation=version.generation)
        if self.queue.contract_digest != contract.digest:
            raise ValueError("verification queue contract digest mismatch")
        self.max_iterations = int(max_iterations)
        self.logs: list[RefinementLogEntry] = []
        self.results: list[VerificationResult] = []
        self._iteration = 0
        if not self.queue.pending:
            self.queue.push(QueueItem("root", {"state": contract.automaton.initial_state_id}, 0, "initial"))

    def _version(self, generation: int | None = None) -> ContractVersion:
        return ContractVersion(self.contract.digest, self.contract.automaton.digest(),
                               resource_digest=self.resource_digest,
                               observation_digest=self.contract.observation_digest,
                               model_digest=self.contract.model_digest,
                               generation=self.registry.version.generation if generation is None
                               else generation)

    def apply(self, action: RefinementAction) -> RefinementLogEntry:
        before = self.contract.digest
        outcome = apply_refinement(
            action, automaton=self.contract.automaton,
            initial_support=self.contract.initial_support,
            targets=self.contract.targets,
            master_cells=self.master.cells,
        )
        new_contract = replace(
            self.contract,
            automaton=outcome.automaton or self.contract.automaton,
            initial_support=outcome.initial_support or self.contract.initial_support,
            targets=outcome.targets or self.contract.targets,
        )
        self.contract = new_contract
        generation = self.registry.version.generation + 1
        invalidated = self.registry.synchronize(
            self._version(generation), reason="CEGAR_REFINEMENT_CHANGED_CONTRACT")
        self.master_cells = outcome.master_cells or self.master.cells
        self.master = self.master.update(self.master_cells, self.contract.digest)
        self.queue.clear_for_refinement(self.contract.digest, generation)
        # A root task is intentionally generic; a caller can replace its
        # payload with a serialized VerificationTask before resuming.
        self.queue.push(QueueItem("root", {"state": self.contract.automaton.initial_state_id}, 0,
                                 action.responsibility))
        entry = RefinementLogEntry(self._iteration, action, before,
                                   self.contract.digest, invalidated, True, outcome.reason)
        self.logs.append(entry)
        return entry

    def run(self) -> CegarResult:
        for iteration in range(self.max_iterations):
            self._iteration = iteration
            item = self.queue.pop()
            if item is None:
                self.queue.push(QueueItem("root", {"state": self.contract.automaton.initial_state_id},
                                          iteration, "replenished"))
                self.queue.pop()
            verifier = self.verifier_factory(self.contract)
            result = verifier.verify()
            self.queue.ack()
            self.results.append(result)
            if result.status == VerifyStatus.CERTIFIED:
                return self._result(VerifyStatus.CERTIFIED,
                                    "CEGAR_REACHED_CERTIFIED_RESULT")
            if result.status == VerifyStatus.COUNTEREXAMPLE:
                return self._result(VerifyStatus.COUNTEREXAMPLE,
                                    "CONCRETE_COUNTEREXAMPLE_REPLAYED")
            if self.refinement_selector is None:
                return self._result(VerifyStatus.UNKNOWN,
                                    "CEGAR_REFINEMENT_SELECTOR_MISSING")
            try:
                action = self.refinement_selector(result)
            except Exception as exc:
                return self._result(VerifyStatus.UNKNOWN,
                                    "CEGAR_REFINEMENT_SELECTOR_ERROR:" + type(exc).__name__)
            if action is None:
                return self._result(VerifyStatus.UNKNOWN, "NO_REFINEMENT_FOR_UNKNOWN_OBLIGATION")
            try:
                self.apply(action)
            except Exception as exc:
                return self._result(VerifyStatus.UNKNOWN,
                                    "REFINEMENT_FAILED:" + type(exc).__name__)
        return self._result(VerifyStatus.UNKNOWN, "CEGAR_BUDGET_EXHAUSTED")

    def _result(self, status: str, reason: str) -> CegarResult:
        return CegarResult(status, reason, len(self.results), tuple(self.results),
                           tuple(self.logs), len(self.queue.pending), self.contract.digest,
                           self.master.digest, self.queue.checkpoint())


__all__ = [
    "PHASE5_SCOPE", "CEGAR_SCHEMA", "CounterexampleKind", "ReplayAssessment",
    "classify_counterexample", "split_time_window", "split_protocol_transition",
    "refine_automaton_transition", "RefinementKind", "default_refinement_selector", "RefinementAction",
    "RefinementResult", "split_observation_cell", "apply_refinement",
    "ContractVersion", "EvidenceRecord", "EvidenceRegistry", "QueueItem",
    "ResumableVerificationQueue", "MasterProblem", "update_backup_policy_graph", "RefinementLogEntry",
    "CegarResult", "CegarEngine",
]
