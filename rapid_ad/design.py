"""Generate matched RAPID-AD factorial scenarios without external dependencies.

Design v3: core is a full event-order factorial (2 tasks x 2 transition states
x 2 task-specific phases x 4 evidence-window timings = 32 cells/seed).
"""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

EARLY_MARGIN_TARGET_M = 5.0
LATE_MARGIN_TARGET_M = 1.5
SHORT_RELEASE_WAIT_S = 3.0
LONG_RELEASE_WAIT_S = 7.0
DEFAULT_GAP_SPAN_M = 2.5
DEFAULT_GAP_DURATION_S = 1.0
DEFAULT_SEEDS = [0]
GAP_LEVELS = ["none", "pre", "overlap", "post"]


def _case(task: str, transition: bool, phase: str, gap_timing: str, seed: int) -> dict[str, Any]:
    if gap_timing not in GAP_LEVELS:
        raise ValueError(f"Unknown gap timing: {gap_timing}")
    safety_task = task == "go_to_stop"
    if safety_task:
        margin_target = EARLY_MARGIN_TARGET_M if phase == "early" else LATE_MARGIN_TARGET_M
        phase_key = phase
        release_wait = None
    else:
        margin_target = None
        phase_key = phase
        release_wait = SHORT_RELEASE_WAIT_S if phase == "short_wait" else LONG_RELEASE_WAIT_S

    gap = gap_timing != "none"
    case: dict[str, Any] = {
        "design_version": 3,
        "task": task,
        "control_transition": bool(transition),
        "evidence_gap": gap,
        "gap_timing": gap_timing,
        "phase": phase_key,
        # Primary GO->STOP phase is defined by a target estimated stopping margin,
        # not an absolute distance that changes meaning with speed or vehicle size.
        "phase_margin_target_m": margin_target,
        "transition_distance_m": None,
        # STOP->GO is a liveness/release task; its phase is a matched wait duration.
        "release_wait_after_start_s": release_wait,
        # All evidence interventions are requested in simulation seconds.
        # For GO->STOP, pre/overlap start is predicted from margin slope and
        # validated from actual timestamps after the episode.
        "gap_duration_s": DEFAULT_GAP_DURATION_S,
        "gap_anchor": "margin_threshold_time" if safety_task else "simulation_time",
        "seed": int(seed),
    }
    task_code = "g2s" if safety_task else "s2g"
    trans_code = "chg" if transition else "static"
    phase_code = phase if safety_task else ("wshort" if phase == "short_wait" else "wlong")
    gap_code = {"none": "nogap", "pre": "pre", "overlap": "overlap", "post": "post"}[gap_timing]
    case["case_id"] = f"{task_code}_{trans_code}_{phase_code}_{gap_code}_s{seed:02d}"
    return case


def build_design(suite: str = "core", seeds: list[int] | None = None) -> list[dict[str, Any]]:
    """Build matched scenarios.

    smoke: compact integration subset, includes all three event-window types.
    core/all: full 32-cell factorial per seed.

    Factors within each task:
      C: no transition vs actual control transition (2)
      P: early/late stopping-margin phase or short/long release wait (2)
      G: no gap/pre/overlap/post evidence window (4)
    """
    seeds = list(DEFAULT_SEEDS if seeds is None else seeds)
    if suite not in {"smoke", "core", "all"}:
        raise ValueError(f"Unknown suite: {suite}")
    tasks = {
        "go_to_stop": ["early", "late"],
        "stop_to_go": ["short_wait", "long_wait"],
    }
    cells: list[dict[str, Any]] = []
    for seed in seeds:
        for task, phases in tasks.items():
            for transition in (False, True):
                for phase in phases:
                    for gap_timing in GAP_LEVELS:
                        cells.append(_case(task, transition, phase, gap_timing, seed))

    if suite == "smoke":
        # Order smoke so --max-cases 1 tests a real GO->STOP transition first,
        # rather than a static placebo. The suite remains an integration subset,
        # not a balanced statistical design.
        smoke_order = [
            ("go_to_stop", True, "early", "none"),
            ("go_to_stop", True, "late", "none"),
            ("go_to_stop", True, "late", "pre"),
            ("go_to_stop", True, "late", "overlap"),
            ("go_to_stop", True, "late", "post"),
            ("go_to_stop", False, "early", "none"),
            ("go_to_stop", False, "late", "overlap"),
            ("stop_to_go", True, "short_wait", "none"),
            ("stop_to_go", True, "short_wait", "pre"),
            ("stop_to_go", True, "short_wait", "overlap"),
            ("stop_to_go", True, "short_wait", "post"),
            ("stop_to_go", True, "long_wait", "overlap"),
            ("stop_to_go", False, "short_wait", "none"),
            ("stop_to_go", False, "short_wait", "overlap"),
        ]
        by_key = {(c["task"], c["control_transition"], c["phase"], c["gap_timing"]): c for c in cells}
        cells = [by_key[key] for key in smoke_order if key in by_key]
    return cells


def write_design(cases: list[dict[str, Any]], out_dir: str | Path) -> tuple[Path, Path]:
    out_dir = Path(out_dir)
    cases_dir = out_dir / "cases"
    cases_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "manifest.json"
    csv_path = out_dir / "manifest.csv"
    json_path.write_text(json.dumps(cases, indent=2), encoding="utf-8")
    fields = [
        "case_id", "design_version", "task", "control_transition", "evidence_gap",
        "gap_timing", "phase", "phase_margin_target_m", "transition_distance_m",
        "release_wait_after_start_s", "gap_anchor", "gap_duration_s", "seed",
    ]
    with csv_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        for case in cases:
            writer.writerow({k: case.get(k) for k in fields})
            (cases_dir / f"{case['case_id']}.json").write_text(json.dumps(case, indent=2), encoding="utf-8")
    return json_path, csv_path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--suite", choices=["smoke", "core", "all"], default="core")
    parser.add_argument("--seeds", default="0", help="Comma-separated repeat ids, e.g. 0,1,2")
    parser.add_argument("--out", required=True, help="Output design directory")
    args = parser.parse_args()
    seeds = [int(x.strip()) for x in args.seeds.split(",") if x.strip()]
    cases = build_design(args.suite, seeds)
    jpath, cpath = write_design(cases, args.out)
    print(f"Generated {len(cases)} cases")
    print(f"JSON: {jpath}")
    print(f"CSV:  {cpath}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
