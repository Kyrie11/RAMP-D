#!/usr/bin/env python3
"""Check CARLA/MARSHAL paths, imported API provenance, and optional server health."""
from __future__ import annotations

import argparse
import glob
import os
import re
import subprocess
import sys
from pathlib import Path


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--carla-root", default="/data0/senzeyu2/dataset/CRADrive/CARLA0.9.15")
    ap.add_argument("--marshal-root", default="/home/senzeyu2/code/MARSHAL")
    ap.add_argument("--base-config", default=str(Path(__file__).resolve().parents[1] / "configs" / "base_episode.json"))
    ap.add_argument("--roadwork-root", default="/home/senzeyu2/code/roadwork-dataset")
    ap.add_argument("--bench2drive-root", default="/home/senzeyu2/code/Bench2Drive")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=2000)
    ap.add_argument("--timeout", type=float, default=5.0)
    ap.add_argument("--skip-server", action="store_true")
    args = ap.parse_args()

    carla_root = Path(args.carla_root).expanduser().resolve()
    marshal_root = Path(args.marshal_root).expanduser().resolve()
    print(f"Python: {sys.executable}")
    print(f"Python version: {sys.version.split()[0]}")
    print(f"CARLA root: {carla_root}")
    print(f"MARSHAL root: {marshal_root}")
    failures = 0

    required = [
        ("CarlaUE4.sh", carla_root / "CarlaUE4.sh"),
        ("CARLA PythonAPI", carla_root / "PythonAPI" / "carla"),
        ("CARLA agents package", carla_root / "PythonAPI" / "carla" / "agents"),
        ("MARSHAL scenario harness", marshal_root / "marshal_bench" / "scenarios" / "_common.py"),
    ]
    if not any((marshal_root / candidate).exists() for candidate in ("start.py", "scripts/run_marshal_sweep.py", "scripts/run_marshal_officer_demo.py")):
        required.append(("MARSHAL entrypoint (start.py or sweep/demo script)", marshal_root / "start.py"))
    for label, path in required:
        if path.exists():
            print(f"[OK] {label}: {path}")
        else:
            print(f"[FAIL] {label} not found: {path}")
            failures += 1

    for label, path in [
        ("ROADWork clone (optional)", Path(args.roadwork_root)),
        ("Bench2Drive clone (optional)", Path(args.bench2drive_root)),
    ]:
        print(f"[OK] {label}: {path}") if path.exists() else print(f"[INFO] {label} not found: {path}; not required for Stage 1-3")

    wheels = glob.glob(str(carla_root / "PythonAPI" / "carla" / "dist" / "carla*0.9.15*.whl"))
    if wheels:
        print("[INFO] Candidate CARLA 0.9.15 wheels:")
        for wheel in wheels:
            print(f"       {wheel}")
    else:
        print("[WARN] No 0.9.15 wheel found under CARLA_ROOT; verify the installed PythonAPI source.")

    carla_api_root = carla_root / "PythonAPI" / "carla"
    sys.path.insert(0, str(carla_api_root))
    for egg in sorted((carla_api_root / "dist").glob("*0.9.15*.egg"), reverse=True):
        sys.path.insert(0, str(egg))
    try:
        import carla  # type: ignore
        module_path = Path(getattr(carla, "__file__", "unknown")).resolve()
        print(f"[OK] import carla: {module_path}")
        if str(module_path).startswith(str(carla_root)):
            print("[OK] imported CARLA module is under the configured CARLA_ROOT")
        else:
            print("[WARN] imported CARLA module is outside CARLA_ROOT; confirm it is the 0.9.15 API matching the server")
    except Exception as exc:
        print(f"[FAIL] import carla failed: {type(exc).__name__}: {exc}")
        return 2

    try:
        sys.path.insert(0, str(marshal_root))
        from marshal_bench.controllers import make_controller  # noqa: F401
        from marshal_bench.scenarios._common import run_scenario  # noqa: F401
        print("[OK] MARSHAL imports work")
    except Exception as exc:
        print(f"[FAIL] MARSHAL imports failed: {type(exc).__name__}: {exc}")
        failures += 1

    # Warn about hard-coded alternate CARLA trees. The uploaded run logs showed
    # CARLA_0.9.15 while the configured root was CARLA0.9.15 (without underscore).
    compat_file = marshal_root / "marshal_bench" / "utils" / "carla_api_compat.py"
    if compat_file.exists():
        txt = compat_file.read_text(encoding="utf-8", errors="replace")
        candidates = sorted(set(re.findall(r"/[^\"'\s]+/CARLA[_A-Za-z0-9.]+/PythonAPI/carla", txt)))
        for candidate in candidates:
            resolved = str(Path(candidate).resolve())
            expected = str((carla_root / "PythonAPI" / "carla").resolve())
            if resolved != expected:
                print(f"[WARN] MARSHAL compatibility code contains alternate CARLA agents path: {candidate}")
                print("       Ensure this path is the same 0.9.15 installation, or replace it with CARLA_ROOT/PythonAPI/carla.")

    if not args.skip_server:
        checker = Path(__file__).resolve().parent / "check_carla.py"
        env = os.environ.copy()
        env["CARLA_ROOT"] = str(carla_root)
        proc = subprocess.run(
            [sys.executable, str(checker), "--host", args.host, "--port", str(args.port), "--timeout", str(args.timeout)],
            env=env, text=True, capture_output=True, timeout=max(10.0, args.timeout + 3.0),
        )
        print(proc.stdout, end="")
        if proc.returncode != 0:
            print(proc.stderr, end="")
            failures += 1
        else:
            spawn_checker = Path(__file__).resolve().parent / "check_spawn.py"
            spawn_proc = subprocess.run(
                [sys.executable, str(spawn_checker), "--base-config", str(Path(args.base_config).expanduser().resolve()), "--host", args.host, "--port", str(args.port), "--timeout", str(args.timeout)],
                env=env, text=True, capture_output=True, timeout=max(10.0, args.timeout + 3.0),
            )
            print("[SPAWN CHECK]")
            print(spawn_proc.stdout, end="")
            if spawn_proc.returncode != 0:
                print(spawn_proc.stderr, end="")
                failures += 1

    if failures:
        print(f"Preflight failed with {failures} blocking issue(s).")
        return 2
    print("Preflight passed. Run exactly one Oracle smoke episode before any batch.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
