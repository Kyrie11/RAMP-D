#!/usr/bin/env python3
"""Build and replay the Phase 3 public backup-policy graph fixture."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from rampd_core import (
    Interval, StateBounds, SupportAtom, BeliefCell, SafeDomain,
    ActionWitness, AtomTransition, ObservationSuccessors, EvidenceVerdict,
    compute_information_invariant, default_backup_limits,
    synthesize_public_backup, save_backup_graph, replay_backup_graph,
)


def _state(px):
    return StateBounds(Interval(*px), Interval(-1, 1), Interval(-.1, .1),
                       Interval(0, 10), Interval(-2, 2), Interval(-.3, .3))


def _atom(aid, px):
    return SupportAtom(aid, _state(px), (),
                       (("monitor", "ok"), ("protocol", "open")))


def build_fixture():
    l0, l1 = _atom("l0", (0, .5)), _atom("l1", (.5, 1))
    L = BeliefCell("L", (l0, l1), (
        ActionWitness("hold", (0., 0.), (
            AtomTransition("l0", EvidenceVerdict.PROVED, "demo-l0",
                           (ObservationSuccessors("stay", (l0,)),)),
            AtomTransition("l1", EvidenceVerdict.PROVED, "demo-l1",
                           (ObservationSuccessors("stay", (l1,)),)),)),))
    a0, a1 = _atom("a0", (2, 2.5)), _atom("a1", (2.5, 3))
    A = BeliefCell("A", (a0, a1), (
        ActionWitness("yield", (-1., 0.), (
            AtomTransition("a0", EvidenceVerdict.PROVED, "demo-a0",
                           (ObservationSuccessors("yielded", (l0,)),)),
            AtomTransition("a1", EvidenceVerdict.PROVED, "demo-a1",
                           (ObservationSuccessors("yielded", (l1,)),)),)),))
    safe = SafeDomain(
        StateBounds(Interval(-10, 10), Interval(-10, 10), Interval(-1, 1),
                    Interval(0, 20), Interval(-5, 5), Interval(-.5, .5)),
        allowed_modes=(("monitor", ("ok",)), ("protocol", ("open",))),
        required_mode_fields=("monitor", "protocol"),
    )
    invariant = compute_information_invariant((A, L), safe,
                                              lambda ref: ref.startswith("demo-"))
    return (A, L), invariant


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--output", type=Path, default=Path("reports/phase3_demo.json"))
    ap.add_argument("--graph", type=Path,
                    default=Path("reports/phase3_backup_graph.json"))
    args = ap.parse_args()
    cells, invariant = build_fixture()
    limits = default_backup_limits()
    synthesis = synthesize_public_backup(cells, invariant, control_limits=limits)
    if synthesis.graph is None:
        raise SystemExit(json.dumps({"status": synthesis.status,
                                     "reasons": synthesis.reasons}))
    save_backup_graph(args.graph, synthesis.graph)
    replay_ok, replay_message = replay_backup_graph(args.graph, limits)
    payload = {
        "classification": "finite_public_backup_graph_demo_not_vehicle_safety_experiment",
        "status": synthesis.status,
        "nodes": synthesis.executable_nodes,
        "retained_cell_ids": list(invariant.retained_cell_ids),
        "all_children_retained": synthesis.all_children_retained,
        "common_control_violations": synthesis.common_control_violations,
        "certificate_replay": replay_ok,
        "certificate_replay_message": replay_message,
        "assurance_scope": synthesis.assurance_scope,
        "certified": synthesis.certified,
        "graph": str(args.graph),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2) + "\n")
    print(json.dumps(payload, indent=2))
    if (synthesis.status != "BACKUP_GRAPH_SYNTHESIZED" or
            not replay_ok or synthesis.executable_nodes != len(invariant.retained_cell_ids)):
        raise SystemExit(2)


if __name__ == "__main__":
    main()
