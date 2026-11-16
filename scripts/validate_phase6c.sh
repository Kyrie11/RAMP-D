#!/usr/bin/env bash
# Phase6C: goal -> implementation -> tests -> failure analysis -> report.
# A skipped parser or simulator is NEVER a full Phase 6C PASS.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPORT_DIR="${REPORT_DIR:-$ROOT/reports/phase6c_$(date -u +%Y%m%dT%H%M%SZ)}"
PYTHON_BIN="${PYTHON_BIN:-python}"
WOMD_ROOT="${WOMD_ROOT:-/data0/senzeyu2/dataset/waymo_open_dataset_motion_v_1_3_1/uncompressed/scenario}"
AV2_ROOT="${AV2_ROOT:-/data0/senzeyu2/dataset/Argoverse2/motion}"
MAX_RECORDS="${MAX_RECORDS:-2}"
mkdir -p "$REPORT_DIR"
export PYTHONPATH="$ROOT/python${PYTHONPATH:+:$PYTHONPATH}"
export PYTEST_DISABLE_PLUGIN_AUTOLOAD="${PYTEST_DISABLE_PLUGIN_AUTOLOAD:-1}"

# The standard import path requires native MPFR; its absence is a regression
# blocker, not a reason to claim the full tests passed.
if [[ -z "${RAMPD_INTERVAL_LIB:-}" && -f "$ROOT/build_phase3/librampd_interval.so" ]]; then
  export RAMPD_INTERVAL_LIB="$ROOT/build_phase3/librampd_interval.so"
fi
set +e
"$PYTHON_BIN" -m pytest -q \
  "$ROOT/tests/test_phase6_data_audit.py" \
  "$ROOT/tests/test_phase6b_record_adapters.py" \
  "$ROOT/tests/test_phase6c.py" \
  --junitxml="$REPORT_DIR/phase6c_pytest.xml" \
  > "$REPORT_DIR/phase6c_pytest.log" 2>&1
TEST_RC=$?
# Full historical Python/MPFR and native CTest regression: part of acceptance
# (not replaced by 6C's isolated synthetic tests).
if [[ "${RUN_FULL_REGRESSION:-1}" == "1" ]]; then
  "$PYTHON_BIN" -m pytest -q "$ROOT/tests" \
    --junitxml="$REPORT_DIR/all_pytest.xml" \
    > "$REPORT_DIR/all_pytest.log" 2>&1
  FULL_RC=$?
  if [[ -f "$ROOT/build_phase3/CTestTestfile.cmake" ]]; then
    ctest --test-dir "$ROOT/build_phase3" --output-on-failure \
      > "$REPORT_DIR/native_ctest.log" 2>&1
    NATIVE_RC=$?
  else
    NATIVE_RC=2
    echo "SKIP: missing built CTest native regression manifest" > "$REPORT_DIR/native_ctest.log"
  fi
else
  FULL_RC=2; NATIVE_RC=2
  echo "SKIP: RUN_FULL_REGRESSION=0" > "$REPORT_DIR/all_pytest.log"
  echo "SKIP: RUN_FULL_REGRESSION=0" > "$REPORT_DIR/native_ctest.log"
fi
"$PYTHON_BIN" "$ROOT/scripts/evaluate_phase6c.py" \
  --womd-root "$WOMD_ROOT" --av2-root "$AV2_ROOT" \
  --max-records "$MAX_RECORDS" \
  --output "$REPORT_DIR/phase6c_dataset_gate.json" \
  > "$REPORT_DIR/phase6c_dataset_gate.log" 2>&1
DATA_RC=$?
if [[ -n "${CARLA_COSIM_DIR:-}" && -n "${SUMO_CONFIG:-}" ]]; then
  "$PYTHON_BIN" "$ROOT/scripts/smoke_phase6c_cosim.py" \
    --carla-cosim-dir "$CARLA_COSIM_DIR" \
    --sumo-config "$SUMO_CONFIG" \
    --expected-carla-map "${CARLA_MAP:-}" \
    --tls-manager "${TLS_MANAGER:-sumo}" \
    --steps "${COSIM_STEPS:-20}" --step-length "${SIM_DT:-0.05}" \
    --output "$REPORT_DIR/phase6c_cosim_smoke.json" \
    > "$REPORT_DIR/phase6c_cosim.log" 2>&1
  SIM_RC=$?
else
  SIM_RC=2
  printf '{"schema":"rampd.phase6c.cosim-clock-ledger.v1","status":"SKIP","reason":"SUMO_CONFIG and CARLA_COSIM_DIR not both provided; simulator not launched"}\n' > "$REPORT_DIR/phase6c_cosim_smoke.json"
fi
set -e
"$PYTHON_BIN" - <<'PY' "$REPORT_DIR" "$TEST_RC" "$DATA_RC" "$SIM_RC" "$FULL_RC" "$NATIVE_RC"
import json,sys
from pathlib import Path
root=Path(sys.argv[1]); test_rc,data_rc,sim_rc,full_rc,native_rc=map(int,sys.argv[2:])
def read_status(filename):
    p=root/filename
    if not p.exists(): return 'ERROR'
    try: return json.loads(p.read_text()).get('status','ERROR')
    except Exception: return 'ERROR'
data=read_status('phase6c_dataset_gate.json')
sim=read_status('phase6c_cosim_smoke.json')
all_pass=(test_rc==0 and full_rc==0 and native_rc==0 and data_rc==0
          and sim_rc==0 and data=='PASS' and sim=='PASS')
# pytest RC=2 means INTERRUPTED/COLLECTION_ERROR, never a benign SKIP.
full_enabled=__import__('os').environ.get('RUN_FULL_REGRESSION','1')=='1'
failed_test=(test_rc!=0 or (full_enabled and full_rc!=0))
status=('PASS' if all_pass else
        'ERROR' if failed_test or native_rc not in (0,2) or data=='ERROR' or
        (data_rc not in (0,2)) or sim=='ERROR' or sim_rc not in (0,2)
        else 'SKIP')
result={'schema':'rampd.phase6c.acceptance.v1', 'phase':'6C',
        'status':status, 'python_tests_exit_code':test_rc,
        'full_python_regression_exit_code':full_rc,
        'full_regression_requested':full_enabled,
        'native_ctest_exit_code':native_rc,
        'phase6c_fully_implemented':False,
        'acceptance_scope':'BOUNDED_DATASET_PREDICTOR_AND_COSIM_SMOKE_ONLY',
        'dataset_gate_exit_code':data_rc,'dataset_status':data,
        'cosim_exit_code':sim_rc,'cosim_status':sim,
        'full_support_certified':False, 'task_winning_certified':False,
        'model_trained':False,'rulenet_trained':False,
        'real_scene_closed_loop_planning_certified':False,
        'scope':'real-dataset CV-baseline + soft-rank API + CARLA/SUMO clock smoke (when available)'}
(root/'phase6c_acceptance_summary.json').write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
print(json.dumps(result,indent=2,sort_keys=True))
PY
"$PYTHON_BIN" "$ROOT/scripts/package_report_phase6b.py" \
  --report "$REPORT_DIR" --output "$ROOT/reports/RAMP-D_Phase6C_server_report.zip"
if [[ "$TEST_RC" -ne 0 || "$DATA_RC" -ne 0 || "$SIM_RC" -ne 0 || "$FULL_RC" -ne 0 || "$NATIVE_RC" -ne 0 ]]; then
  echo "PHASE6C_NOT_FULLY_ACCEPTED report=$ROOT/reports/RAMP-D_Phase6C_server_report.zip" >&2
  exit 2
fi
echo "PHASE6C_SMOKE_PASS_NOT_FORMAL_CERTIFICATION report=$ROOT/reports/RAMP-D_Phase6C_server_report.zip"
