#!/usr/bin/env python3
"""Fast CARLA RPC health check used before and after each episode."""
from __future__ import annotations

import argparse
import json
import os
import socket
import sys
import time
from pathlib import Path


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=2000)
    ap.add_argument("--timeout", type=float, default=5.0)
    ap.add_argument("--out", default=None)
    ap.add_argument("--allow-sync", action="store_true", help="Do not fail if world synchronous mode is enabled")
    args = ap.parse_args()
    report = {
        "time_unix": time.time(),
        "host": args.host,
        "port": args.port,
        "timeout_s": args.timeout,
        "python": sys.executable,
        "python_version": sys.version.split()[0],
        "carla_root_env": os.environ.get("CARLA_ROOT"),
    }
    try:
        with socket.create_connection((args.host, args.port), timeout=args.timeout):
            report["tcp_reachable"] = True
    except OSError as exc:
        report.update({"tcp_reachable": False, "error": repr(exc)})
        _write(report, args.out)
        print(json.dumps(report, indent=2))
        return 2
    carla_root = Path(os.environ.get("CARLA_ROOT", "/data0/senzeyu2/dataset/CRADrive/CARLA0.9.15")).expanduser().resolve()
    carla_api_root = carla_root / "PythonAPI" / "carla"
    sys.path.insert(0, str(carla_api_root))
    for egg in sorted((carla_api_root / "dist").glob("*0.9.15*.egg"), reverse=True):
        sys.path.insert(0, str(egg))
    try:
        import carla  # type: ignore
        report["carla_module"] = getattr(carla, "__file__", "unknown")
        client = carla.Client(args.host, args.port)
        client.set_timeout(args.timeout)
        client_version = client.get_client_version()
        server_version = client.get_server_version()
        world = client.get_world()
        map_name = getattr(world.get_map(), "name", "unknown")
        settings = world.get_settings()
        sync_mode = bool(getattr(settings, "synchronous_mode", False))
        blueprints = world.get_blueprint_library()
        try:
            blueprints.find("vehicle.tesla.model3")
            tesla_blueprint_available = True
        except Exception:
            tesla_blueprint_available = False
        report.update({
            "client_version": client_version,
            "server_version": server_version,
            "versions_match": client_version == server_version,
            "map_name": map_name,
            "actor_count": len(world.get_actors()),
            "world_synchronous_mode": sync_mode,
            "fixed_delta_seconds": getattr(settings, "fixed_delta_seconds", None),
            "vehicle_tesla_model3_available": tesla_blueprint_available,
        })
        if client_version != server_version:
            report["error"] = "CARLA client/server version mismatch"
            _write(report, args.out)
            print(json.dumps(report, indent=2))
            return 3
        if sync_mode and not args.allow_sync:
            report["error"] = "CARLA world is left in synchronous mode outside an episode; reset/restart the server before continuing"
            _write(report, args.out)
            print(json.dumps(report, indent=2))
            return 5
    except Exception as exc:
        report.update({"api_ok": False, "error": repr(exc)})
        _write(report, args.out)
        print(json.dumps(report, indent=2))
        return 4
    report["api_ok"] = True
    _write(report, args.out)
    print(json.dumps(report, indent=2))
    return 0


def _write(report: dict, out: str | None) -> None:
    if not out:
        return
    path = Path(out)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2), encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
