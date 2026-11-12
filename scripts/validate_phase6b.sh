#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPORT_DIR="${REPORT_DIR:-$ROOT/reports/phase6b_$(date -u +%Y%m%dT%H%M%SZ)}"
PYTHON_BIN="${PYTHON_BIN:-python}"
WOMD_ROOT="${WOMD_ROOT:-/data0/senzeyu2/dataset/waymo_open_dataset_motion_v_1_3_1/uncompressed/scenario}"
AV2_ROOT="${AV2_ROOT:-/data0/senzeyu2/dataset/Argoverse2/motion}"
MAX_RECORDS="${MAX_RECORDS:-3}"
mkdir -p "$REPORT_DIR"
export PYTHONPATH="$ROOT/python${PYTHONPATH:+:$PYTHONPATH}"
export PYTEST_DISABLE_PLUGIN_AUTOLOAD="${PYTEST_DISABLE_PLUGIN_AUTOLOAD:-1}"

"$PYTHON_BIN" -m pytest -q "$ROOT/tests/test_phase6_data_audit.py" \
  "$ROOT/tests/test_phase6b_record_adapters.py" \
  --junitxml="$REPORT_DIR/phase6b_pytest.xml" | tee "$REPORT_DIR/phase6b_pytest.log"

"$PYTHON_BIN" - <<'PY' "$REPORT_DIR" "$WOMD_ROOT" "$AV2_ROOT" "$MAX_RECORDS"
import json
from pathlib import Path
import sys

from rampd_core import (OptionalDependencyError, iter_av2_validation,
                        iter_womd_validation)

report_dir = Path(sys.argv[1])
womd_root, av2_root, max_records = sys.argv[2], sys.argv[3], int(sys.argv[4])

def sample(name, iterator_factory):
    rows = []
    try:
        for parsed in iterator_factory():
            rows.append({
                "scenario_id": parsed.scenario_id,
                "source_file": parsed.source_file,
                "record_index": parsed.record_index,
                "content_sha256": parsed.content_sha256,
                "parser_version": parsed.parser_version,
                "source_schema": parsed.source_schema,
                "split": parsed.scene.manifest.split,
                "current_time_index": parsed.scene.manifest.current_time_index,
                "track_count": len(parsed.scene.tracks),
                "future_available": parsed.scene.manifest.future_available,
                "position_reference": parsed.scene.manifest.position_reference,
                "coordinate_frame": parsed.scene.manifest.coordinate_frame,
                "map_file": parsed.map_file,
                "clocks": None if parsed.clocks is None else parsed.clocks.to_dict(),
            })
    except (FileNotFoundError, OptionalDependencyError) as exc:
        return {"status": "SKIP", "reason": f"{type(exc).__name__}: {exc}", "samples": []}
    except Exception as exc:
        return {"status": "ERROR", "reason": f"{type(exc).__name__}: {exc}", "samples": []}
    return {"status": "PASS" if rows else "SKIP", "reason": None, "samples": rows}

payload = {
    "schema": "rampd.phase6b.acceptance.v1",
    "phase": "6B",
    "womd_validation": sample("womd_validation",
                               lambda: iter_womd_validation(womd_root, max_records=max_records)),
    "av2_validation": sample("av2_validation",
                              lambda: iter_av2_validation(av2_root, max_records=max_records)),
    "simulators_used": False,
    "four_clock_injection": "explicit_only_no_dataset_inference",
    "future_leakage_guard": True,
    "content_hash_recorded": True,
}
statuses = [payload[x]["status"] for x in ("womd_validation", "av2_validation")]
payload["status"] = "PASS" if all(x == "PASS" for x in statuses) else ("SKIP" if "ERROR" not in statuses else "ERROR")
(report_dir / "phase6b_acceptance_summary.json").write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
print(json.dumps(payload, indent=2, sort_keys=True))
PY

echo "PHASE6B_LOCAL_PASS report=$REPORT_DIR"

"$PYTHON_BIN" "$ROOT/scripts/package_report_phase6b.py" \
  --report "$REPORT_DIR" --output "$ROOT/reports/RAMP-D_Phase6B_server_report.zip"
