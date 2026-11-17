#!/usr/bin/env bash
# A5/1 exact finite audit + mandatory fresh native build and physical bridge replay.
# Acceptance is scoped. Cannot claim A5 full task-winning or full-support safety.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-python}"
BUILD_DIR="${A5_NATIVE_BUILD_DIR:-$ROOT/build_phase6c_a5}"
REPORT_DIR="${REPORT_DIR:-$ROOT/reports/phase6c_a5_$(date -u +%Y%m%dT%H%M%SZ)}"
mkdir -p "$REPORT_DIR"
export PYTHONPATH="$ROOT/python${PYTHONPATH:+:$PYTHONPATH}"
export PYTEST_DISABLE_PLUGIN_AUTOLOAD="${PYTEST_DISABLE_PLUGIN_AUTOLOAD:-1}"
"$PYTHON_BIN" "$ROOT/scripts/verify_release.py" | tee "$REPORT_DIR/release_integrity.log"
"$PYTHON_BIN" -m pytest -q "$ROOT/tests/test_a5_native_discovery.py" \
  "$ROOT/tests/test_phase6c_a5_finite.py" \
  --junitxml="$REPORT_DIR/finite_audit.xml" | tee "$REPORT_DIR/finite_audit.log"
# Always rerun CMake configuration. On this gate, use a distinct build folder;
# no previous build is removed and no source checkout is overwritten.
cmake -S "$ROOT" -B "$BUILD_DIR" -DRAMPD_BUILD_TESTS=ON -DCMAKE_BUILD_TYPE=Release \
  | tee "$REPORT_DIR/cmake_configure.log"
cmake --build "$BUILD_DIR" -j "${A5_BUILD_JOBS:-4}" | tee "$REPORT_DIR/cmake_build.log"
export RAMPD_INTERVAL_LIB="$BUILD_DIR/librampd_interval.so"
"$PYTHON_BIN" "$ROOT/scripts/check_native_ctest.py" "$BUILD_DIR" \
  --log "$REPORT_DIR/native_ctest.log" | tee "$REPORT_DIR/native_summary.json"
"$PYTHON_BIN" -m pytest -q "$ROOT/tests/test_phase6c_a5_bridge.py" \
  "$ROOT/tests/test_phase6c_a5_finite.py" \
  "$ROOT/tests/test_sc_inner.py" \
  "$ROOT/tests/test_sc_a4_proof_audit.py" \
  "$ROOT/tests/test_phase4_protocol.py" \
  "$ROOT/tests/test_phase4_full.py" \
  "$ROOT/tests/test_picard.py" \
  "$ROOT/tests/test_footprint.py" \
  --junitxml="$REPORT_DIR/a5_math_regression.xml" | tee "$REPORT_DIR/a5_math_regression.log"
"$PYTHON_BIN" -m pytest -q "$ROOT/tests" --junitxml="$REPORT_DIR/all_pytest.xml" \
  | tee "$REPORT_DIR/all_pytest.log"
"$PYTHON_BIN" - "$REPORT_DIR" <<'PY'
import json,sys,pathlib
p=pathlib.Path(sys.argv[1])
summary={"phase":"6C-A5/1", "status":"LOCAL_AND_NATIVE_REPLAY_PASS",
         "scope":"FINITE_TASK_MODEL_AND_BOUNDED_SYNTHETIC_PHYSICAL_PROTOCOL_EVIDENCE",
         "real_scene_full_support_certified":False,
         "real_task_terminal_tail_verified":False,
         "model_completeness_outside_declared_toy_world":False,
         "training_complete":False, "datasets_used":False, "simulators_used":False}
(p/'phase6c_a5_acceptance_summary.json').write_text(json.dumps(summary,indent=2)+'\n')
print(json.dumps(summary,indent=2))
PY
echo "A5_1_SCOPED_GATE_PASS report=$REPORT_DIR"
