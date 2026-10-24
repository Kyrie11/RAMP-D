"""Generate matched RAPID-AD factorial scenarios without external dependencies."""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

EARLY_DISTANCE_M = 12.0
LATE_DISTANCE_M = 9.0
SHORT_RELEASE_WAIT_S = 3.0
LONG_RELEASE_WAIT_S = 7.0
DEFAULT_SEEDS = [0]


def _case(task: str, transition: bool, phase: str, gap_timing: str, seed: int) -> dict[str, Any]:
    safety = task == "go_to_stop"
    if safety:
        phase_distance = EARLY_DISTANCE_M if phase == "early" else LATE_DISTANCE_M
        phase_key = phase
        release_wait = None
    else:
        phase_distance = None
        phase_key = phase
        release_wait = SHORT_RELEASE_WAIT_S if phase == "short_wait" else LONG_RELEASE_WAIT_S
    gap = gap_timing != "none"
    case = {
        "task": task,
        "control_transition": bool(transition),
        "evidence_gap": bool(gap),
        "gap_timing": gap_timing,
        "phase": phase_key,
        "transition_distance_m": phase_distance,
        "release_wait_after_start_s": release_wait,
        "gap_span_m": 2.5,
        "gap_duration_s": 1.0,
        "seed": int(seed),
    }
    task_code = "g2s" if safety else "s2g"
    trans_code = "chg" if transition else "static"
    phase_code = phase if safety else ("wshort" if phase == "short_wait" else "wlong")
    gap_code = {"none": "nogap", "pre": "pre", "overlap": "overlap", "post": "post"}[gap_timing]
    case["case_id"] = f"{task_code}_{trans_code}_{phase_code}_{gap_code}_s{seed:02d}"
    return case


def build_design(suite: str = "core", seeds: list[int] | None = None) -> list[dict[str, Any]]:
    """Build the scenario matrix.

    core: 2 directions x 2 transition states x 2 phases x {no-gap, overlap-gap} = 16 cells/seed.
    all:  2 directions x 2 transition states x 2 phases x {none, pre, overlap, post} = 32 cells/seed.
    smoke: a six-case integration subset; not for statistical claims.
    """
    seeds = seeds or DEFAULT_SEEDS
    if suite not in {"smoke", "core", "all"}:
        raise ValueError(f"Unknown suite: {suite}")
    tasks = {
        "go_to_stop": ["early", "late"],
        "stop_to_go": ["short_wait", "long_wait"],
    }
    gap_levels = ["none", "overlap"] if suite == "core" else ["none", "pre", "overlap", "post"]
    cells: list[dict[str, Any]] = []
    for seed in seeds:
        for task, phases in tasks.items():
            for transition in (False, True):
                for phase in phases:
                    for gap_timing in gap_levels:
                        cells.append(_case(task, transition, phase, gap_timing, seed))
    if suite == "smoke":
        wanted = {
            ("go_to_stop", False, "early", "none"),
            ("go_to_stop", True, "late", "none"),
            ("go_to_stop", True, "late", "overlap"),
            ("stop_to_go", False, "short_wait", "overlap"),
            ("stop_to_go", True, "short_wait", "none"),
            ("stop_to_go", True, "long_wait", "overlap"),
        }
        cells = [c for c in cells if (c["task"], c["control_transition"], c["phase"], c["gap_timing"]) in wanted]
    return cells


def write_design(cases: list[dict[str, Any]], out_dir: str | Path) -> tuple[Path, Path]:
    out_dir = Path(out_dir)
    cases_dir = out_dir / "cases"
    cases_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "manifest.json"
    csv_path = out_dir / "manifest.csv"
    json_path.write_text(json.dumps(cases, indent=2), encoding="utf-8")
    fields = [
        "case_id", "task", "control_transition", "evidence_gap", "gap_timing",
        "phase", "transition_distance_m", "release_wait_after_start_s",
        "gap_span_m", "gap_duration_s", "seed",
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
    parser.add_argument("--seeds", default="0", help="Comma-separated repeat/seed ids, e.g. 0,1,2")
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
