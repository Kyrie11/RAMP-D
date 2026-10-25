#!/usr/bin/env python3
"""Check whether the configured ego spawn station is occupied or off-road."""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--base-config", default=str(Path(__file__).resolve().parents[1] / "configs" / "base_episode.json"))
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=2000)
    ap.add_argument("--timeout", type=float, default=5.0)
    ap.add_argument("--radius-m", type=float, default=5.0)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()
    cfg = json.loads(Path(args.base_config).read_text(encoding="utf-8"))
    spawn = (cfg.get("ego") or {}).get("spawn_transform") or {}
    if not all(k in spawn for k in ("x", "y", "z", "yaw")):
        print("[FAIL] base config has no complete ego.spawn_transform")
        return 2
    carla_root = Path(os.environ.get("CARLA_ROOT", "/data0/senzeyu2/dataset/CRADrive/CARLA0.9.15")).expanduser().resolve()
    carla_api_root = carla_root / "PythonAPI" / "carla"
    sys.path.insert(0, str(carla_api_root))
    for egg in sorted((carla_api_root / "dist").glob("*0.9.15*.egg"), reverse=True):
        sys.path.insert(0, str(egg))
    try:
        import carla  # type: ignore
        client = carla.Client(args.host, args.port)
        client.set_timeout(args.timeout)
        world = client.get_world()
        location = carla.Location(x=float(spawn["x"]), y=float(spawn["y"]), z=float(spawn["z"]))
        waypoint = world.get_map().get_waypoint(location, project_to_road=True, lane_type=carla.LaneType.Driving)
        report = {
            "map_name": getattr(world.get_map(), "name", "unknown"),
            "spawn_transform": spawn,
            "radius_m": args.radius_m,
            "waypoint_found": waypoint is not None,
            "nearby_dynamic_actors": [],
        }
        if waypoint is not None:
            report["road_id"] = waypoint.road_id
            report["lane_id"] = waypoint.lane_id
            report["lane_type"] = str(waypoint.lane_type)
            report["waypoint_location"] = {"x": waypoint.transform.location.x, "y": waypoint.transform.location.y, "z": waypoint.transform.location.z}
        for actor in world.get_actors():
            type_id = str(getattr(actor, "type_id", ""))
            if not (type_id.startswith("vehicle.") or type_id.startswith("walker.") or type_id.startswith("sensor.")):
                continue
            try:
                loc = actor.get_location()
                dx, dy, dz = loc.x - location.x, loc.y - location.y, loc.z - location.z
                dist = (dx * dx + dy * dy + dz * dz) ** 0.5
                if dist <= args.radius_m:
                    report["nearby_dynamic_actors"].append({
                        "id": actor.id, "type_id": type_id, "distance_m": round(dist, 3),
                        "location": {"x": loc.x, "y": loc.y, "z": loc.z},
                    })
            except Exception:
                pass
        report["clear"] = bool(report["waypoint_found"] and not report["nearby_dynamic_actors"])
        out = json.dumps(report, indent=2)
        print(out)
        if args.out:
            path = Path(args.out)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(out, encoding="utf-8")
        return 0 if report["clear"] else 5
    except Exception as exc:
        report = {"error": repr(exc), "carla_root_env": os.environ.get("CARLA_ROOT")}
        print(json.dumps(report, indent=2))
        if args.out:
            Path(args.out).write_text(json.dumps(report, indent=2), encoding="utf-8")
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
