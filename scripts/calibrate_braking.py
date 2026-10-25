#!/usr/bin/env python3
"""Measure a conservative full-brake envelope for the configured CARLA ego vehicle.

Run with no other CARLA client actively ticking the world. The script temporarily
switches the world to synchronous mode and restores settings in a finally block.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import statistics
import sys
import time
from pathlib import Path


def speed_mps(actor) -> float:
    v = actor.get_velocity()
    return math.sqrt(float(v.x) ** 2 + float(v.y) ** 2 + float(v.z) ** 2)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--base-config", default=str(Path(__file__).resolve().parents[1] / "configs" / "base_episode.json"))
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=2000)
    ap.add_argument("--rpc-timeout", type=float, default=8.0)
    ap.add_argument("--vehicle-blueprint", default=None,
                    help="Must match the actual MARSHAL ego blueprint; defaults to config ego.blueprint or vehicle.tesla.model3")
    ap.add_argument("--target-speed-kmh", type=float, default=12.0)
    ap.add_argument("--repeats", type=int, default=3)
    ap.add_argument("--fps", type=float, default=20.0)
    ap.add_argument("--conservatism", type=float, default=0.8, help="Multiply effective deceleration by this factor")
    ap.add_argument("--max-relative-spread", type=float, default=0.20,
                    help="Refuse --apply-config when (max-min)/median deceleration exceeds this value")
    ap.add_argument("--out", default="/data0/senzeyu2/dataset/RAPID-AD/calibration/braking_calibration.json")
    ap.add_argument("--apply-config", action="store_true", help="Write conservative deceleration into base config and mark it calibrated")
    args = ap.parse_args()
    if args.repeats < 2:
        ap.error("use at least 2 repeats to estimate run-to-run variation")
    if not 0.3 <= args.conservatism <= 1.0:
        ap.error("--conservatism must be in [0.3, 1.0]")

    cfg_path = Path(args.base_config).resolve()
    cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
    spawn = (cfg.get("ego") or {}).get("spawn_transform") or {}
    blueprint_id = str(args.vehicle_blueprint or (cfg.get("ego") or {}).get("blueprint", "vehicle.tesla.model3"))
    if not all(k in spawn for k in ("x", "y", "z", "yaw")):
        print("[FAIL] base config needs ego.spawn_transform x/y/z/yaw")
        return 2

    actor = None
    client = None
    world = None
    original_settings = None
    results = []
    try:
        import carla  # type: ignore
        client = carla.Client(args.host, args.port)
        client.set_timeout(args.rpc_timeout)
        client_version = client.get_client_version()
        server_version = client.get_server_version()
        if client_version != server_version:
            raise RuntimeError(f"CARLA client/server mismatch: {client_version} vs {server_version}")
        world = client.get_world()
        map_name = getattr(world.get_map(), "name", "unknown")
        if "Town03" not in map_name:
            raise RuntimeError(f"Expected Town03 for the configured spawn station, current map is {map_name}")
        original_settings = world.get_settings()
        settings = world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = 1.0 / max(1.0, args.fps)
        world.apply_settings(settings)
        bp = world.get_blueprint_library().find(blueprint_id)
        transform = carla.Transform(
            carla.Location(x=float(spawn["x"]), y=float(spawn["y"]), z=float(spawn["z"])),
            carla.Rotation(yaw=float(spawn["yaw"])),
        )
        target_speed = args.target_speed_kmh / 3.6
        dt = 1.0 / max(1.0, args.fps)
        print(f"[INFO] map={map_name} client/server={client_version}/{server_version} vehicle={blueprint_id}")
        print(f"[INFO] target speed={args.target_speed_kmh:.2f} km/h repeats={args.repeats}")

        for rep in range(args.repeats):
            actor = world.try_spawn_actor(bp, transform)
            if actor is None:
                raise RuntimeError("Could not spawn calibration vehicle at the configured station; run check_spawn.py and clear the world first")
            actor.set_autopilot(False)
            fwd = actor.get_transform().get_forward_vector()
            origin = actor.get_location()

            def progress() -> float:
                loc = actor.get_location()
                return (float(loc.x) - float(origin.x)) * float(fwd.x) + (float(loc.y) - float(origin.y)) * float(fwd.y)

            # Warm up a few ticks, then accelerate under a fixed low throttle.
            for _ in range(3):
                actor.apply_control(carla.VehicleControl(throttle=0.0, brake=0.0))
                world.tick()
            speed_history = []
            accelerated = False
            for tick in range(int(5.0 * args.fps)):
                actor.apply_control(carla.VehicleControl(throttle=0.35, brake=0.0, steer=0.0))
                world.tick()
                v = speed_mps(actor)
                speed_history.append(v)
                if v >= target_speed * 0.98:
                    accelerated = True
                    break
            if not accelerated:
                raise RuntimeError(f"Could not reach target speed in repeat {rep + 1}; last speed={speed_history[-1] if speed_history else 0:.3f} m/s")

            v0 = speed_mps(actor)
            start_progress = progress()
            brake_trace = []
            stopped = False
            for tick in range(int(6.0 * args.fps)):
                actor.apply_control(carla.VehicleControl(throttle=0.0, brake=1.0, steer=0.0, hand_brake=False))
                world.tick()
                v = speed_mps(actor)
                brake_trace.append({"t_s": (tick + 1) * dt, "speed_mps": v, "progress_m": progress() - start_progress})
                if len(brake_trace) >= max(2, int(0.5 * args.fps)) and all(x["speed_mps"] < 0.12 for x in brake_trace[-max(2, int(0.5 * args.fps)):]):
                    stopped = True
                    break
            distance = max(0.0, progress() - start_progress)
            if not stopped or distance < 0.05:
                raise RuntimeError(f"Full-brake calibration did not reach a stable stop in repeat {rep + 1}; stopped={stopped}, distance={distance:.3f} m")
            effective_decel = v0 * v0 / (2.0 * distance)
            # Use a conservative multiplier and take the weakest repeat later.
            results.append({
                "repeat": rep + 1,
                "speed_at_brake_mps": v0,
                "speed_at_brake_kmh": v0 * 3.6,
                "stopping_distance_center_m": distance,
                "effective_deceleration_mps2": effective_decel,
                "stop_duration_s": brake_trace[-1]["t_s"],
                "trace": brake_trace,
            })
            print(f"[OK] repeat={rep + 1} v0={v0*3.6:.2f} km/h distance={distance:.3f} m effective_decel={effective_decel:.3f} m/s^2")
            actor.destroy()
            actor = None
            for _ in range(2):
                world.tick()

        decel_values = [r["effective_deceleration_mps2"] for r in results]
        median_decel = statistics.median(decel_values)
        relative_spread = ((max(decel_values) - min(decel_values)) / median_decel) if median_decel > 0 else float("inf")
        calibration_stable = relative_spread <= args.max_relative_spread
        conservative_decel = min(decel_values) * args.conservatism
        report = {
            "timestamp_unix": time.time(),
            "map_name": map_name,
            "carla_client_version": client_version,
            "carla_server_version": server_version,
            "carla_python_module": getattr(carla, "__file__", "unknown"),
            "vehicle_blueprint": blueprint_id,
            "target_speed_kmh": args.target_speed_kmh,
            "repeats": args.repeats,
            "conservatism_multiplier": args.conservatism,
            "effective_deceleration_values_mps2": decel_values,
            "median_effective_deceleration_mps2": median_decel,
            "relative_spread": relative_spread,
            "max_relative_spread_threshold": args.max_relative_spread,
            "calibration_stable": calibration_stable,
            "conservative_max_brake_decel_mps2": conservative_decel,
            "results": results,
            "notes": [
                "Calibration is specific to this vehicle, speed range, map surface, weather, and CARLA build.",
                "Use the conservative value only for the matching vehicle and conditions; repeat after changing friction/weather or vehicle blueprint.",
                "This estimates straight-line full-brake performance, not a formal reachability proof.",
            ],
        }
        out_path = Path(args.out).expanduser().resolve()
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(f"[OK] calibration written: {out_path}")
        print(f"[RESULT] conservative_max_brake_decel_mps2={conservative_decel:.3f}")
        print(f"[RESULT] calibration_stable={calibration_stable} relative_spread={relative_spread:.3f}")
        if args.apply_config and not calibration_stable:
            print("[FAIL] calibration variability exceeds threshold; config was not changed. Increase repeats or inspect the setup.", file=sys.stderr)
            return 3
        if args.apply_config:
            cfg.setdefault("scene", {})["max_brake_decel_mps2"] = conservative_decel
            cfg["scene"]["recoverability_calibrated"] = True
            cfg["scene"]["braking_calibration_file"] = str(out_path)
            cfg["scene"]["braking_calibration_vehicle"] = blueprint_id
            cfg_path.write_text(json.dumps(cfg, indent=2) + "\n", encoding="utf-8")
            print(f"[OK] updated {cfg_path}; review the calibration JSON before scientific use")
        return 0
    except Exception as exc:
        print(f"[FAIL] {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2
    finally:
        if actor is not None:
            try:
                actor.destroy()
            except Exception:
                pass
        if world is not None and original_settings is not None:
            try:
                world.apply_settings(original_settings)
            except Exception as exc:
                print(f"[WARN] could not restore CARLA world settings: {exc!r}", file=sys.stderr)


if __name__ == "__main__":
    raise SystemExit(main())
