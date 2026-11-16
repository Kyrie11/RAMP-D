#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPORT_DIR="${REPORT_DIR:-$ROOT/reports/phase6b_$(date -u +%Y%m%dT%H%M%SZ)}"
PYTHON_BIN="${PYTHON_BIN:-python}"
WOMD_ROOT="${WOMD_ROOT:-/data0/senzeyu2/dataset/waymo_open_dataset_motion_v_1_3_1/uncompressed/scenario}"
AV2_ROOT="${AV2_ROOT:-/data0/senzeyu2/dataset/Argoverse2/motion}"
MAX_RECORDS="${MAX_RECORDS:-3}"
# Fast bounded sampling is the default. Set HASH_SOURCE_FILES=1 for a full
# cryptographic digest of every source TFRecord/Parquet file.
HASH_SOURCE_FILES="${HASH_SOURCE_FILES:-0}"
case "$HASH_SOURCE_FILES" in
  0|1) ;;
  *) echo "HASH_SOURCE_FILES must be 0 or 1" >&2; exit 2 ;;
esac
mkdir -p "$REPORT_DIR"
export PYTHONPATH="$ROOT/python${PYTHONPATH:+:$PYTHONPATH}"
export PYTEST_DISABLE_PLUGIN_AUTOLOAD="${PYTEST_DISABLE_PLUGIN_AUTOLOAD:-1}"
export HASH_SOURCE_FILES

TEST_START_NS="$(date +%s%N)"
"$PYTHON_BIN" -m pytest -q "$ROOT/tests/test_phase6_data_audit.py" \
  "$ROOT/tests/test_phase6b_record_adapters.py" \
  --junitxml="$REPORT_DIR/phase6b_pytest.xml" | tee "$REPORT_DIR/phase6b_pytest.log"
TEST_END_NS="$(date +%s%N)"
export PHASE6B_PYTEST_ELAPSED_SECONDS="$("$PYTHON_BIN" -c \
  'import sys; print(max(0.0, (int(sys.argv[2])-int(sys.argv[1]))/1e9))' \
  "$TEST_START_NS" "$TEST_END_NS")"

"$PYTHON_BIN" - <<'PY' "$REPORT_DIR" "$WOMD_ROOT" "$AV2_ROOT" "$MAX_RECORDS"
import json
import os
from pathlib import Path
import sys
from time import perf_counter

from rampd_core import (OptionalDependencyError, iter_av2_validation,
                        iter_womd_validation)

report_dir = Path(sys.argv[1])
womd_root, av2_root, max_records = sys.argv[2], sys.argv[3], int(sys.argv[4])
hash_source_files = os.environ.get("HASH_SOURCE_FILES", "0") == "1"

def sample(name, iterator_factory):
    started = perf_counter()
    rows = []
    seen_ids = set()
    seen_digests = set()
    try:
        for parsed in iterator_factory():
            if parsed.scenario_id in seen_ids:
                raise ValueError(f"duplicate scenario_id in validation sample: {parsed.scenario_id}")
            if parsed.scenario_content_sha256 in seen_digests:
                raise ValueError(f"duplicate parsed scenario digest: {parsed.scenario_content_sha256}")
            seen_ids.add(parsed.scenario_id)
            seen_digests.add(parsed.scenario_content_sha256)
            source_path = Path(parsed.source_file)
            try:
                stat = source_path.stat()
                source_size_bytes = stat.st_size
                source_mtime_ns = stat.st_mtime_ns
            except OSError:
                source_size_bytes = None
                source_mtime_ns = None
            rows.append({
                "scenario_id": parsed.scenario_id,
                "source_file": parsed.source_file,
                "source_file_size_bytes": source_size_bytes,
                "source_file_mtime_ns": source_mtime_ns,
                "record_index": parsed.record_index,
                "content_sha256": parsed.content_sha256,
                "content_sha256_semantics": parsed.scene.manifest.metadata.get(
                    "content_sha256_semantics",
                    "source_file_sha256" if parsed.source_file_sha256 else
                    "record_sha256" if parsed.record_sha256 else
                    "canonical_parsed_scene_or_rows_sha256",
                ),
                "source_file_sha256": parsed.source_file_sha256,
                "source_file_hash_status": (
                    "computed" if parsed.source_file_sha256 else "not_computed"
                ),
                "record_sha256": parsed.record_sha256,
                "scenario_content_sha256": parsed.scenario_content_sha256,
                "parser_version": parsed.parser_version,
                "source_schema": parsed.source_schema,
                "split": parsed.scene.manifest.split,
                "current_time_index": parsed.scene.manifest.current_time_index,
                "track_count": len(parsed.scene.tracks),
                "future_available": parsed.scene.manifest.future_available,
                "sample_rate_hz": parsed.scene.manifest.sample_rate_hz,
                "position_reference": parsed.scene.manifest.position_reference,
                "coordinate_frame": parsed.scene.manifest.coordinate_frame,
                "sdc_track_ids": [t.track_id for t in parsed.scene.tracks if t.is_sdc],
                "focal_track_ids": [t.track_id for t in parsed.scene.tracks if t.is_focal],
                "benchmark_target_track_ids": [t.track_id for t in parsed.scene.tracks if t.to_predict],
                "map_file": parsed.map_file,
                "map_content_sha256": parsed.map_content_sha256,
                "clocks": None if parsed.clocks is None else parsed.clocks.to_dict(),
            })
    except (FileNotFoundError, OptionalDependencyError) as exc:
        status = "ERROR" if rows else "SKIP"
        return {
            "status": status, "reason": f"{type(exc).__name__}: {exc}",
            "samples": rows, "elapsed_seconds": perf_counter() - started,
        }
    except Exception as exc:
        return {
            "status": "ERROR", "reason": f"{type(exc).__name__}: {exc}",
            "samples": rows, "elapsed_seconds": perf_counter() - started,
        }
    return {
        "status": "PASS" if rows else "SKIP", "reason": None,
        "samples": rows, "elapsed_seconds": perf_counter() - started,
    }

payload = {
    "schema": "rampd.phase6b.acceptance.v2",
    "phase": "6B",
    "max_records_per_dataset": max_records,
    "womd_validation": sample(
        "womd_validation",
        lambda: iter_womd_validation(
            womd_root, max_records=max_records,
            hash_source_files=hash_source_files,
        ),
    ),
    "av2_validation": sample(
        "av2_validation",
        lambda: iter_av2_validation(
            av2_root, max_records=max_records,
            hash_source_files=hash_source_files,
        ),
    ),
    "simulators_used": False,
    "four_clock_injection": "explicit_only_no_dataset_inference",
    "future_leakage_guard": True,
    "hash_policy": (
        "full_source_file_sha256" if hash_source_files
        else "bounded_sample_record_and_canonical_scene_hashes; source_file_sha256_not_computed"
    ),
    "source_file_hashes_requested": hash_source_files,
    "sample_integrity_note": (
        "Every parsed WOMD protobuf record has an exact serialized-record SHA-256; "
        "AV2 rows and both canonical scene representations are hashed. Source-file "
        "SHA-256 is additionally computed only when HASH_SOURCE_FILES=1. File size "
        "and mtime are reported as provenance metadata, not as cryptographic hashes."
    ),
    "phase_timings": {
        "pytest_elapsed_seconds": float(os.environ.get("PHASE6B_PYTEST_ELAPSED_SECONDS", "0")),
        "womd_elapsed_seconds": 0.0,
    },
}
# Record per-dataset timings separately so the slow reader can be identified.
payload["phase_timings"]["womd_elapsed_seconds"] = payload["womd_validation"]["elapsed_seconds"]
payload["phase_timings"]["av2_elapsed_seconds"] = payload["av2_validation"]["elapsed_seconds"]
all_samples = (
    payload["womd_validation"]["samples"] + payload["av2_validation"]["samples"]
)
payload["content_hash_recorded"] = bool(all_samples) and all(
    row.get("content_sha256") and row.get("scenario_content_sha256")
    for row in all_samples
)
payload["full_source_file_hashes_computed"] = bool(all_samples) and all(
    row.get("source_file_sha256") for row in all_samples
)
payload["integrity_status"] = (
    "FULL_SOURCE_AND_SCENARIO_HASHED" if payload["full_source_file_hashes_computed"]
    else "SCENARIO_HASHED_SOURCE_FILE_HASH_OMITTED" if payload["content_hash_recorded"]
    else "NO_REAL_SCENE_HASHED"
)
statuses = [payload[x]["status"] for x in ("womd_validation", "av2_validation")]
payload["status"] = ("PASS" if all(x == "PASS" for x in statuses)
                     else "ERROR" if "ERROR" in statuses else "SKIP")
(report_dir / "phase6b_acceptance_summary.json").write_text(
    json.dumps(payload, indent=2, sort_keys=True) + "\\n"
)
print(json.dumps(payload, indent=2, sort_keys=True))
PY

"$PYTHON_BIN" "$ROOT/scripts/package_report_phase6b.py" \
  --report "$REPORT_DIR" --output "$ROOT/reports/RAMP-D_Phase6B_server_report.zip"

STATUS="$("$PYTHON_BIN" -c 'import json,sys; print(json.load(open(sys.argv[1]))["status"])' \
  "$REPORT_DIR/phase6b_acceptance_summary.json")"
case "$STATUS" in
  PASS)
    echo "PHASE6B_STATUS=PASS report=$REPORT_DIR"
    ;;
  SKIP)
    echo "PHASE6B_STATUS=SKIP report=$REPORT_DIR (real-data acceptance incomplete)" >&2
    exit 3
    ;;
  *)
    echo "PHASE6B_STATUS=ERROR report=$REPORT_DIR" >&2
    exit 4
    ;;
esac
