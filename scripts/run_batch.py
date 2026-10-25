#!/usr/bin/env python3
"""Fail-fast runner for RAPID-AD matched CARLA episodes.

Every child stdout/stderr is saved. The CARLA RPC endpoint is checked before
and after each episode; a broken simulator stops the batch instead of turning
subsequent episodes into misleading spawn/time-out failures.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
from rapid_ad.design import build_design, write_design  # noqa: E402


def slug(text: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", text).strip("_") or "model"


def tail(path: Path, n: int = 35) -> str:
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        return "\n".join(lines[-n:])
    except Exception:
        return ""


def health_check(project_root: Path, host: str, port: int, timeout: float, env: dict, out_path: Path) -> bool:
    checker = project_root / "scripts" / "check_carla.py"
    with out_path.open("w", encoding="utf-8") as fh:
        try:
            proc = subprocess.run(
                [sys.executable, str(checker), "--host", host, "--port", str(port), "--timeout", str(timeout)],
                env=env, stdout=fh, stderr=subprocess.STDOUT, text=True,
                timeout=max(10.0, timeout + 4.0),
            )
            return proc.returncode == 0
        except subprocess.TimeoutExpired:
            fh.write("\n[HEALTH CHECK TIMEOUT]\n")
            return False



def spawn_check(project_root: Path, host: str, port: int, timeout: float, env: dict, out_path: Path, base_config: Path) -> bool:
    checker = project_root / "scripts" / "check_spawn.py"
    with out_path.open("w", encoding="utf-8") as fh:
        try:
            proc = subprocess.run(
                [sys.executable, str(checker), "--base-config", str(base_config), "--host", host, "--port", str(port), "--timeout", str(timeout)],
                env=env, stdout=fh, stderr=subprocess.STDOUT, text=True,
                timeout=max(10.0, timeout + 3.0),
            )
            return proc.returncode == 0
        except subprocess.TimeoutExpired:
            fh.write("\n[SPAWN CHECK TIMEOUT]\n")
            return False

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--suite", choices=["smoke", "core", "all"], default="smoke")
    parser.add_argument("--seeds", default="0", help="Comma-separated matched seed ids, e.g. 0,1,2")
    parser.add_argument("--controllers", nargs="+", default=["rapid_ad_oracle"],
                        help="Run separately by controller during debugging; e.g. rapid_ad_oracle vlm")
    parser.add_argument("--model", default=None, help="Model id/path when controller=vlm")
    parser.add_argument("--controller-config-json", default=None)
    parser.add_argument("--carla-root", default="/data0/senzeyu2/dataset/CRADrive/CARLA0.9.15")
    parser.add_argument("--marshal-root", default="/home/senzeyu2/code/MARSHAL")
    parser.add_argument("--base-config", default=str(PROJECT_ROOT / "configs" / "base_episode.json"))
    parser.add_argument("--allow-uncalibrated", action="store_true", help="Exploratory only: allow core/all without vehicle-specific braking calibration; results cannot support recoverability claims")
    parser.add_argument("--data-root", default="/data0/senzeyu2/dataset/RAPID-AD")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=2000)
    parser.add_argument("--timeout-s", type=float, default=12.0, help="Simulation-time episode horizon")
    parser.add_argument("--rpc-timeout-s", type=float, default=8.0)
    parser.add_argument("--wall-timeout-s", type=float, default=180.0, help="Hard wall-clock timeout per episode")
    parser.add_argument("--query-period-s", type=float, default=0.5)
    parser.add_argument("--max-queries", type=int, default=None)
    parser.add_argument("--max-cases", type=int, default=0, help="Limit the selected design to the first N cases")
    parser.add_argument("--start-index", type=int, default=0, help="Zero-based case index for resuming a design")
    parser.add_argument("--run-tag", default=None)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--continue-on-error", action="store_true",
                        help="Continue only when the CARLA server remains healthy; not recommended for debugging")
    parser.add_argument("--skip-health-check", action="store_true", help="Debug only; not recommended")
    parser.add_argument("--actor-count-tolerance", type=int, default=2,
                        help="Allowed actor-count drift after an episode before flagging possible cleanup leaks")
    args = parser.parse_args()

    if "vlm" in args.controllers and not args.model:
        parser.error("--model is required when controllers includes vlm")
    if args.timeout_s <= 0 or args.wall_timeout_s <= 0 or args.rpc_timeout_s <= 0:
        parser.error("timeouts must be positive")

    project_root = Path(__file__).resolve().parents[1]
    marshal_root = Path(args.marshal_root).expanduser().resolve()
    carla_root = Path(args.carla_root).expanduser().resolve()
    data_root = Path(args.data_root).expanduser().resolve()
    base_config_path = Path(args.base_config).expanduser().resolve()
    if not base_config_path.is_file():
        parser.error(f"base config not found: {base_config_path}")
    base_config = json.loads(base_config_path.read_text(encoding="utf-8"))
    calibrated = bool((base_config.get("scene") or {}).get("recoverability_calibrated", False))
    if args.suite in {"core", "all"} and not calibrated and not args.allow_uncalibrated:
        parser.error("core/all requires scene.recoverability_calibrated=true in --base-config after running calibrate_braking.py; use --allow-uncalibrated only for explicitly exploratory runs")
    seeds = [int(x.strip()) for x in args.seeds.split(",") if x.strip()]
    cases = build_design(args.suite, seeds)
    if args.start_index < 0 or args.start_index >= max(1, len(cases)):
        parser.error("--start-index is outside the design")
    cases = cases[args.start_index:]
    if args.max_cases > 0:
        cases = cases[:args.max_cases]
    design_name = f"{args.suite}_v3_seeds_{'_'.join(map(str, seeds))}"
    run_tag = args.run_tag or datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    design_dir = data_root / "design" / design_name
    write_design(build_design(args.suite, seeds), design_dir)
    run_root = data_root / "runs" / run_tag
    run_root.mkdir(parents=True, exist_ok=False)
    manifest = {
        "run_tag": run_tag,
        "design_version": 3,
        "suite": args.suite,
        "seeds": seeds,
        "controllers": args.controllers,
        "model": args.model,
        "query_period_s": args.query_period_s,
        "simulation_timeout_s": args.timeout_s,
        "wall_timeout_s": args.wall_timeout_s,
        "case_count_selected": len(cases),
        "case_count_full_design": len(build_design(args.suite, seeds)),
        "start_index": args.start_index,
        "case_ids": [c["case_id"] for c in cases],
        "carla_root": str(carla_root),
        "marshal_root": str(marshal_root),
        "base_config": str(base_config_path),
        "recoverability_calibrated": calibrated,
        "allow_uncalibrated": bool(args.allow_uncalibrated),
        "design_dir": str(design_dir),
        "health_check_enabled": not args.skip_health_check,
    }
    (run_root / "run_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"Design: {design_dir} ({manifest['case_count_full_design']} full-design cases)")
    print(f"Selected cases: {len(cases)}; run tag: {run_tag}")

    runner = project_root / "scripts" / "run_episode.py"
    child_env = os.environ.copy()
    child_env["CARLA_ROOT"] = str(carla_root)
    child_env["MARSHAL_NO_STOP_EARLY_TERMINATION"] = "1"
    child_env["MARSHAL_TIMEOUT_S"] = str(float(args.timeout_s))
    old_pp = child_env.get("PYTHONPATH", "")
    carla_api_root = carla_root / "PythonAPI" / "carla"
    import_paths = [str(project_root), str(marshal_root), str(carla_api_root)]
    # CARLA 0.9.15 often ships an .egg rather than an installed wheel. Add the
    # matching egg explicitly so the client API and agents path come from the
    # configured tree, not an accidental older site-packages install.
    import_paths.extend(sorted(str(p) for p in (carla_api_root / "dist").glob("*0.9.15*.egg")))
    import_paths.extend([x for x in old_pp.split(os.pathsep) if x])
    child_env["PYTHONPATH"] = os.pathsep.join(dict.fromkeys(import_paths))

    errors: list[dict] = []
    baseline_actor_count = None
    if not args.dry_run and not args.skip_health_check:
        pre_health = run_root / "health_before.txt"
        if not health_check(project_root, args.host, args.port, args.rpc_timeout_s, child_env, pre_health):
            print(f"[FATAL] CARLA health check failed before the batch. See {pre_health}")
            (run_root / "batch_status.json").write_text(json.dumps({"status": "aborted_preflight", "errors": []}, indent=2), encoding="utf-8")
            return 2
        try:
            baseline_actor_count = json.loads(pre_health.read_text(encoding="utf-8")).get("actor_count")
        except Exception:
            baseline_actor_count = None
        pre_spawn = run_root / "spawn_before.txt"
        if not spawn_check(project_root, args.host, args.port, args.rpc_timeout_s, child_env, pre_spawn, base_config_path):
            print(f"[FATAL] configured ego spawn station is occupied or invalid. See {pre_spawn}")
            (run_root / "batch_status.json").write_text(json.dumps({"status": "aborted_spawn_preflight", "errors": []}, indent=2), encoding="utf-8")
            return 2

    abort_reason = None
    for controller in args.controllers:
        model_slug = slug(args.model) if controller == "vlm" and args.model else "default"
        out_root = run_root / f"{slug(controller)}_{model_slug}"
        out_root.mkdir(parents=True, exist_ok=True)
        for case in cases:
            case_path = design_dir / "cases" / f"{case['case_id']}.json"
            episode_dir = out_root / case["case_id"]
            episode_dir.mkdir(parents=True, exist_ok=True)
            cmd = [
                sys.executable, str(runner),
                "--marshal-root", str(marshal_root),
                "--case-json", str(case_path),
                "--base-config", str(base_config_path),
                "--controller", controller,
                "--host", args.host,
                "--port", str(args.port),
                "--timeout-s", str(args.timeout_s),
                "--rpc-timeout", str(args.rpc_timeout_s),
                "--query-period-s", str(args.query_period_s),
                "--out-root", str(out_root),
                "--episode-id", case["case_id"],
            ]
            if args.model and controller == "vlm":
                cmd.extend(["--model", args.model])
            if args.max_queries is not None:
                cmd.extend(["--max-queries", str(args.max_queries)])
            if args.controller_config_json:
                cmd.extend(["--controller-config-json", str(Path(args.controller_config_json).resolve())])
            print(f"\n[{controller}] {case['case_id']}")
            if args.dry_run:
                print("$ " + " ".join(cmd))
                continue

            stdout_path = episode_dir / "episode_stdout.log"
            stderr_path = episode_dir / "episode_stderr.log"
            returncode = None
            wall_timeout = False
            try:
                with stdout_path.open("w", encoding="utf-8") as out_f, stderr_path.open("w", encoding="utf-8") as err_f:
                    completed = subprocess.run(
                        cmd, cwd=str(marshal_root), env=child_env,
                        stdout=out_f, stderr=err_f, text=True,
                        timeout=args.wall_timeout_s,
                    )
                    returncode = completed.returncode
            except subprocess.TimeoutExpired:
                wall_timeout = True
                returncode = 124
                stderr_path.write_text(stderr_path.read_text(encoding="utf-8", errors="replace") + "\n[WALL TIMEOUT: child killed by runner]\n", encoding="utf-8")

            metrics_path = episode_dir / "rapid_ad_metrics.json"
            if returncode == 0 and not metrics_path.exists():
                returncode = 5
            case_status = {
                "controller": controller, "case_id": case["case_id"],
                "returncode": returncode, "wall_timeout": wall_timeout,
                "metrics_file_exists": metrics_path.exists(),
                "stdout_log": str(stdout_path), "stderr_log": str(stderr_path),
            }
            (episode_dir / "parent_status.json").write_text(json.dumps(case_status, indent=2), encoding="utf-8")
            if returncode != 0:
                errors.append(case_status)
                print(f"[FAIL] returncode={returncode}; stdout/stderr saved under {episode_dir}")
                print("--- stderr tail ---")
                print(tail(stderr_path, 25))
                print("--- stdout tail ---")
                print(tail(stdout_path, 15))

            if not args.skip_health_check:
                health_path = episode_dir / "health_after.txt"
                healthy = health_check(project_root, args.host, args.port, args.rpc_timeout_s, child_env, health_path)
                if not healthy:
                    abort_reason = f"CARLA health check failed after {case['case_id']}"
                    print(f"[FATAL] {abort_reason}; see {health_path}")
                    break
                if baseline_actor_count is not None:
                    try:
                        after_actor_count = json.loads(health_path.read_text(encoding="utf-8")).get("actor_count")
                        if after_actor_count is not None and abs(int(after_actor_count) - int(baseline_actor_count)) > args.actor_count_tolerance:
                            abort_reason = (f"CARLA actor-count drift after {case['case_id']}: "
                                            f"before={baseline_actor_count}, after={after_actor_count}; possible actor cleanup leak")
                            print(f"[FATAL] {abort_reason}; inspect server and episode actors before continuing")
                            break
                    except Exception as exc:
                        abort_reason = f"Could not verify actor cleanup after {case['case_id']}: {exc!r}"
                        print(f"[FATAL] {abort_reason}")
                        break
                spawn_path = episode_dir / "spawn_after.txt"
                if not spawn_check(project_root, args.host, args.port, args.rpc_timeout_s, child_env, spawn_path, base_config_path):
                    abort_reason = f"configured ego spawn station is not clear after {case['case_id']}"
                    print(f"[FATAL] {abort_reason}; see {spawn_path}. Do not continue the batch until the world is clean.")
                    break

            if returncode != 0 and not args.continue_on_error:
                abort_reason = f"episode failed: {controller}/{case['case_id']} rc={returncode}"
                break
        if abort_reason:
            break

    status = "completed" if not abort_reason and not errors else "failed_or_aborted"
    summary = {"status": status, "abort_reason": abort_reason, "error_count": len(errors), "errors": errors}
    (run_root / "batch_status.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    error_path = run_root / f"{design_name}_errors.json"
    error_path.write_text(json.dumps(errors, indent=2), encoding="utf-8")
    print(f"\nBatch status: {status}; run tag: {run_tag}; errors: {len(errors)}")
    print(f"Details: {run_root}")
    if abort_reason:
        print(f"Stopped early: {abort_reason}")
    if errors or abort_reason:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
