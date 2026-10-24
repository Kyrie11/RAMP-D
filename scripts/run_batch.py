#!/usr/bin/env python3
"""Run a RAPID-AD design matrix against one or more MARSHAL controllers."""
from __future__ import annotations

import argparse
import json
import os
from datetime import datetime
import re
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
from rapid_ad.design import build_design, write_design


def slug(text: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", text).strip("_") or "model"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--suite", choices=["smoke", "core", "all"], default="smoke")
    parser.add_argument("--seeds", default="0", help="Comma-separated repeat ids, e.g. 0,1,2")
    parser.add_argument("--controllers", nargs="+", default=["rapid_ad_oracle", "baseline", "pid"],
                        help="e.g. rapid_ad_oracle baseline tm pid mpc vlm")
    parser.add_argument("--model", default=None, help="Model id when controller=vlm")
    parser.add_argument("--controller-config-json", default=None)
    parser.add_argument("--marshal-root", default="/home/senzeyu2/code/MARSHAL")
    parser.add_argument("--data-root", default="/data0/senzeyu2/dataset/RAPID-AD")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=2000)
    parser.add_argument("--timeout-s", type=float, default=22.0)
    parser.add_argument("--query-period-s", type=float, default=0.5,
                        help="VLM query interval in simulation seconds; 0.5 is the diagnostic default")
    parser.add_argument("--max-queries", type=int, default=None)
    parser.add_argument("--max-cases", type=int, default=0, help="Optional cap for pilot runs; 0 means all cells")
    parser.add_argument("--run-tag", default=None, help="Output namespace; defaults to current timestamp")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if "vlm" in args.controllers and not args.model:
        parser.error("--model is required when controllers includes vlm")
    project_root = Path(__file__).resolve().parents[1]
    marshal_root = Path(args.marshal_root).expanduser().resolve()
    data_root = Path(args.data_root).expanduser().resolve()
    seeds = [int(x.strip()) for x in args.seeds.split(",") if x.strip()]
    cases = build_design(args.suite, seeds)
    if args.max_cases > 0:
        cases = cases[:args.max_cases]
    design_name = f"{args.suite}_seeds_{'_'.join(map(str, seeds))}"
    run_tag = args.run_tag or datetime.now().strftime("%Y%m%d_%H%M%S")
    design_dir = data_root / "design" / design_name
    write_design(cases, design_dir)
    run_root = data_root / "runs" / run_tag
    run_root.mkdir(parents=True, exist_ok=True)
    (run_root / "run_manifest.json").write_text(json.dumps({
        "run_tag": run_tag,
        "suite": args.suite,
        "seeds": seeds,
        "controllers": args.controllers,
        "model": args.model,
        "query_period_s": args.query_period_s,
        "case_count": len(cases),
        "case_ids": [c["case_id"] for c in cases],
        "marshal_root": str(marshal_root),
        "design_dir": str(design_dir),
    }, indent=2), encoding="utf-8")
    print(f"Design: {design_dir} ({len(cases)} cases)")
    print(f"Run tag: {run_tag}")

    runner = project_root / "scripts" / "run_episode.py"
    errors = []
    for controller in args.controllers:
        model_slug = slug(args.model) if controller == "vlm" and args.model else "default"
        out_root = data_root / "runs" / run_tag / f"{slug(controller)}_{model_slug}"
        for case in cases:
            case_path = design_dir / "cases" / f"{case['case_id']}.json"
            episode_id = case["case_id"]
            cmd = [
                sys.executable, str(runner),
                "--marshal-root", str(marshal_root),
                "--case-json", str(case_path),
                "--controller", controller,
                "--host", args.host,
                "--port", str(args.port),
                "--timeout-s", str(args.timeout_s),
                "--query-period-s", str(args.query_period_s),
                "--out-root", str(out_root),
                "--episode-id", episode_id,
            ]
            if args.model and controller == "vlm":
                cmd.extend(["--model", args.model])
            if args.max_queries is not None:
                cmd.extend(["--max-queries", str(args.max_queries)])
            if args.controller_config_json:
                cmd.extend(["--controller-config-json", str(Path(args.controller_config_json).resolve())])
            print("\n$ " + " ".join(cmd))
            if args.dry_run:
                continue
            child_env = os.environ.copy()
            child_env["MARSHAL_NO_STOP_EARLY_TERMINATION"] = "1"
            child_env["MARSHAL_TIMEOUT_S"] = str(float(args.timeout_s))
            completed = subprocess.run(cmd, cwd=str(marshal_root), env=child_env)
            if completed.returncode != 0:
                errors.append({"controller": controller, "case_id": case["case_id"], "returncode": completed.returncode})
                print(f"[WARN] episode failed: controller={controller} case={case['case_id']} rc={completed.returncode}")

    if not args.dry_run:
        err_path = data_root / "runs" / run_tag / f"{design_name}_errors.json"
        err_path.parent.mkdir(parents=True, exist_ok=True)
        err_path.write_text(json.dumps(errors, indent=2), encoding="utf-8")
        print(f"Batch finished. Run tag: {run_tag}; failed episodes: {len(errors)}; error log: {err_path}")
        print(f"Next: python {project_root / 'scripts' / 'analyze_results.py'} --data-root {data_root} --run-tag {run_tag}")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
