#!/usr/bin/env bash
# Strict read-only Phase6B + Phase6C-A2 map smoke. No simulator needed.
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-python3}"
WOMD_ROOT="${WOMD_ROOT:-/data0/senzeyu2/dataset/waymo_open_dataset_motion_v_1_3_1/uncompressed/scenario}"
AV2_ROOT="${AV2_ROOT:-/data0/senzeyu2/dataset/Argoverse2/motion}"
MAX_RECORDS="${MAX_RECORDS:-1}"
MAX_FILES="${MAX_FILES:-3}"
REPORT_DIR="${REPORT_DIR:-$ROOT/reports/phase6b_$(date -u +%Y%m%dT%H%M%SZ)}"
mkdir -p "$REPORT_DIR" "$ROOT/reports"
cd "$ROOT" || exit 4
export PYTHONPATH="$ROOT/python${PYTHONPATH:+:$PYTHONPATH}"
export PYTEST_DISABLE_PLUGIN_AUTOLOAD="${PYTEST_DISABLE_PLUGIN_AUTOLOAD:-1}"

"$PYTHON_BIN" -c 'import sys; assert sys.version_info >= (3,10), "Python 3.10+ required"' \
  || { echo 'PHASE6B_STATUS=ERROR:PYTHON_VERSION'; exit 4; }

"$PYTHON_BIN" scripts/validate_phase6c_a_dependency_free.py \
  --junitxml "$REPORT_DIR/phase6b_pytest.xml" > "$REPORT_DIR/phase6b_pytest.log" 2>&1
TEST_RC=$?
cat "$REPORT_DIR/phase6b_pytest.log"
if [[ $TEST_RC -ne 0 ]]; then
  printf '{"status":"ERROR","reason":"unit tests failed","real_scene_verified":false}\n' > "$REPORT_DIR/phase6b_acceptance_summary.json"
  echo "PHASE6B_STATUS=ERROR report=$REPORT_DIR"
  exit 4
fi

"$PYTHON_BIN" scripts/validate_phase6b_real.py \
  --womd-root "$WOMD_ROOT" --av2-root "$AV2_ROOT" \
  --max-records "$MAX_RECORDS" --max-files "$MAX_FILES" \
  --output "$REPORT_DIR/phase6b_acceptance_summary.json" \
  > "$REPORT_DIR/phase6b_real.log" 2>&1
REAL_RC=$?
cat "$REPORT_DIR/phase6b_real.log"
"$PYTHON_BIN" scripts/package_report_phase6b.py --report "$REPORT_DIR" \
  --output "$ROOT/reports/RAMP-D_Phase6B_server_report.zip" || true
if [[ $REAL_RC -eq 0 ]]; then STATUS=PASS; elif [[ $REAL_RC -eq 3 ]]; then STATUS=SKIP; else STATUS=ERROR; fi
echo "PHASE6B_STATUS=$STATUS report=$REPORT_DIR"
exit "$REAL_RC"
