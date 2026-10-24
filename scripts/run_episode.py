#!/usr/bin/env python3
"""Run one RAPID-AD episode through MARSHAL's CARLA scenario harness."""
from __future__ import annotations

import argparse
import json
import logging
import os
import re
import sys
import traceback
from pathlib import Path


def _safe(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", value).strip("_") or "episode"


def _merge_dict(dst: dict, src: dict) -> dict:
    for key, value in src.items():
        if isinstance(value, dict) and isinstance(dst.get(key), dict):
            _merge_dict(dst[key], value)
        else:
            dst[key] = value
    return dst


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--marshal-root", default="/home/senzeyu2/code/MARSHAL")
    parser.add_argument("--case-json", required=True)
    parser.add_argument("--base-config", default=None)
    parser.add_argument("--controller", default="rapid_ad_oracle",
                        help="MARSHAL controller name: rapid_ad_oracle, baseline, tm, pid, mpc, vlm, or a registered model")
    parser.add_argument("--model", default=None, help="Model id for controller=vlm")
    parser.add_argument("--controller-config-json", default=None,
                        help="Optional JSON object merged into the episode config for model-specific settings")
    parser.add_argument("--query-period-s", type=float, default=0.5)
    parser.add_argument("--max-queries", type=int, default=None)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=2000)
    parser.add_argument("--rpc-timeout", type=float, default=20.0)
    parser.add_argument("--timeout-s", type=float, default=22.0)
    parser.add_argument("--fps", type=float, default=20.0)
    parser.add_argument("--out-root", default="/data0/senzeyu2/dataset/RAPID-AD/runs")
    parser.add_argument("--episode-id", default=None)
    parser.add_argument("--evidence-mode", choices=["frame_hold", "physical_occluder"], default=None)
    args = parser.parse_args()

    project_root = Path(__file__).resolve().parents[1]
    marshal_root = Path(args.marshal_root).expanduser().resolve()
    sys.path.insert(0, str(project_root))
    sys.path.insert(0, str(marshal_root))

    from marshal_bench.utils.logging_utils import EpisodeLogger
    import carla  # type: ignore

    base_path = Path(args.base_config).resolve() if args.base_config else project_root / "configs" / "base_episode.json"
    config = json.loads(base_path.read_text(encoding="utf-8"))
    case = json.loads(Path(args.case_json).resolve().read_text(encoding="utf-8"))
    if args.evidence_mode:
        case["evidence_mode"] = args.evidence_mode
        if args.evidence_mode == "physical_occluder":
            # A persistent physical occluder is an external-validity check, not
            # one of the timed frame-hold factorial cells.
            case["gap_timing"] = "none"
            case["evidence_gap"] = True
    config["rapid_ad"] = case
    config["controller"] = args.controller
    config["timeout_sec"] = float(args.timeout_s)
    config["fps"] = float(args.fps)
    # Dynamic episodes must run to the configured horizon; MARSHAL's static
    # expected-action early-stop logic is not an appropriate stopping rule.
    os.environ["MARSHAL_NO_STOP_EARLY_TERMINATION"] = "1"
    os.environ["MARSHAL_TIMEOUT_S"] = str(float(args.timeout_s))
    config["seed"] = int(case.get("seed", config.get("seed", 1)))
    config["expected_behavior"] = dict(config.get("expected_behavior") or {})
    config["expected_behavior"]["action"] = "HOLD"
    config["_rapid_ad_project_root"] = str(project_root)

    if args.controller == "vlm":
        if not args.model:
            parser.error("--model is required when --controller vlm")
        config["vlm"] = dict(config.get("vlm") or {})
        config["vlm"].update({
            "backend": config["vlm"].get("backend", "hf"),
            "model": args.model,
            "query_period_s": float(args.query_period_s),
            "max_queries": args.max_queries,
        })
    if args.controller in {"pid", "mpc"}:
        config["classical"] = dict(config.get("classical") or {})
        config["classical"].setdefault("target_speed_kmh", float((config.get("ego") or {}).get("target_speed", 12.0)))
        config[args.controller] = dict(config.get(args.controller) or {})
        config[args.controller].setdefault("target_speed_kmh", float((config.get("ego") or {}).get("target_speed", 12.0)))
    if args.controller_config_json:
        custom = json.loads(Path(args.controller_config_json).resolve().read_text(encoding="utf-8"))
        _merge_dict(config, custom)

    episode_id = args.episode_id or f"rapid_ad_{_safe(str(case.get('case_id', 'case')))}_{_safe(args.controller)}"
    config["episode_id"] = episode_id
    out_root = Path(args.out_root).expanduser().resolve()
    out_root.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(level=logging.INFO, filename=str(out_root / f"{_safe(episode_id)}.log"),
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    logger = EpisodeLogger(episode_id, output_root=str(out_root))
    config["_episode_logger"] = logger
    clean_config = {k: v for k, v in config.items() if not k.startswith("_")}
    logger.save_metadata({"project": "RAPID-AD", "config": clean_config, "case": case})

    try:
        client = carla.Client(args.host, int(args.port))
        client.set_timeout(float(args.rpc_timeout))
        client_ver = client.get_client_version()
        server_ver = client.get_server_version()
        if client_ver != server_ver:
            raise RuntimeError(f"CARLA client/server version mismatch: client={client_ver}, server={server_ver}")
        from marshal_bench.scenarios.rapid_ad_factorial_demo import run as run_rapid_ad
        result = run_rapid_ad(client, config, logger)
        logger.save_metadata({"marshal_result": result}, name="marshal_result.json")
        logger.log_event("rapid_ad_episode_finished", case_id=case.get("case_id"), controller=args.controller)
        logger.close()
        print(f"[OK] episode={episode_id}")
        print(f"[OK] metrics={out_root / episode_id / 'rapid_ad_metrics.json'}")
        return 0
    except Exception as exc:
        logger.log_event("rapid_ad_episode_exception", error=repr(exc), traceback=traceback.format_exc())
        logger.save_metadata({"error": repr(exc), "traceback": traceback.format_exc()}, name="episode_error.json")
        logger.close()
        print(f"[FAIL] {type(exc).__name__}: {exc}", file=sys.stderr)
        traceback.print_exc()
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
