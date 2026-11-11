#!/usr/bin/env python3
"""Replay a Phase 3 graph; never infer a real-scene/full-protocol certificate.

Without --expected-contract-digest, the contract is self-described by the
artifact. Supplying a digest pins the caller's contract, but does not prove
that its physical assumptions hold in the current world.
"""
import argparse
import json
from pathlib import Path

from rampd_core.backup_graph import load_backup_graph


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("graph", type=Path)
    ap.add_argument("--expected-contract-digest", default=None,
                    help="Optional contract digest supplied independently by the caller")
    args = ap.parse_args()
    try:
        graph = load_backup_graph(
            args.graph, expected_contract_digest=args.expected_contract_digest)
        node_ids = set(graph.node_map)
        closed = all(child in node_ids for node in graph.nodes
                     for _, child in node.observation_children)
        if not closed:
            raise ValueError("retained graph is not closed")
        result = {
            "status": "BACKUP_GRAPH_REPLAY_PASS",
            "ok": True,
            "assurance_scope": graph.assurance_scope,
            "full_support_certified": False,
            "current_scene_verified": False,
            "contract_digest": graph.contract_digest,
            "caller_contract_pinned": args.expected_contract_digest is not None,
            "retained_nodes": len(graph.nodes),
            "retained_cell_ids": sorted(node_ids),
            "closed_graph": closed,
            "message": (
                "Graph, local evidence and finite fixed point replayed against the caller's contract digest."
                if args.expected_contract_digest is not None else
                "Graph, local evidence and finite fixed point replayed under the artifact's self-described contract."
            ),
        }
    except (OSError, ValueError, TypeError, KeyError, AttributeError,
            RuntimeError, OverflowError, ZeroDivisionError) as exc:
        print(json.dumps({
            "status": "BACKUP_GRAPH_REPLAY_FAILED", "ok": False,
            "full_support_certified": False, "current_scene_verified": False,
            "message": f"{type(exc).__name__}: {exc}",
        }, indent=2, allow_nan=False))
        return 2
    print(json.dumps(result, indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
