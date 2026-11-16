#!/usr/bin/env python3
"""Bounded read-only WOMD/AV2 real-data validation, with strict PASS/SKIP/ERROR.

This script tests real optional dataset readers, not the native MPFR verifier.
It creates an import shell for the pure-Python dataset modules to permit
independent diagnosis even before a C++ backend is available.
"""
from __future__ import annotations

import argparse
import importlib
import json
from pathlib import Path
import sys
import traceback
import types

ROOT = Path(__file__).resolve().parents[1]
LIB = ROOT / "python" / "rampd_core"
sys.path.insert(0, str(ROOT / "python"))
pkg = types.ModuleType("rampd_core")
pkg.__path__ = [str(LIB)]
sys.modules["rampd_core"] = pkg
for name in ("protocol", "map_context", "scene_schema", "record_adapters", "forecast", "phase6c"):
    # Explicitly order imports for standalone diagnostics.
    importlib.import_module("rampd_core." + name)
from rampd_core.record_adapters import (iter_womd_validation, iter_av2_validation,
                                         OptionalDependencyError)
from rampd_core.phase6c import build_scene_forecast_sample


def _validate_one(parsed):
    scene = parsed.scene
    scene.assert_valid()
    ctx = scene.map_context
    if ctx is None or not ctx.complete_geometry or not ctx.primitives:
        raise ValueError("map_geometry_incomplete: map could not be fully parsed")
    sample = build_scene_forecast_sample(scene)
    inputs = sample.encoder_inputs
    if inputs["static_map"] is None or inputs["static_map"].signals:
        raise ValueError("encoder map contains future/unobserved signal states")
    if inputs["static_map"].coordinate_frame != sample.coordinate_frame:
        raise ValueError("map/track coordinate frames are inconsistent")
    if any(s.timestamp_s > sample.current_timestamp_s for s in sample.map_context_history.signals):
        raise ValueError("future signal leaked into sample history")
    if any(s.timestamp_s <= sample.current_timestamp_s for s in sample.future_signal_targets):
        raise ValueError("signal label leakage across current time boundary")
    return {
        "scenario_id": parsed.scenario_id,
        "source_file": parsed.source_file,
        "source_file_sha256": parsed.source_file_sha256,
        "record_sha256": parsed.record_sha256,
        "scenario_content_sha256": parsed.scenario_content_sha256,
        "map_content_sha256": parsed.map_content_sha256,
        "map_primitives": len(ctx.primitives),
        "signals_all": len(ctx.signals),
        "signals_history": len(sample.map_context_history.signals),
        "signals_future_label": len(sample.future_signal_targets),
        "track_count": len(scene.tracks),
        "current_time_index": scene.manifest.current_time_index,
        "map_geometry_complete": ctx.complete_geometry,
        "position_reference": scene.manifest.position_reference,
        "map_coordinate_frame": ctx.coordinate_frame,
        "future_available": scene.manifest.future_available,
    }


def _probe(label, root, iterator, n, max_files, skip_hash=False):
    result = {"dataset": label, "root": str(root), "status": "ERROR", "records": [], "reason": None}
    if not root.is_dir():
        result.update(status="SKIP", reason=f"dataset directory does not exist: {root}")
        return result
    try:
        if label == "WOMD":
            examples = iterator(root, max_records=n, max_files=max_files,
                                hash_source_files=not skip_hash)
        else:
            examples = iterator(root, max_records=n, hash_source_files=not skip_hash)
        for parsed in examples:
            result["records"].append(_validate_one(parsed))
        ids = [r["scenario_id"] for r in result["records"]]
        if not ids:
            raise ValueError("no real records parsed")
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate scenario IDs in sampled records")
        result["status"] = "PASS"
    except (FileNotFoundError, ImportError, ModuleNotFoundError, OptionalDependencyError) as exc:
        result.update(status="SKIP", reason=f"{type(exc).__name__}: {exc}")
    except Exception as exc:
        result.update(status="ERROR", reason=f"{type(exc).__name__}: {exc}",
                      traceback=traceback.format_exc(limit=6))
    return result


def main():
    a = argparse.ArgumentParser()
    a.add_argument("--womd-root", required=True, type=Path)
    a.add_argument("--av2-root", required=True, type=Path)
    a.add_argument("--max-records", type=int, default=1)
    a.add_argument("--max-files", type=int, default=3)
    a.add_argument("--output", required=True, type=Path)
    a.add_argument("--skip-source-file-hash", action="store_true",
                   help="Fast debug only; default is full shard/file SHA-256")
    args = a.parse_args()
    if not 1 <= args.max_records <= 100 or not 1 <= args.max_files <= 100:
        a.error("max-records and max-files must be 1..100")
    womd = _probe("WOMD", args.womd_root, iter_womd_validation, args.max_records, args.max_files,
                  args.skip_source_file_hash)
    av2 = _probe("AV2", args.av2_root, iter_av2_validation, args.max_records, args.max_files,
                 args.skip_source_file_hash)
    statuses = (womd["status"], av2["status"])
    status = "ERROR" if "ERROR" in statuses else "SKIP" if "SKIP" in statuses else "PASS"
    summary = {"phase": "6B_real_data_and_6C_A2_geometry_smoke",
               "status": status, "datasets": {"womd": womd, "av2": av2},
               "real_scene_verified": status == "PASS",
               "map_geometry_verified_on_sample": status == "PASS",
               "native_mpfr_verified": False, "full_support_certified": False,
               "simulators_used": False, "records_requested_per_dataset": args.max_records,
               "source_file_hashing_enabled": not args.skip_source_file_hash}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return {"PASS": 0, "SKIP": 3, "ERROR": 4}[status]


if __name__ == "__main__":
    raise SystemExit(main())
