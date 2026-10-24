#!/usr/bin/env python3
"""Check CARLA/MARSHAL paths, Python API import, and optional running server."""
from __future__ import annotations

import argparse
import glob
import os
import socket
import sys
from pathlib import Path


def check_server(host: str, port: int, timeout: float, carla_module) -> int:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            pass
    except OSError as exc:
        print(f"[WARN] CARLA RPC endpoint {host}:{port} not reachable: {exc}")
        return 1
    try:
        client = carla_module.Client(host, port)
        client.set_timeout(timeout)
        client_ver = client.get_client_version()
        server_ver = client.get_server_version()
        print(f"[OK] CARLA client version: {client_ver}")
        print(f"[OK] CARLA server version: {server_ver}")
        if client_ver != server_ver:
            print("[FAIL] Client/server CARLA versions differ; use the matching PythonAPI wheel and server build.")
            return 2
        world = client.get_world()
        map_name = getattr(world.get_map(), "name", "unknown")
        print(f"[INFO] Current map: {map_name}")
        if "Town03" not in map_name:
            print("[WARN] RAPID-AD's first scene uses Town03. The runner will request Town03; confirm it exists in this CARLA package.")
        return 0
    except Exception as exc:
        print(f"[FAIL] CARLA RPC connected but API check failed: {type(exc).__name__}: {exc}")
        return 2


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--carla-root", default="/data0/senzeyu2/dataset/CRADrive/CARLA0.9.15")
    parser.add_argument("--marshal-root", default="/home/senzeyu2/code/MARSHAL")
    parser.add_argument("--roadwork-root", default="/home/senzeyu2/code/roadwork-dataset")
    parser.add_argument("--bench2drive-root", default="/home/senzeyu2/code/Bench2Drive")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=2000)
    parser.add_argument("--timeout", type=float, default=5.0)
    parser.add_argument("--skip-server", action="store_true", help="Only check local paths and Python imports")
    args = parser.parse_args()

    carla_root = Path(args.carla_root).expanduser().resolve()
    marshal_root = Path(args.marshal_root).expanduser().resolve()
    print(f"Python: {sys.executable}")
    print(f"Python version: {sys.version.split()[0]}")
    print(f"CARLA root: {carla_root}")
    print(f"MARSHAL root: {marshal_root}")

    failures = 0
    for label, path in [
        ("CarlaUE4.sh", carla_root / "CarlaUE4.sh"),
        ("CARLA PythonAPI", carla_root / "PythonAPI" / "carla"),
        ("MARSHAL scenario harness", marshal_root / "marshal_bench" / "scenarios" / "_common.py"),
        ("MARSHAL runner", marshal_root / "scripts" / "_run_vlm_test.py"),
        ("ROADWork clone", Path(args.roadwork_root)),
        ("Bench2Drive clone", Path(args.bench2drive_root)),
    ]:
        if path.exists():
            print(f"[OK] {label}: {path}")
        else:
            print(f"[WARN] {label} not found: {path}")
            if label in {"CarlaUE4.sh", "CARLA PythonAPI", "MARSHAL scenario harness", "MARSHAL runner"}:
                failures += 1

    wheel_pattern = str(carla_root / "PythonAPI" / "carla" / "dist" / "carla*0.9.15*.whl")
    wheels = glob.glob(wheel_pattern)
    if wheels:
        print("[INFO] Candidate CARLA 0.9.15 wheels:")
        for wheel in wheels:
            print(f"       {wheel}")
    else:
        print(f"[WARN] No wheel matched {wheel_pattern}; check PythonAPI/carla/dist or the installed package.")

    try:
        import carla  # type: ignore
        print(f"[OK] import carla: module={getattr(carla, '__file__', 'unknown')} version={getattr(carla, '__version__', 'not exposed')}")
    except Exception as exc:
        print(f"[FAIL] import carla failed: {type(exc).__name__}: {exc}")
        print("       Install the CARLA 0.9.15 wheel matching this Python interpreter from PythonAPI/carla/dist.")
        return 2

    try:
        sys.path.insert(0, str(marshal_root))
        from marshal_bench.controllers import make_controller  # noqa: F401
        from marshal_bench.scenarios._common import run_scenario  # noqa: F401
        print("[OK] MARSHAL imports work in this Python environment")
    except Exception as exc:
        print(f"[FAIL] MARSHAL imports failed: {type(exc).__name__}: {exc}")
        failures += 1

    if not args.skip_server:
        status = check_server(args.host, args.port, args.timeout, carla)
        if status == 2:
            failures += 1
        elif status == 1:
            print("[INFO] Start CARLA and rerun preflight without --skip-server before executing episodes.")
            return 1

    if failures:
        print(f"Preflight completed with {failures} blocking issue(s).")
        return 2
    print("Preflight checks passed. Next run the existing MARSHAL reference sweep before RAPID-AD episodes.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
