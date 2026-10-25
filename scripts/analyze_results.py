#!/usr/bin/env python3
"""Aggregate RAPID-AD v3 metrics and estimate paired, seed-blocked interactions."""
from __future__ import annotations

import argparse
import csv
import json
import random
import statistics
from collections import defaultdict
from pathlib import Path
from typing import Any


GO_TO_STOP_FAILURES = {
    "unsafe_continuation", "stop_not_completed", "decision_after_recovery_deadline",
    "unrecoverable_before_evidence", "evidence_availability_unmeasured",
}
STOP_TO_GO_FAILURES = {"unsafe_continuation", "stale_retention", "evidence_availability_unmeasured", "initial_stop_not_established"}


def _median(values: list[float]) -> float | None:
    return statistics.median(values) if values else None


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def load_episodes(data_root: Path, run_tag: str | None = None) -> list[dict]:
    episodes: list[dict] = []
    search_root = (data_root / "runs" / run_tag) if run_tag else (data_root / "runs")
    for path in search_root.glob("**/rapid_ad_metrics.json"):
        try:
            obj = json.loads(path.read_text(encoding="utf-8"))
            obj["_path"] = str(path)
            obj["_run_tag"] = path.parts[-4] if len(path.parts) >= 4 else "unknown"
            episodes.append(obj)
        except Exception as exc:
            print(f"[WARN] cannot read {path}: {exc}")
    return episodes


def is_setup_valid(ep: dict) -> bool:
    return bool(ep.get("setup_valid", False))


def is_exposure_valid(ep: dict) -> bool:
    if "exposure_valid" in ep:
        return bool(ep.get("exposure_valid"))
    # Backward-compatible v1 fallback: anchor + setup; not sufficient for final claims.
    return is_setup_valid(ep) and ep.get("anchor_status") == "reached"


def is_causal_valid(ep: dict) -> bool:
    base = bool(ep.get("valid_for_causal_analysis")) if "valid_for_causal_analysis" in ep else is_exposure_valid(ep)
    if not base:
        return False
    if ep.get("_require_visual_audit") and bool(ep.get("transition_expected")):
        return bool(ep.get("_visual_audit_pass", False))
    return True


def overall_failure(ep: dict) -> bool:
    case = ep.get("case") or {}
    task = case.get("task")
    ft = ep.get("failure_type")
    if task == "go_to_stop":
        return bool(ep.get("unsafe_crossing_while_stop")) or ft in GO_TO_STOP_FAILURES
    if task == "stop_to_go":
        return bool(ep.get("unsafe_crossing_while_stop")) or ft in STOP_TO_GO_FAILURES
    return False


def estimated_avoidable_failure(ep: dict) -> bool:
    if "avoidable_failure_estimated" in ep:
        return bool(ep.get("avoidable_failure_estimated"))
    value = ep.get("avoidable_failure")
    return bool(value) if value is not None else False


def aggregate(episodes: list[dict]) -> list[dict]:
    groups: dict[tuple, list[dict]] = defaultdict(list)
    for ep in episodes:
        case = ep.get("case") or {}
        key = (
            str(ep.get("controller", "unknown")), str(case.get("task", "unknown")),
            bool(case.get("control_transition")), str(case.get("phase", "unknown")),
            str(case.get("gap_timing", "none")), str(case.get("evidence_mode", "frame_hold")),
        )
        groups[key].append(ep)
    rows: list[dict] = []
    for key, eps in sorted(groups.items()):
        controller, task, transition, phase, gap_timing, evidence_mode = key
        setup = [e for e in eps if is_setup_valid(e)]
        exposed = [e for e in eps if is_exposure_valid(e)]
        safety_valid = [e for e in eps if bool(e.get("valid_for_safety_analysis", is_causal_valid(e)))]
        causal_valid = [e for e in eps if is_causal_valid(e)]
        valid = safety_valid
        failures = [e for e in valid if overall_failure(e)]
        unsafe = [e for e in valid if bool(e.get("unsafe_crossing_while_stop"))]
        nonrecoverable = [e for e in valid if e.get("failure_type") == "unrecoverable_before_evidence"]
        avoidable = [e for e in causal_valid if estimated_avoidable_failure(e)]
        resume_eps = [e for e in valid if transition and task == "stop_to_go" and e.get("resume_latency_s") is not None]
        resume = [float(e["resume_latency_s"]) for e in resume_eps if _is_number(e.get("resume_latency_s"))]
        margins = [float(e["recoverability_margin_at_evidence_m"]) for e in valid if _is_number(e.get("recoverability_margin_at_evidence_m"))]
        response = [float(e["command_response_latency_s"]) for e in valid if _is_number(e.get("command_response_latency_s"))]
        action_change = [float(e["decision_action_change_latency_from_transition_s"]) for e in causal_valid if _is_number(e.get("decision_action_change_latency_from_transition_s"))]
        speed_drop = [float(e["speed_drop_latency_from_evidence_s"]) for e in causal_valid if _is_number(e.get("speed_drop_latency_from_evidence_s"))]
        speed_increase = [float(e["speed_increase_latency_from_evidence_s"]) for e in causal_valid if _is_number(e.get("speed_increase_latency_from_evidence_s"))]
        collisions = [e for e in valid if float(e.get("collision_count", 0) or 0) > 0]
        rows.append({
            "controller": controller, "task": task, "control_transition": int(transition),
            "phase": phase, "gap_timing": gap_timing, "evidence_mode": evidence_mode,
            "episodes": len(eps), "setup_valid_episodes": len(setup),
            "exposure_valid_episodes": len(exposed), "safety_valid_episodes": len(safety_valid),
            "causal_valid_episodes": len(causal_valid),
            "invalid_or_unexposed_episodes": len(eps) - len(exposed),
            "overall_failure_rate_safety_valid": len(failures) / len(valid) if valid else None,
            "unsafe_crossing_rate_safety_valid": len(unsafe) / len(valid) if valid else None,
            "estimated_avoidable_failure_rate_causal_valid": len(avoidable) / len(causal_valid) if causal_valid else None,
            "unrecoverable_before_evidence_rate_safety_valid": len(nonrecoverable) / len(valid) if valid else None,
            "collision_episode_rate_safety_valid": len(collisions) / len(valid) if valid else None,
            "median_command_response_latency_s": _median(response),
            "median_decision_action_change_latency_s": _median(action_change),
            "median_speed_drop_latency_from_evidence_s": _median(speed_drop),
            "median_speed_increase_latency_from_evidence_s": _median(speed_increase),
            "median_resume_latency_s": _median(resume),
            "median_margin_at_evidence_m": _median(margins),
            "recoverability_calibrated_all": bool(valid) and all(bool(e.get("recoverability_estimate_calibrated")) for e in valid),
        })
    return rows


def _cell_outcome(ep: dict, outcome: str) -> float:
    if outcome == "overall_failure":
        return 1.0 if overall_failure(ep) else 0.0
    if outcome == "estimated_avoidable_failure":
        return 1.0 if estimated_avoidable_failure(ep) else 0.0
    raise ValueError(outcome)


def _interaction(p: dict[tuple[int, int, int], float]) -> float:
    # C=transition, E=target evidence-window present (vs none), P=late phase.
    return (p[(1, 1, 1)] - p[(1, 1, 0)] - p[(1, 0, 1)] - p[(0, 1, 1)]
            + p[(1, 0, 0)] + p[(0, 1, 0)] + p[(0, 0, 1)] - p[(0, 0, 0)])


def interaction_estimates(episodes: list[dict], bootstrap_samples: int = 2000) -> list[dict]:
    """Estimate paired additive C x evidence-window x phase interactions.

    For each timing type (pre/overlap/post), compare that gap with the no-gap
    control. Each seed/run block contributes only when all 8 matched cells are
    valid. This avoids treating missing or invalid CARLA episodes as successes.
    """
    results: list[dict] = []
    tasks = ("go_to_stop", "stop_to_go")
    for controller in sorted({str(e.get("controller", "unknown")) for e in episodes}):
        for task in tasks:
            for gap_type in ("pre", "overlap", "post"):
                for outcome in ("overall_failure", "estimated_avoidable_failure"):
                    # One cell per (run, seed, C, E, phase). Duplicate runs/cells are not silently averaged.
                    cell_map: dict[tuple, dict[tuple[int, int, int], dict]] = {}
                    duplicate_keys: set[tuple] = set()
                    for ep in episodes:
                        # Do not mix v1/v2 runs with v3: evidence timing and
                        # validity semantics changed in this version.
                        if int(ep.get("schema_version", 1)) != 3:
                            continue
                        if str(ep.get("controller", "unknown")) != controller:
                            continue
                        case = ep.get("case") or {}
                        if case.get("task") != task or case.get("gap_timing") not in {"none", gap_type}:
                            continue
                        if not is_causal_valid(ep):
                            continue
                        phase = case.get("phase")
                        late = int(phase in {"late", "long_wait"})
                        c = int(bool(case.get("control_transition")))
                        e = int(case.get("gap_timing") == gap_type)
                        block = (str(ep.get("_run_tag", "unknown")), int(case.get("seed", -1)))
                        cell = (c, e, late)
                        slot = cell_map.setdefault(block, {})
                        if cell in slot:
                            duplicate_keys.add((block, cell))
                        else:
                            slot[cell] = ep
                    block_interactions: list[tuple[tuple[str, int], float]] = []
                    block_counts = 0
                    for block, cells in cell_map.items():
                        if len(cells) != 8 or any((block, cell) in duplicate_keys for cell in cells):
                            continue
                        vals = {cell: _cell_outcome(ep, outcome) for cell, ep in cells.items()}
                        block_interactions.append((block, _interaction(vals)))
                        block_counts += 1
                    values = [v for _, v in block_interactions]
                    estimate = statistics.mean(values) if values else None
                    ci_low = ci_high = None
                    if len(values) >= 2:
                        rng = random.Random(20261025)
                        boot = [statistics.mean(rng.choices(values, k=len(values))) for _ in range(bootstrap_samples)]
                        boot.sort()
                        ci_low = boot[int(0.025 * (len(boot) - 1))]
                        ci_high = boot[int(0.975 * (len(boot) - 1))]
                    results.append({
                        "controller": controller, "task": task, "gap_timing_vs_none": gap_type,
                        "outcome": outcome, "paired_seed_blocks": block_counts,
                        "interaction_CxGxPhase_additive": estimate,
                        "bootstrap_95ci_low": ci_low, "bootstrap_95ci_high": ci_high,
                        "underpowered_warning": block_counts < 5,
                        "cell_counts_by_block": json.dumps({str(k): len(v) for k, v in cell_map.items()}, sort_keys=True),
                        "interpretation": "Descriptive paired additive interaction. Require >=5 independent matched blocks, valid exposure, physical recoverability calibration, and a prespecified outcome before making a causal claim.",
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


def load_visual_audit(path: Path) -> dict[tuple[str, str, str], bool]:
    mapping: dict[tuple[str, str, str], bool] = {}
    with path.open("r", newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            key = (str(row.get("run_tag", "")), str(row.get("controller", "")), str(row.get("case_id", "")))
            value = str(row.get("audit_pass", "")).strip().lower()
            if key[0] and key[1] and key[2]:
                mapping[key] = value in {"yes", "y", "true", "1", "pass"}
    return mapping


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--data-root", default="/data0/senzeyu2/dataset/RAPID-AD")
    ap.add_argument("--run-tag", default=None)
    ap.add_argument("--visual-audit-csv", default=None, help="CSV created by make_visual_audit_manifest.py with manually filled audit_pass column")
    ap.add_argument("--require-visual-audit", action="store_true", help="Exclude dynamic-transition episodes until audit_pass=yes; recommended for final RQ2 analysis")
    args = ap.parse_args()
    if args.require_visual_audit and not args.visual_audit_csv:
        ap.error("--require-visual-audit requires --visual-audit-csv")
    root = Path(args.data_root).expanduser().resolve()
    episodes = load_episodes(root, args.run_tag)
    audit_map = load_visual_audit(Path(args.visual_audit_csv).expanduser().resolve()) if args.visual_audit_csv else {}
    for ep in episodes:
        ep["_require_visual_audit"] = bool(args.require_visual_audit)
        case = ep.get("case") or {}
        key = (str(ep.get("_run_tag", "")), str(ep.get("controller", "")), str(case.get("case_id", "")))
        ep["_visual_audit_pass"] = audit_map.get(key, False)
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
        "schema_versions": sorted({e.get("schema_version", 1) for e in episodes}),
        "warning": "Only schema-v3 episodes enter factorial interactions. Inspect setup/exposure validity and failure taxonomy. All effects remain provisional until transition/mask diagnostic frames are visually audited. Pilot estimates do not establish causal effects.",
        "visual_audit_pending_episodes": sum(
            1 for e in episodes if e.get("visual_audit_status") == "pending_manual_audit"
            and (not args.require_visual_audit or not e.get("_visual_audit_pass", False))
        ),
        "visual_audit_required": bool(args.require_visual_audit),
        "visual_audit_csv": str(Path(args.visual_audit_csv).expanduser().resolve()) if args.visual_audit_csv else None,
        "audited_dynamic_episodes_passed": sum(1 for e in episodes if e.get("transition_expected") and e.get("_visual_audit_pass")),
    }, indent=2), encoding="utf-8")
    print(f"Loaded episodes: {len(episodes)}")
    print(f"Cell summary: {analysis_dir / 'cell_summary.csv'}")
    print(f"Factorial interactions: {analysis_dir / 'factorial_interactions.csv'}")
    print("Important: only complete matched seed blocks enter interaction estimates; report invalid/unexposed cases separately.")
    if args.require_visual_audit:
        print("Visual audit is required for dynamic transitions; missing/failed audit rows are excluded from causal interactions.")
    else:
        print("WARNING: interaction estimates are provisional until diagnostic frames are visually audited; rerun with --require-visual-audit for final analysis.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
