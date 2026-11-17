#!/usr/bin/env bash
# Hard gate on all actual mathematical modules. The independent finite-game
# oracle can run without MPFR; SC and physical safety replays cannot.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-python}"
REPORT_DIR="${REPORT_DIR:-$ROOT/reports/phase6c_a4_$(date -u +%Y%m%dT%H%M%SZ)}"
mkdir -p "$REPORT_DIR"
export PYTHONPATH="$ROOT/python${PYTHONPATH:+:$PYTHONPATH}"
export PYTEST_DISABLE_PLUGIN_AUTOLOAD="${PYTEST_DISABLE_PLUGIN_AUTOLOAD:-1}"
"$PYTHON_BIN" "$ROOT/scripts/verify_release.py"
"$PYTHON_BIN" -m pytest -q "$ROOT/tests/test_phase6c_a4_finite.py" \
  --junitxml="$REPORT_DIR/independent_finite.xml" | tee "$REPORT_DIR/independent_finite.log"
BUILD_DIR="${NATIVE_BUILD_DIR:-$ROOT/build_phase3}"
if [[ ! -f "$BUILD_DIR/librampd_interval.so" || ! -f "$BUILD_DIR/CTestTestfile.cmake" ]]; then
  printf 'A4_NATIVE_UNAVAILABLE: build the clean CMake tree with tests before acceptance.\n' >&2
  printf 'cmake -S "%s" -B "%s" -DRAMPD_BUILD_TESTS=ON -DCMAKE_BUILD_TYPE=Release\n' "$ROOT" "$BUILD_DIR" >&2
  printf 'cmake --build "%s" -j 4\n' "$BUILD_DIR" >&2
  exit 2
fi
export RAMPD_INTERVAL_LIB="$BUILD_DIR/librampd_interval.so"
"$PYTHON_BIN" "$ROOT/scripts/check_native_ctest.py" "$BUILD_DIR" \
  --log "$REPORT_DIR/native_ctest.log" | tee "$REPORT_DIR/native_summary.json"
"$PYTHON_BIN" -m pytest -q \
  "$ROOT/tests/test_sc_inner.py" \
  "$ROOT/tests/test_sc_a4_proof_audit.py" \
  "$ROOT/tests/test_phase4_full.py" \
  "$ROOT/tests/test_phase4_protocol.py" \
  "$ROOT/tests/test_phase5_cegar.py" \
  "$ROOT/tests/test_picard.py" \
  "$ROOT/tests/test_interval_audit.py" \
  --junitxml="$REPORT_DIR/math_gate_pytest.xml" | tee "$REPORT_DIR/math_gate_pytest.log"
echo "A4_CONDITIONAL_MATH_GATE_PASS (NOT REAL-SCENE FULL-SUPPORT CERTIFICATION) report=$REPORT_DIR"
