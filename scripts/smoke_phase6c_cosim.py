#!/usr/bin/env python3
"""Bounded headless CARLA 0.9.16/SUMO 1.20 co-simulation smoke.

Only this process ticks both simulators. It reuses CARLA's official 0.9.16
`SimulationSynchronization`, never starts a second uncontrolled sync loop.
SUMO cfg and matching CARLA map must already exist and be manually checked.
"""
from __future__ import annotations
import argparse
import importlib.util
import json
import os
from pathlib import Path
import sys

from rampd_core.clock_ledger import CoSimTick, CoSimLedger


def run(args) -> dict:
    # Fail closed before acquiring ownership if the configuration is missing.
    if not args.sumo_config.is_file():
        raise FileNotFoundError(f"SUMO .sumocfg missing: {args.sumo_config}")
    script = args.carla_cosim_dir / "run_synchronization.py"
    if not script.is_file():
        raise FileNotFoundError(f"CARLA integration entry missing: {script}")
    if not (args.carla_cosim_dir / "sumo_integration").is_dir():
        raise FileNotFoundError("official CARLA sumo_integration package missing")
    if not os.environ.get("SUMO_HOME"):
        raise RuntimeError("SUMO_HOME is required by CARLA's 0.9.16 bridge")
    # Both a read-only connection and the official bridge use the same CARLA
    # PythonAPI package.  Pre-check prevents concurrent synchronous tick owners.
    import carla
    probe = carla.Client(args.carla_host, args.carla_port)
    probe.set_timeout(10.0)
    world = probe.get_world()
    world_name = world.get_map().name
    if world.get_settings().synchronous_mode:
        raise RuntimeError("CARLA already in synchronous mode: another tick owner may exist")
    if args.expected_carla_map and args.expected_carla_map not in world_name:
        raise RuntimeError(f"CARLA map mismatch: expected {args.expected_carla_map}, got {world_name}")
    sys.path.insert(0, str(args.carla_cosim_dir.resolve()))
    spec = importlib.util.spec_from_file_location("rampd_carla_official_cosim", script)
    if spec is None or spec.loader is None:
        raise RuntimeError("official CARLA co-sim module could not be loaded")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    import traci  # Loaded from SUMO_HOME/tools or installed traci package.

    ledger = CoSimLedger(args.step_length)
    sumo = None
    carla_sim = None
    sync = None
    try:
        sumo = module.SumoSimulation(str(args.sumo_config.resolve()), args.step_length,
                                     None, None, False, 1)
        carla_sim = module.CarlaSimulation(args.carla_host, args.carla_port, args.step_length)
        # Using the unmodified official sync class means one tick owner;
        # TLS master is explicit and checked in the experiment report.
        sync = module.SimulationSynchronization(sumo, carla_sim,
                                                tls_manager=args.tls_manager)
        for step in range(args.steps):
            sync.tick()
            snapshot = carla_sim.world.get_snapshot()
            ledger.record(CoSimTick(
                step=step, carla_frame=int(snapshot.frame),
                carla_elapsed_s=float(snapshot.timestamp.elapsed_seconds),
                sumo_elapsed_s=float(traci.simulation.getTime()),
                sumo_actor_count=int(traci.vehicle.getIDCount()),
                carla_actor_count=len(carla_sim.world.get_actors().filter('vehicle.*')),
                mapped_sumo_to_carla=len(sync.sumo2carla_ids),
                mapped_carla_to_sumo=len(sync.carla2sumo_ids)))
    finally:
        if sync is not None:
            sync.close()
        else:
            if carla_sim is not None:
                carla_sim.close()
            if sumo is not None:
                sumo.close()
    return {**ledger.summary(), "carla_map":world_name,
            "sumo_config":str(args.sumo_config.resolve()),
            "tls_manager":args.tls_manager, "headless":True,
            "sensor_production_and_delivery_timestamps":"NOT_COLLECTED",
            "event_issue_receipt_activation_local_times":"NOT_COLLECTED",
            "actor_mapping_observed":any(t.mapped_sumo_to_carla+t.mapped_carla_to_sumo > 0 for t in ledger.ticks),
            "actor_identity_and_geometry_verified":False,
            "assurance_scope":"SINGLE_OWNER_CLOCK_AND_REPORTED_ACTOR_COUNTS_SMOKE_ONLY"}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sumo-config", type=Path, required=True)
    parser.add_argument("--carla-cosim-dir", type=Path, required=True)
    parser.add_argument("--carla-host", default="127.0.0.1")
    parser.add_argument("--carla-port", type=int, default=2000)
    parser.add_argument("--expected-carla-map", default="")
    parser.add_argument("--tls-manager", choices=("sumo", "carla", "none"), default="sumo")
    parser.add_argument("--step-length", type=float, default=0.05)
    parser.add_argument("--steps", type=int, default=20)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.steps < 2:
        parser.error("--steps must be >= 2 to verify increments")
    try:
        result = run(args)
    except Exception as exc:
        result = {"schema":"rampd.phase6c.cosim-clock-ledger.v1", "status":"ERROR",
                  "failure_type":type(exc).__name__, "reason":str(exc),
                  "protocol_four_clocks_observed":False,
                  "continuous_physical_safety_certified":False}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result,indent=2,sort_keys=True)+"\n")
    print(json.dumps({k:v for k,v in result.items() if k != "ticks"},indent=2))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
