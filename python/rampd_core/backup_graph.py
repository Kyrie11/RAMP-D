"""Executable public backup graph with fail-closed local execution guards.

The graph is executable in the declared Phase 3 benchmark model. It cannot
authorize real-world or full-protocol execution before Phase 4 certification.
"""
from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
import json
import math
from pathlib import Path

from .interval import Interval
from .belief import BeliefCell
from .backup import ASSURANCE_SCOPE, LocalEvidenceStore
from .invariant import (compute_information_invariant, support_subset_cell,
                        EvidenceContext, _atom, _atom_from, _action, _action_from)


class BackupExecutionError(RuntimeError):
    """Local evidence is lost. No default maneuver is silently substituted."""


@dataclass(frozen=True)
class BackupNode:
    cell: BeliefCell
    action: object
    controller_ref: str
    observation_children: tuple[tuple[str, str], ...]


@dataclass(frozen=True)
class BackupPolicyGraph:
    cells: tuple[BeliefCell, ...]
    nodes: tuple[BackupNode, ...]
    invariant: object
    evidence: LocalEvidenceStore
    assurance_scope: str = ASSURANCE_SCOPE
    full_support_certified: bool = False

    @property
    def node_map(self):
        return {n.cell.cell_id: n for n in self.nodes}

    @property
    def contract_digest(self):
        return self.evidence.contract.digest


def build_backup_graph(cells, evidence):
    cells = tuple(cells)
    invariant = compute_information_invariant(cells, evidence.contract.domain, evidence.verify)
    by_id = {c.cell_id: c for c in cells}
    nodes = []
    for decision in invariant.decisions:
        if not decision.retained:
            continue
        cell = by_id[decision.cell_id]
        action = next(a for a in cell.actions if a.action_id == decision.selected_action_id)
        if action.controller_ref not in evidence.laws:
            raise ValueError("retained action does not resolve to an executable public law")
        nodes.append(BackupNode(cell, action, action.controller_ref, decision.observation_children))
    return BackupPolicyGraph(cells, tuple(nodes), invariant, evidence)


def _node_claims(graph):
    return [{"cell_id": n.cell.cell_id, "action_id": n.action.action_id,
             "controller_ref": n.controller_ref,
             "observation_children": [list(pair) for pair in n.observation_children]}
            for n in graph.nodes]


def save_backup_graph(graph, path):
    payload = {"schema": "rampd.public-backup-graph.v1",
               "assurance_scope": ASSURANCE_SCOPE, "full_support_certified": False,
               "contract_digest": graph.contract_digest,
               "cells": [{"cell_id": c.cell_id, "policy_node_id": c.policy_node_id,
                          "atoms": [_atom(a) for a in c.atoms],
                          "actions": [_action(a) for a in c.actions]} for c in graph.cells],
               "nodes": _node_claims(graph), "evidence": graph.evidence.to_dict()}
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n")


def load_backup_graph(path_or_dict, *, expected_contract_digest=None):
    """Replay every selected edge and the fixed point; raise on mismatched claims.

    A caller that intends execution MUST pin its own trusted contract digest;
    the self-described certificate alone cannot attest to the current scene.
    """
    d = path_or_dict if isinstance(path_or_dict, dict) else json.loads(Path(path_or_dict).read_text())
    if (d.get("schema") != "rampd.public-backup-graph.v1" or
            d.get("assurance_scope") != ASSURANCE_SCOPE or d.get("full_support_certified") is not False):
        raise ValueError("unsupported backup graph schema/assurance")
    evidence = LocalEvidenceStore.from_dict(d["evidence"])
    if evidence.contract.digest != d["contract_digest"]:
        raise ValueError("graph contract digest mismatch")
    if expected_contract_digest is not None and evidence.contract.digest != expected_contract_digest:
        raise ValueError("graph does not match the caller's current contract")
    cells = tuple(BeliefCell(c["cell_id"], tuple(_atom_from(a) for a in c["atoms"]),
                            tuple(_action_from(a) for a in c["actions"]), c["policy_node_id"])
                  for c in d["cells"])
    graph = build_backup_graph(cells, evidence)
    if _node_claims(graph) != d["nodes"]:
        raise ValueError("backup graph differs from independently recomputed fixed point")
    return graph


def _time(value):
    if isinstance(value, Fraction):
        result = value
    else:
        value = float(value)
        if not math.isfinite(value):
            raise BackupExecutionError("nonfinite execution time")
        result = Fraction.from_float(value)
    if result < 0:
        raise BackupExecutionError("negative execution time")
    return result


class BackupExecutor:
    """One public law per node; advance only on a real observation and posterior.

    The supplied support must be a sound state estimate. This class checks
    containment, complete stored posterior coverage and measurement-domain
    consistency; Phase 4 must establish the real observation/protocol model.
    """
    def __init__(self, graph, start_cell_id, initial_support, *, expected_contract_digest,
                 start_time=Fraction(0)):
        if expected_contract_digest != graph.contract_digest:
            raise BackupExecutionError("current contract differs from verified contract")
        # Public dataclasses are serializable containers, not proof tokens.
        # Rebuild even for an in-memory graph so hand-constructed/truncated
        # nodes cannot bypass the same checks used by the file loader.
        try:
            replayed = build_backup_graph(graph.cells, graph.evidence)
            if _node_claims(replayed) != _node_claims(graph):
                raise ValueError("node claims differ from the replayed closed graph")
        except (ValueError, TypeError, KeyError, RuntimeError) as exc:
            raise BackupExecutionError("backup graph replay failed: " + str(exc)) from exc
        self.graph = graph
        self._expected_contract_digest = expected_contract_digest
        self._nodes = graph.node_map
        if start_cell_id not in self._nodes:
            raise BackupExecutionError("start node was not retained")
        self.cell_id = start_cell_id
        self._support = initial_support
        self._time = _time(start_time)
        self._pending = False
        self._lost = False
        self._pending_posterior = None
        self._guard_support(initial_support, self._nodes[self.cell_id].cell)

    @property
    def next_time(self):
        return self._time + Fraction.from_float(self.graph.evidence.contract.decision_period_s)

    @property
    def time(self):
        return self._time

    @property
    def lost(self):
        return self._lost

    def _fail(self, reason):
        self._lost = True
        raise BackupExecutionError(reason)

    def _guard_support(self, support, target):
        if not isinstance(support, BeliefCell) or not support_subset_cell(support.atoms, target):
            self._fail("state/support outside the verified information cell")

    def command(self, measured_state, *, at_time):
        if self._lost:
            self._fail("local certificate already lost")
        try:
            actual_time = _time(at_time)
        except (ValueError, TypeError, OverflowError, BackupExecutionError) as exc:
            self._fail("invalid command time: " + str(exc))
        if self._pending or actual_time != self._time:
            self._fail("command requested outside its decision instant or repeated before update")
        node = self._nodes[self.cell_id]
        if self.graph.contract_digest != self._expected_contract_digest:
            self._fail("current contract changed after executor initialization")
        if node.controller_ref != node.action.controller_ref:
            self._fail("node law differs from its verified action law")
        law = self.graph.evidence.laws.get(node.controller_ref)
        if law is None or law.digest != node.controller_ref:
            self._fail("missing or mismatched executable law digest")
        transitions = {t.source_atom_id: t for t in node.action.transitions}
        if (len(transitions) != len(node.action.transitions) or
                set(transitions) != {a.atom_id for a in node.cell.atoms}):
            self._fail("cached action lacks complete source transition coverage")
        # Check current proof bindings at use time; a mutated/stale in-memory
        # object must not silently change the controller under a cached graph.
        for atom in node.cell.atoms:
            transition = transitions[atom.atom_id]
            if not self.graph.evidence.verify(
                    EvidenceContext(node.cell, atom, node.action, transition)):
                self._fail("cached transition evidence failed replay")
        try:
            values = tuple(float(x) for x in measured_state)
            if len(values) != 6 or not all(math.isfinite(x) for x in values):
                self._fail("invalid ego measurement")
            error = self.graph.evidence.contract.measurement_error
            compatible = [a for a in self._support.atoms
                          if all((x+e).contains(y) for x, e, y in zip(a.ego.as_tuple(), error, values))]
            if not compatible:
                self._fail("ego measurement outside the declared measurement domain")
            command = law.command(values)
            if not all(all(bound.contains(u) for bound, u in zip(
                    law.image(a.ego, error).as_tuple(), command)) for a in compatible):
                self._fail("executed command outside the verified control image")
        except (ValueError, TypeError, OverflowError) as exc:
            self._fail("invalid measured state: " + str(exc))
        self._pending = True
        self._pending_posterior = {}
        for transition in node.action.transitions:
            for branch in transition.branches:
                self._pending_posterior.setdefault(branch.observation, []).extend(branch.atoms)
        return command

    def advance(self, observation, posterior, *, at_time):
        if self._lost:
            self._fail("local certificate already lost")
        try:
            actual_time = _time(at_time)
        except (ValueError, TypeError, OverflowError, BackupExecutionError) as exc:
            self._fail("invalid observation time: " + str(exc))
        if not self._pending or actual_time != self.next_time:
            self._fail("observation update outside the verified decision interval")
        if self.graph.contract_digest != self._expected_contract_digest:
            self._fail("current contract changed during the execution interval")
        node = self._nodes[self.cell_id]
        children = dict(node.observation_children)
        if not isinstance(observation, str) or not observation:
            self._fail("invalid observation label")
        if observation not in children:
            self._fail("uncovered observation; no default child is permitted")
        child = self._nodes[children[observation]]
        # Check measured posterior against both the propagated bound and child.
        # Atom IDs can coincide across source branches; only geometry/modes
        # matter, so give this temporary union unique representation IDs.
        from dataclasses import replace
        atoms = tuple(replace(a, atom_id=f"runtime-post:{i}") for i, a in
                      enumerate(self._pending_posterior[observation]))
        propagated = BeliefCell("runtime-post", atoms)
        self._guard_support(posterior, propagated)
        self._guard_support(posterior, child.cell)
        self.cell_id = child.cell.cell_id
        self._support = posterior
        self._time = self.next_time
        self._pending = False
        self._pending_posterior = None
        return self.cell_id
