#!/usr/bin/env python3
"""Aggregate RAPID-AD per-episode diagnostics and estimate factorial interactions."""
from __future__ import annotations

import argparse
import csv
import json
import math
import statistics
from collections import defaultdict
from pathlib import Path
from typing import Any


def _bool(x: Any) -> bool:
    return bool(x) if x is not None else False


def _median(values: list[float]) -> float | None:
    return statistics.median(values) if values else None


def load_episodes(data_root: Path, run_tag: str | None = None) -> list[dict]:
    episodes = []
    search_root = (data_root / "runs" / run_tag) if run_tag else (data_root / "runs")
    for path in search_root.glob("**/rapid_ad_metrics.json"):
        try:
            obj = json.loads(path.read_text(encoding="utf-8"))
            obj["_path"] = str(path)
            episodes.append(obj)
        except Exception as exc:
            print(f"[WARN] cannot read {path}: {exc}")
    return episodes


def outcome_failure(ep: dict) -> bool:
    task = (ep.get("case") or {}).get("task")
    if task == "go_to_stop":
        return _bool(ep.get("unsafe_crossing_while_stop")) or ep.get("failure_type") in {
            "stop_not_completed", "decision_after_recovery_deadline", "unrecoverable_before_evidence", "evidence_availability_unmeasured"
        }
    return _bool(ep.get("unsafe_crossing_while_stop")) or ep.get("failure_type") in {
        "initial_stop_not_established", "stale_retention", "unsafe_continuation"
    }


def interaction_failure(ep: dict) -> bool:
    task = (ep.get("case") or {}).get("task")
    if task == "go_to_stop":
        return (_bool(ep.get("unsafe_crossing_while_stop")) or ep.get("failure_type") in {
            "stop_not_completed", "decision_after_recovery_deadline", "unrecoverable_before_evidence", "evidence_availability_unmeasured"
        })
    # For the release branch, isolate stale retention from the separate failure
    # to establish the initial stop state.
    return ep.get("failure_type") == "stale_retention"


def eligible_for_avoidable_rate(ep: dict) -> bool:
    if not _bool(ep.get("setup_valid")):
        return False
    case = ep.get("case") or {}
    if case.get("task") == "go_to_stop":
        return (_bool(ep.get("moving_before_transition_or_anchor"))
                and ep.get("recoverability_margin_at_evidence_m") is not None
                and float(ep.get("recoverability_margin_at_evidence_m")) > 0.0)
    return _bool(ep.get("stop_confirmed_before_release"))


def aggregate(episodes: list[dict]) -> list[dict]:
    groups = defaultdict(list)
    for ep in episodes:
        case = ep.get("case") or {}
        key = (
            str(ep.get("controller", "unknown")),
            str(case.get("task", "unknown")),
            bool(case.get("control_transition")),
            str(case.get("phase", "unknown")),
            str(case.get("gap_timing", "none")),
            str(case.get("evidence_mode", "frame_hold")),
        )
        groups[key].append(ep)
    rows = []
    for key, eps in sorted(groups.items()):
        controller, task, transition, phase, gap_timing, evidence_mode = key
        valid = [e for e in eps if _bool(e.get("setup_valid"))]
        eligible = [e for e in valid if eligible_for_avoidable_rate(e)]
        failures = [e for e in valid if outcome_failure(e)]
        unsafe = [e for e in valid if _bool(e.get("unsafe_crossing_while_stop"))]
        avoidable = [e for e in eligible if _bool(e.get("avoidable_failure"))]
        recoverable = [e for e in valid if _bool(e.get("physically_recoverable_at_evidence"))]
        collision_eps = [e for e in valid if float(e.get("collision_count", 0) or 0) > 0]
        response = [float(e["observable_brake_response_latency_s"]) for e in valid if isinstance(e.get("observable_brake_response_latency_s"), (int, float))]
        resume = [float(e["resume_latency_s"]) for e in valid if isinstance(e.get("resume_latency_s"), (int, float))]
        margins = [float(e["recoverability_margin_at_evidence_m"]) for e in valid if isinstance(e.get("recoverability_margin_at_evidence_m"), (int, float))]
        rows.append({
            "controller": controller,
            "task": task,
            "control_transition": int(transition),
            "phase": phase,
            "gap_timing": gap_timing,
            "evidence_mode": evidence_mode,
            "episodes": len(eps),
            "valid_episodes": len(valid),
            "eligible_episodes": len(eligible),
            "failure_rate_all": len(failures) / len(valid) if valid else None,
            "unsafe_crossing_rate": len(unsafe) / len(valid) if valid else None,
            "avoidable_failure_rate_eligible": len(avoidable) / len(eligible) if eligible else None,
            "recoverable_at_evidence_rate": len(recoverable) / len(valid) if valid else None,
            "collision_episode_rate": len(collision_eps) / len(valid) if valid else None,
            "median_brake_response_latency_s": _median(response),
            "median_resume_latency_s": _median(resume),
            "median_recoverability_margin_m": _median(margins),
            "setup_invalid_episodes": len(eps) - len(valid),
        })
    return rows


def interaction_estimates(episodes: list[dict]) -> list[dict]:
    """Additive three-factor interaction on episode failure rate for core cells.

    Factors: C=control transition, E=overlap evidence gap, M=late/long phase.
    This is descriptive unless every cell has enough valid repetitions.
    """
    groups = defaultdict(list)
    for ep in episodes:
        case = ep.get("case") or {}
        if case.get("gap_timing") not in {"none", "overlap"}:
            continue
        task = case.get("task")
        if task not in {"go_to_stop", "stop_to_go"}:
            continue
        phase = case.get("phase")
        late = phase in {"late", "long_wait"}
        key = (str(ep.get("controller", "unknown")), task,
               int(bool(case.get("control_transition"))),
               int(case.get("gap_timing") == "overlap"), int(late))
        if not _bool(ep.get("setup_valid")):
            continue
        if task == "go_to_stop":
            if ep.get("anchor_status") != "reached" or not _bool(ep.get("moving_before_transition_or_anchor")):
                continue
        else:
            if not _bool(ep.get("stop_confirmed_before_release")):
                continue
        groups[key].append(1.0 if interaction_failure(ep) else 0.0)
    results = []
    controllers = sorted({k[0] for k in groups})
    for controller in controllers:
        for task in ("go_to_stop", "stop_to_go"):
            means = {}
            counts = {}
            for c in (0, 1):
                for e in (0, 1):
                    for m in (0, 1):
                        vals = groups.get((controller, task, c, e, m), [])
                        means[(c, e, m)] = statistics.mean(vals) if vals else None
                        counts[(c, e, m)] = len(vals)
            def _interaction(p):
                return (p[(1, 1, 1)] - p[(1, 1, 0)] - p[(1, 0, 1)] - p[(0, 1, 1)]
                        + p[(1, 0, 0)] + p[(0, 1, 0)] + p[(0, 0, 1)] - p[(0, 0, 0)])
            if any(v is None for v in means.values()):
                interaction = None
                ci_low = ci_high = None
            else:
                interaction = _interaction(means)
                import random
                rng = random.Random(20261024)
                boot = []
                for _ in range(1000):
                    sampled_means = {}
                    for cell, vals in groups.items():
                        if cell[0] == controller and cell[1] == task:
                            sampled = [rng.choice(vals) for _ in range(len(vals))]
                            sampled_means[(cell[2], cell[3], cell[4])] = statistics.mean(sampled)
                    if len(sampled_means) == 8:
                        boot.append(_interaction(sampled_means))
                boot.sort()
                ci_low = boot[int(0.025 * (len(boot) - 1))] if boot else None
                ci_high = boot[int(0.975 * (len(boot) - 1))] if boot else None
            results.append({
                "controller": controller,
                "task": task,
                "interaction_CxExM_additive": interaction,
                "bootstrap_95ci_low": ci_low,
                "bootstrap_95ci_high": ci_high,
                "cell_counts": json.dumps({f"C{c}E{e}M{m}": counts[(c, e, m)] for c in (0,1) for e in (0,1) for m in (0,1)}),
                "interpretation": "Descriptive additive interaction; bootstrap CI is unreliable with very few repeats and does not replace matched-scene causal validity checks.",
            })
    return results


def write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fields = list(rows[0].keys())
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", default="/data0/senzeyu2/dataset/RAPID-AD")
    parser.add_argument("--run-tag", default=None, help="Restrict analysis to one run_batch output namespace")
    args = parser.parse_args()
    root = Path(args.data_root).expanduser().resolve()
    episodes = load_episodes(root, args.run_tag)
    if not episodes:
        search_root = (root / "runs" / args.run_tag) if args.run_tag else (root / "runs")
        print(f"No rapid_ad_metrics.json found under {search_root}")
        return 1
    agg = aggregate(episodes)
    interactions = interaction_estimates(episodes)
    analysis_dir = root / "analysis" / (args.run_tag or "all_runs")
    write_csv(analysis_dir / "cell_summary.csv", agg)
    write_csv(analysis_dir / "factorial_interactions.csv", interactions)
    (analysis_dir / "analysis_metadata.json").write_text(json.dumps({
        "episode_count": len(episodes),
        "cell_count": len(agg),
        "interaction_count": len(interactions),
        "run_tag": args.run_tag,
        "warning": "These are diagnostics, not paper claims. Inspect invalid cells, recoverability, and per-episode traces before interpreting rates.",
    }, indent=2), encoding="utf-8")
    print(f"Loaded episodes: {len(episodes)}")
    print(f"Cell summary: {analysis_dir / 'cell_summary.csv'}")
    print(f"Interaction summary: {analysis_dir / 'factorial_interactions.csv'}")
    print("Important: do not claim super-additivity from the point estimate alone; use repeated seeds and confidence intervals.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
