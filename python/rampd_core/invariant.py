"""Finite robust information-state predecessor and greatest fixed point.

This is an exact solver for the supplied finite abstract game. It only accepts
per-atom transition evidence that an external evidence verifier approves.
The returned set is labelled S_in_candidate: Phase 2 does not itself establish
that the abstraction covers the concrete protocol support or that the evidence
backend is the full Phase 4 verifier.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Iterable
import json
from pathlib import Path

from .belief import BeliefCell, SupportAtom
from .interval import Interval
from .model import StateBounds, BicycleParameters, prove_friction_feasible


class EvidenceVerdict(str, Enum):
    PROVED = "PROVED"
    UNKNOWN = "UNKNOWN"
    VIOLATION = "VIOLATION"


@dataclass(frozen=True)
class ObservationSuccessors:
    observation: str
    atoms: tuple[SupportAtom, ...]
    def __post_init__(self):
        if not self.observation:
            raise ValueError("observation label must be nonempty")
        if not self.atoms:
            raise ValueError("empty observation branches must be omitted")
        object.__setattr__(self, "atoms", tuple(self.atoms))


@dataclass(frozen=True)
class AtomTransition:
    source_atom_id: str
    verdict: EvidenceVerdict
    evidence_ref: str | None
    branches: tuple[ObservationSuccessors, ...]
    def __post_init__(self):
        if not self.source_atom_id:
            raise ValueError("source_atom_id must be nonempty")
        if not isinstance(self.verdict, EvidenceVerdict):
            object.__setattr__(self, "verdict", EvidenceVerdict(self.verdict))
        if self.verdict is EvidenceVerdict.PROVED and not self.evidence_ref:
            raise ValueError("PROVED transition requires evidence_ref")
        branches = tuple(self.branches)
        if not branches:
            raise ValueError("each source atom must have at least one possible observation branch")
        if len({b.observation for b in branches}) != len(branches):
            raise ValueError("duplicate observation branch for one source atom")
        object.__setattr__(self, "branches", branches)


@dataclass(frozen=True)
class ActionWitness:
    """One common control and complete successor support for every source atom."""
    action_id: str
    control: tuple[float, ...]
    transitions: tuple[AtomTransition, ...]
    def __post_init__(self):
        if not self.action_id:
            raise ValueError("action_id must be nonempty")
        control = tuple(float(x) for x in self.control)
        if len(control) != 2 or any(not __import__('math').isfinite(x) for x in control):
            raise ValueError("common ego control must be (jerk, steering_rate), both finite")
        transitions = tuple(self.transitions)
        if not transitions:
            raise ValueError("action witness needs transitions")
        if len({t.source_atom_id for t in transitions}) != len(transitions):
            raise ValueError("one transition per source atom is required")
        object.__setattr__(self, "control", control)
        object.__setattr__(self, "transitions", transitions)


@dataclass(frozen=True)
class SafeDomain:
    ego_bounds: StateBounds
    other_bounds: tuple[tuple[str, Interval], ...] = ()
    allowed_modes: tuple[tuple[str, tuple[str, ...]], ...] = ()
    required_mode_fields: tuple[str, ...] = ()
    friction: BicycleParameters | None = None
    def __post_init__(self):
        other = tuple(sorted(self.other_bounds))
        allowed = tuple(sorted((str(k), tuple(sorted(set(v)))) for k, v in self.allowed_modes))
        if any(not isinstance(v, Interval) for _, v in other):
            raise TypeError("other_bounds must contain intervals")
        if any(not vals for _, vals in allowed):
            raise ValueError("allowed mode sets must be nonempty")
        object.__setattr__(self, "other_bounds", other)
        object.__setattr__(self, "allowed_modes", allowed)
        object.__setattr__(self, "required_mode_fields", tuple(sorted(set(self.required_mode_fields))))

    def contains_atom(self, atom: SupportAtom) -> tuple[bool, str]:
        if not self.ego_bounds.contains(atom.ego):
            return False, "EGO_STATE_OUTSIDE_SAFE_DOMAIN"
        other = atom.other_dict
        for name, bound in self.other_bounds:
            if name not in other or not bound.contains(other[name]):
                return False, f"OTHER_STATE_OUTSIDE_SAFE_DOMAIN:{name}"
        mode = atom.mode_dict
        for key in self.required_mode_fields:
            if key not in mode:
                return False, f"MISSING_REQUIRED_MODE:{key}"
        for key, allowed in self.allowed_modes:
            if key not in mode or mode[key] not in allowed:
                return False, f"MODE_OUTSIDE_SAFE_DOMAIN:{key}"
        if self.friction is not None:
            try:
                if not prove_friction_feasible(atom.ego, self.friction):
                    return False, "FRICTION_NOT_PROVED_FEASIBLE"
            except Exception:
                return False, "FRICTION_ENCLOSURE_UNRESOLVED"
        return True, "SAFE"


@dataclass(frozen=True)
class CellDecision:
    cell_id: str
    retained: bool
    reason: str
    selected_action_id: str | None = None
    control: tuple[float, ...] | None = None
    observation_children: tuple[tuple[str, str], ...] = ()
    iteration: int | None = None


@dataclass(frozen=True)
class InvariantResult:
    status: str
    retained_cell_ids: tuple[str, ...]
    decisions: tuple[CellDecision, ...]
    iterations: int
    removals_per_iteration: tuple[int, ...]
    assurance_scope: str = "FINITE_ABSTRACTION_ONLY"
    certified: bool = False


def _atom_subset(a: SupportAtom, b: SupportAtom) -> bool:
    """Prove box(a) subset box(b), including exact discrete-mode equality."""
    if a.mode != b.mode:
        return False
    if set(a.other_dict) != set(b.other_dict):
        return False
    if not b.ego.contains(a.ego):
        return False
    bd, ad = b.other_dict, a.other_dict
    return all(bd[k].contains(ad[k]) for k in ad)


def support_subset_cell(support: Iterable[SupportAtom], cell: BeliefCell) -> bool:
    """Conservative union coverage: each posterior box lies in a target atom.

    A box covered only by the union of several partially overlapping target
    boxes is not accepted; that case is unresolved and requires refinement.
    """
    target = cell.atoms
    return all(any(_atom_subset(succ, t) for t in target) for succ in support)


def _evaluate_action(cell: BeliefCell, action: ActionWitness,
                     current: dict[str, BeliefCell],
                     evidence_verifier: Callable[[str], bool] | None,
                     atom_index: dict[str, list[BeliefCell]]):
    source_ids = {a.atom_id for a in cell.atoms}
    transition_ids = {t.source_atom_id for t in action.transitions}
    if source_ids != transition_ids:
        return None, "INCOMPLETE_SOURCE_COVERAGE"
    if evidence_verifier is None:
        return None, "NO_EVIDENCE_VERIFIER"
    posterior: dict[str, list[SupportAtom]] = {}
    for tr in action.transitions:
        if tr.verdict is not EvidenceVerdict.PROVED:
            return None, "TRANSITION_" + tr.verdict.value
        try:
            evidence_ok = bool(evidence_verifier(tr.evidence_ref))
        except Exception:
            evidence_ok = False
        if not evidence_ok:
            return None, "EVIDENCE_REPLAY_FAILED"
        for branch in tr.branches:
            posterior.setdefault(branch.observation, []).extend(branch.atoms)
    if not posterior:
        return None, "NO_POSSIBLE_OBSERVATION"
    children = []
    for observation in sorted(posterior):
        support = posterior[observation]
        # Fast path: successor atom identifiers are stable across an abstract
        # transition. If a target cell contains the same atom id, check those
        # candidates first; fall back to the full cell family when needed.
        first_candidates = atom_index.get(support[0].atom_id, [])
        targets = [c for c in first_candidates if support_subset_cell(support, c)]
        if not targets:
            seen = {c.cell_id for c in first_candidates}
            targets = [c for cid, c in current.items()
                       if cid not in seen and support_subset_cell(support, c)]
        if not targets:
            return None, f"POSTERIOR_NOT_COVERED:{observation}"
        target = min(targets, key=lambda c: c.cell_id)
        children.append((observation, target.cell_id))
    return tuple(children), "PREDECESSOR_PROVED"


def compute_information_invariant(cells: Iterable[BeliefCell], safe_domain: SafeDomain,
                                  evidence_verifier: Callable[[str], bool] | None = None) -> InvariantResult:
    """Compute the greatest fixed point of the supplied finite info-state game.

    S0 contains only cells wholly inside the hard-safe domain. A cell remains
    iff there exists one common action whose every atom transition is proved
    safe and every nonempty observation posterior is covered by one cell in
    the current S. The iteration is monotone decreasing and removes at least
    one cell on every nonterminal iteration, hence at most M removals.
    """
    cells = tuple(cells)
    if not cells:
        raise ValueError("at least one abstract belief cell is required")
    if len({c.cell_id for c in cells}) != len(cells):
        raise ValueError("cell ids must be unique")
    if len({c.policy_node_id for c in cells}) != len(cells):
        raise ValueError("each complete belief support must have one unique policy node; merge observationally equivalent subcells into one support")
    by_id = {c.cell_id: c for c in cells}
    decisions: dict[str, CellDecision] = {}
    current: dict[str, BeliefCell] = {}
    for c in cells:
        unsafe = [safe_domain.contains_atom(a) for a in c.atoms]
        failed = next((reason for ok, reason in unsafe if not ok), None)
        if failed:
            decisions[c.cell_id] = CellDecision(c.cell_id, False, "INITIAL_" + failed)
        else:
            current[c.cell_id] = c
    removals = []
    iteration = 0
    while True:
        iteration += 1
        remove_now: dict[str, str] = {}
        selected: dict[str, tuple[ActionWitness, tuple[tuple[str, str], ...]]] = {}
        atom_index: dict[str, list[BeliefCell]] = {}
        for target_cell in current.values():
            for target_atom in target_cell.atoms:
                atom_index.setdefault(target_atom.atom_id, []).append(target_cell)
        for cell_id in sorted(current):
            cell = current[cell_id]
            reasons = []
            actions = sorted(cell.actions, key=lambda a: a.action_id)
            for action in actions:
                if not isinstance(action, ActionWitness):
                    reasons.append("INVALID_ACTION_WITNESS")
                    continue
                children, reason = _evaluate_action(cell, action, current, evidence_verifier, atom_index)
                if children is not None:
                    selected[cell_id] = (action, children)
                    break
                reasons.append(reason)
            if cell_id not in selected:
                if not actions:
                    remove_now[cell_id] = "NO_CANDIDATE_ACTION"
                else:
                    remove_now[cell_id] = "NO_ROBUST_COMMON_ACTION:" + "|".join(sorted(set(reasons)))
        # Simultaneous elimination is required for the greatest fixed point.
        for cell_id, reason in remove_now.items():
            current.pop(cell_id)
            decisions[cell_id] = CellDecision(cell_id, False, reason, iteration=iteration)
        removals.append(len(remove_now))
        if not remove_now:
            for cell_id, (action, children) in selected.items():
                decisions[cell_id] = CellDecision(cell_id, True, "FIXPOINT_WITNESS",
                    action.action_id, action.control, children, iteration)
            break
        if iteration > len(cells) + 1:
            raise RuntimeError("finite fixed-point termination invariant violated")
    # Ensure no retained child points outside the final fixed point.
    retained = set(current)
    for cid in retained:
        d = decisions[cid]
        if any(child not in retained for _, child in d.observation_children):
            raise RuntimeError("internal error: retained witness points to removed cell")
    return InvariantResult(
        status="FIXPOINT_CONVERGED",
        retained_cell_ids=tuple(sorted(retained)),
        decisions=tuple(decisions[k] for k in sorted(decisions)),
        iterations=iteration,
        removals_per_iteration=tuple(removals),
    )


# ----------------------------- JSON certificates -----------------------------
def _iv(x): return [x.lo, x.hi]
def _state(s): return [_iv(v) for v in s.as_tuple()]
def _atom(a):
    return {"atom_id": a.atom_id, "ego": _state(a.ego),
            "other": {k: _iv(v) for k, v in a.other}, "mode": dict(a.mode)}
def _atom_from(d):
    return SupportAtom(d["atom_id"], StateBounds(*(Interval(*x) for x in d["ego"])),
        tuple((k, Interval(*v)) for k, v in d.get("other", {}).items()),
        tuple(d.get("mode", {}).items()))
def _action(a):
    return {"action_id": a.action_id, "control": list(a.control), "transitions": [
        {"source_atom_id": t.source_atom_id, "verdict": t.verdict.value,
         "evidence_ref": t.evidence_ref, "branches": [
             {"observation": b.observation, "atoms": [_atom(x) for x in b.atoms]}
             for b in t.branches]} for t in a.transitions]}
def _action_from(d):
    return ActionWitness(d["action_id"], tuple(d["control"]), tuple(
        AtomTransition(t["source_atom_id"], EvidenceVerdict(t["verdict"]), t.get("evidence_ref"),
            tuple(ObservationSuccessors(b["observation"], tuple(_atom_from(x) for x in b["atoms"]))
                  for b in t["branches"])) for t in d["transitions"]))
def _domain(d):
    return {"ego_bounds": _state(d.ego_bounds),
            "other_bounds": {k: _iv(v) for k, v in d.other_bounds},
            "allowed_modes": {k: list(v) for k, v in d.allowed_modes},
            "required_mode_fields": list(d.required_mode_fields),
            "friction": None if d.friction is None else {
                "wheelbase_m": d.friction.wheelbase_m,
                "friction_coefficient": d.friction.friction_coefficient,
                "gravity_mps2": d.friction.gravity_mps2}}
def _domain_from(d):
    fr = d.get("friction")
    fp = None if fr is None else BicycleParameters(**fr)
    return SafeDomain(StateBounds(*(Interval(*x) for x in d["ego_bounds"])),
        tuple((k, Interval(*v)) for k, v in d.get("other_bounds", {}).items()),
        tuple((k, tuple(v)) for k, v in d.get("allowed_modes", {}).items()),
        tuple(d.get("required_mode_fields", ())), fp)


def save_invariant_certificate(path: str | Path, cells: Iterable[BeliefCell],
                               safe_domain: SafeDomain, result: InvariantResult):
    payload = {"schema": "rampd.info-invariant-candidate.v1",
        "assurance_scope": "FINITE_ABSTRACTION_ONLY", "certified": False,
        "safe_domain": _domain(safe_domain),
        "cells": [{"cell_id": c.cell_id, "policy_node_id": c.policy_node_id,
                   "atoms": [_atom(a) for a in c.atoms],
                   "actions": [_action(a) for a in c.actions]} for c in cells],
        "claimed_result": {"retained_cell_ids": list(result.retained_cell_ids),
            "iterations": result.iterations,
            "removals_per_iteration": list(result.removals_per_iteration),
            "decisions": [{"cell_id": d.cell_id, "retained": d.retained,
                "reason": d.reason, "selected_action_id": d.selected_action_id,
                "control": d.control, "observation_children": list(d.observation_children),
                "iteration": d.iteration} for d in result.decisions]}}
    Path(path).write_text(json.dumps(payload, sort_keys=True, indent=2) + "\n")


@dataclass(frozen=True)
class ReplayResult:
    ok: bool
    message: str
    recomputed: InvariantResult | None = None


def replay_invariant_certificate(path: str | Path,
        evidence_verifier: Callable[[str], bool] | None = None) -> ReplayResult:
    try:
        d = json.loads(Path(path).read_text())
        if d.get("schema") != "rampd.info-invariant-candidate.v1":
            return ReplayResult(False, "unsupported schema")
        if d.get("certified") is not False or d.get("assurance_scope") != "FINITE_ABSTRACTION_ONLY":
            return ReplayResult(False, "invalid assurance claim")
        cells = tuple(BeliefCell(c["cell_id"], tuple(_atom_from(a) for a in c["atoms"]),
            tuple(_action_from(a) for a in c["actions"]), c.get("policy_node_id"))
            for c in d["cells"])
        result = compute_information_invariant(cells, _domain_from(d["safe_domain"]), evidence_verifier)
        claimed = d["claimed_result"]
        actual = {"retained_cell_ids": list(result.retained_cell_ids),
            "iterations": result.iterations,
            "removals_per_iteration": list(result.removals_per_iteration),
            "decisions": [{"cell_id": x.cell_id, "retained": x.retained,
                "reason": x.reason, "selected_action_id": x.selected_action_id,
                "control": None if x.control is None else list(x.control), "observation_children": [list(y) for y in x.observation_children],
                "iteration": x.iteration} for x in result.decisions]}
        if actual != claimed:
            return ReplayResult(False, "fixed-point result does not match recomputation", result)
        return ReplayResult(True, "finite abstraction fixed point replayed; not a concrete safety certificate", result)
    except Exception as exc:
        return ReplayResult(False, f"replay failed: {type(exc).__name__}: {exc}")
