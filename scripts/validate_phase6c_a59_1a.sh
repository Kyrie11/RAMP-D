#!/usr/bin/env bash
# Phase 6C-A59/1a: conditional native-resource / exact-model-clock subgate.
# Deliberately NO live CARLA/SUMO, task completion, physics calibration or
# teacher label certification in this gate.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-python}"
REPORT_DIR="${REPORT_DIR:-$ROOT/reports/phase6c_a59_1a_$(date -u +%Y%m%dT%H%M%SZ)}"
if [ -e "$REPORT_DIR" ]; then echo "REVIEW_EXISTING_REPORT_DIR=$REPORT_DIR" >&2; exit 4; fi
mkdir -p "$REPORT_DIR"
export PYTHONPATH="$ROOT/python${PYTHONPATH:+:$PYTHONPATH}"
export PYTEST_DISABLE_PLUGIN_AUTOLOAD="${PYTEST_DISABLE_PLUGIN_AUTOLOAD:-1}"
export A5_NATIVE_BUILD_DIR="${A5_NATIVE_BUILD_DIR:-$ROOT/build_phase6c_a59_0}"
STAGE=release
trap 'rc=$?; if [ "$rc" -ne 0 ]; then printf "{\"phase\":\"6C-A59/1a\",\"status\":\"ERROR\",\"stage\":\"%s\",\"returncode\":%s}\n" "$STAGE" "$rc" > "$REPORT_DIR/phase6c_a59_1a_acceptance.json"; fi' EXIT
"$PYTHON_BIN" "$ROOT/scripts/verify_release.py" | tee "$REPORT_DIR/release.log"
STAGE=incumbent_a59_0
REPORT_DIR="$REPORT_DIR/incumbent_a59_0" bash "$ROOT/scripts/validate_phase6c_a59_0.sh" | tee "$REPORT_DIR/a59_0.log"
export RAMPD_INTERVAL_LIB="$A5_NATIVE_BUILD_DIR/librampd_interval.so"
STAGE=a59_1a_pure
"$PYTHON_BIN" -m pytest -q "$ROOT/tests/test_phase6c_a59_1_pure.py" \
  --junitxml="$REPORT_DIR/a59_1a_pure.xml" | tee "$REPORT_DIR/a59_1a_pure.log"
STAGE=a59_1a_native
"$PYTHON_BIN" -m pytest -q "$ROOT/tests/test_phase6c_a59_1_native.py" \
  --junitxml="$REPORT_DIR/a59_1a_native.xml" | tee "$REPORT_DIR/a59_1a_native.log"
STAGE=full_pytest
"$PYTHON_BIN" -m pytest -q "$ROOT/tests" \
  --junitxml="$REPORT_DIR/full_pytest.xml" | tee "$REPORT_DIR/full_pytest.log"
STAGE=summary
"$PYTHON_BIN" - "$REPORT_DIR" <<'PY'
import json,pathlib,sys,xml.etree.ElementTree as E
root=pathlib.Path(sys.argv[1])
def check(path):
    tree=E.parse(path).getroot()
    suites=[tree] if tree.tag=='testsuite' else tree.findall('testsuite')
    if not suites or any(int(s.get(x,'0')) for s in suites for x in ('errors','failures','skipped')):
        raise SystemExit('fail/skip or empty: '+str(path))
    return sum(int(s.get('tests','0')) for s in suites)
prev=json.loads((root/'incumbent_a59_0'/'phase6c_a59_0_acceptance.json').read_text())
pure=check(root/'a59_1a_pure.xml');native=check(root/'a59_1a_native.xml');full=check(root/'full_pytest.xml')
if prev['status']!='CONDITIONAL_A59_BOUNDARY_TESTS_PASS' or pure<19 or native<4 or full<718:
    raise SystemExit('INSUFFICIENT_A59_1A_REGRESSION_EVIDENCE')
r={'phase':'6C-A59/1a','status':'CONDITIONAL_A59_1A_SUBGATES_PASS',
   'full_pytest':full,'new_pure_tests':pure,'new_native_tests':native,
   'ctest_from_incumbent':prev['native_ctest'],
   'native_resource_post_integrated':True,'clock_exact_model_guard_integrated':True,
   'mid_tick_native_rule_switch_certified':False,
   'general_multiresource_topology_certified':False,
   'protocol_observation_full_support_certified':False,
   'terminal_sc_acceptance_certified':False,
   'carla_actor_metadata_currently_uploaded':False,
   'carla_actual_action_response_measured':False,
   'vehicle_physics_error_envelope_certified':False,
   'real_carla_sumo_synchronization_verified':False,
   'eight_supervision_labels_certified':False}
(root/'phase6c_a59_1a_acceptance.json').write_text(json.dumps(r,indent=2,ensure_ascii=False)+'\n')
print(json.dumps(r,indent=2,ensure_ascii=False))
PY
printf 'A59_1A_CONDITIONAL_GATE_PASS report=%s\n' "$REPORT_DIR"
