#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPORT_DIR="${REPORT_DIR:-$ROOT/reports/phase4_$(date -u +%Y%m%dT%H%M%SZ)}"
mkdir -p "$REPORT_DIR"
PYTHON_BIN="${PYTHON_BIN:-python}"

export PYTHONPATH="$ROOT/python${PYTHONPATH:+:$PYTHONPATH}"
export PYTEST_DISABLE_PLUGIN_AUTOLOAD="${PYTEST_DISABLE_PLUGIN_AUTOLOAD:-1}"
if [[ -z "${RAMPD_INTERVAL_LIB:-}" && -f "$ROOT/build_phase3/librampd_interval.so" ]]; then
  export RAMPD_INTERVAL_LIB="$ROOT/build_phase3/librampd_interval.so"
fi

# A fresh Phase 4 checkout may not yet have the native Phase 1D library.  Run
# the historical Phase 0--3 gate once in that case, then continue with the
# Phase 4 superset checks.  All CMake arguments are forwarded unchanged.
if [[ -z "${RAMPD_INTERVAL_LIB:-}" || ! -f "$RAMPD_INTERVAL_LIB" ]]; then
  bash "$ROOT/scripts/validate_phase3.sh" "$@"
  export RAMPD_INTERVAL_LIB="$ROOT/build_phase3/librampd_interval.so"
fi

if [[ ! -f "$ROOT/build_phase3/CTestTestfile.cmake" ]]; then
  echo "native CTest manifest missing: $ROOT/build_phase3/CTestTestfile.cmake" >&2
  exit 1
fi
ctest --test-dir "$ROOT/build_phase3" --output-on-failure \
  | tee "$REPORT_DIR/phase4_ctest.log"
if ! grep -Eq '([0-9]+) tests passed|100% tests passed' "$REPORT_DIR/phase4_ctest.log"; then
  echo "native CTest gate produced no passing-test summary" >&2
  exit 1
fi

"$PYTHON_BIN" -m pytest -q "$ROOT/tests" \
  --junitxml="$REPORT_DIR/all_pytest.xml" | tee "$REPORT_DIR/all_pytest.log"

"$PYTHON_BIN" -m pytest -q \
  "$ROOT/tests/test_phase4_protocol.py" "$ROOT/tests/test_phase4_full.py" \
  "$ROOT/tests/test_forecast_adapter.py" \
  --junitxml="$REPORT_DIR/phase4_pytest.xml" | tee "$REPORT_DIR/phase4_pytest.log"

"$PYTHON_BIN" - <<'PY' | tee "$REPORT_DIR/phase4_examples.json"
import json
from rampd_core.phase4_examples import run_examples
print(json.dumps(run_examples(), sort_keys=True, indent=2))
PY

"$PYTHON_BIN" - <<'PY' "$REPORT_DIR/phase4_acceptance_summary.json"
import json, pathlib
from rampd_core.phase4_examples import run_examples
out = run_examples()
summary = {
    "status": "PHASE4_LOCAL_PASS",
    "scope": "PHASE4_EXPLICIT_PROTOCOL_SUPPORT",
    "phase3_regression_included": True,
    "three_valued_examples": {k: out[k]["status"] for k in ("certified", "counterexample", "unknown")},
    "resource_probe": out["interfaces"],
    "certified_fixture": out["certified"]["status"] == "CERTIFIED",
    "full_support_certified": False,
    "current_scene_verified": False,
    "real_datasets_used": False,
    "simulators_used": False,
    "tex_bib_required": False,
}
pathlib.Path(__import__('sys').argv[1]).write_text(json.dumps(summary, indent=2, sort_keys=True)+"\n")
PY

echo "PHASE4_LOCAL_PASS report=$REPORT_DIR"
