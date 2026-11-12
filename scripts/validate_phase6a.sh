#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPORT_DIR="${REPORT_DIR:-$ROOT/reports/phase6a_$(date -u +%Y%m%dT%H%M%SZ)}"
PYTHON_BIN="${PYTHON_BIN:-python}"
DATA_CONFIG="${DATA_CONFIG:-$ROOT/configs/data_sources.example.json}"
mkdir -p "$REPORT_DIR"
export PYTHONPATH="$ROOT/python${PYTHONPATH:+:$PYTHONPATH}"
export PYTEST_DISABLE_PLUGIN_AUTOLOAD="${PYTEST_DISABLE_PLUGIN_AUTOLOAD:-1}"

"$PYTHON_BIN" -m pytest -q "$ROOT/tests/test_phase6_data_audit.py" \
  --junitxml="$REPORT_DIR/phase6a_pytest.xml" | tee "$REPORT_DIR/phase6a_pytest.log"

# Read-only inventory: missing paths and optional readers are recorded as
# SKIP.  --strict is left to the operator after dependency checks.
"$PYTHON_BIN" "$ROOT/scripts/audit_phase6_data.py" \
  --config "$DATA_CONFIG" --output "$REPORT_DIR/dataset_audit.json" \
  | tee "$REPORT_DIR/dataset_audit.log"

"$PYTHON_BIN" - <<'PY' "$REPORT_DIR/phase6a_acceptance_summary.json"
import json, pathlib, sys, xml.etree.ElementTree as ET
p = pathlib.Path(sys.argv[1]).parent
root = ET.parse(p / "phase6a_pytest.xml").getroot()
cases = list(root.iter("testcase"))
counts = {"tests": len(cases), "errors": sum(c.find("error") is not None for c in cases),
          "failures": sum(c.find("failure") is not None for c in cases),
          "skipped": sum(c.find("skipped") is not None for c in cases)}
if counts["errors"] or counts["failures"]:
    raise SystemExit("Phase 6A Python gate failed: " + str(counts))
audit = json.loads((p / "dataset_audit.json").read_text())
summary = {"status": "PHASE6A_LOCAL_PASS", "phase": "6A", "python": counts,
           "dataset_audit_status": audit.get("status"), "read_only_manifest": True,
           "future_leakage_guard": True, "unified_scene_digest": True,
           "record_parser_invoked": False, "real_scene_verified": False,
           "full_support_certified": False, "simulators_used": False,
           "notes": ["SKIP is valid until server paths and optional readers are confirmed"]}
(p / "phase6a_acceptance_summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
print(json.dumps(summary, indent=2, sort_keys=True))
PY

"$PYTHON_BIN" "$ROOT/scripts/package_report_phase6a.py" --report "$REPORT_DIR" \
  --output "$ROOT/reports/RAMP-D_Phase6A_server_report.zip"
echo "PHASE6A_LOCAL_PASS report=$REPORT_DIR"

