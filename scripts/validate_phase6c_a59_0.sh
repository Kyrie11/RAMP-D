#!/usr/bin/env bash
# A59/0 dependency-gated acceptance. Does NOT run CARLA, SUMO or certify SC.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-python}"
REPORT_DIR="${REPORT_DIR:-$ROOT/reports/phase6c_a59_0_$(date -u +%Y%m%dT%H%M%SZ)}"
mkdir -p "$REPORT_DIR"
export PYTHONPATH="$ROOT/python${PYTHONPATH:+:$PYTHONPATH}"
export PYTEST_DISABLE_PLUGIN_AUTOLOAD="${PYTEST_DISABLE_PLUGIN_AUTOLOAD:-1}"
export A5_NATIVE_BUILD_DIR="${A5_NATIVE_BUILD_DIR:-$ROOT/build_phase6c_a59_0}"
STAGE=release
trap 'rc=$?; if [ "$rc" -ne 0 ]; then printf "{\"phase\":\"6C-A59/0\",\"status\":\"ERROR\",\"stage\":\"%s\",\"returncode\":%s}\n" "$STAGE" "$rc" > "$REPORT_DIR/phase6c_a59_0_acceptance.json"; fi' EXIT
"$PYTHON_BIN" "$ROOT/scripts/verify_release.py" | tee "$REPORT_DIR/release.log"
STAGE=incumbent_a58_math
REPORT_DIR="$REPORT_DIR/incumbent_a58" bash "$ROOT/scripts/validate_phase6c_a5_3b8.sh" | tee "$REPORT_DIR/a58.log"
STAGE=a59_pure
"$PYTHON_BIN" "$ROOT/scripts/validate_a59_pure.py" --junitxml="$REPORT_DIR/a59_pure.xml" | tee "$REPORT_DIR/a59_pure.log"
STAGE=a59_native
export RAMPD_INTERVAL_LIB="$A5_NATIVE_BUILD_DIR/librampd_interval.so"
"$PYTHON_BIN" -m pytest -q "$ROOT/tests/test_phase6c_a59_native.py" \
  --junitxml="$REPORT_DIR/a59_native.xml" | tee "$REPORT_DIR/a59_native.log"
STAGE=summary
"$PYTHON_BIN" - "$REPORT_DIR" <<'PY'
import json,sys,pathlib,xml.etree.ElementTree as E
p=pathlib.Path(sys.argv[1])
def count(f):
    root=E.parse(f).getroot();ss=[root] if root.tag=='testsuite' else root.findall('testsuite')
    if not ss or any(int(s.get(k,'0')) for s in ss for k in ('errors','failures','skipped')):
        raise SystemExit('failed/skipped or missing suite: '+str(f))
    return sum(int(s.get('tests','0')) for s in ss)
a58=json.loads((p/'incumbent_a58'/'phase6c_a5_3b8_acceptance.json').read_text())
n=count(p/'a59_native.xml');q=count(p/'a59_pure.xml')
if a58.get('status')!='CONDITIONAL_LOCAL_OBLIGATIONS_PASS' or n<5 or q<11 or a58['base_server_suite']['all_pytest']<695:
    raise SystemExit('A59/0 conditional base or new regression gate incomplete')
out={'phase':'6C-A59/0','status':'CONDITIONAL_A59_BOUNDARY_TESTS_PASS',
     'a58_verified':True,'a59_native_tests':n,'a59_pure_tests':q,
     'all_python_tests_in_base':a58['base_server_suite']['all_pytest'],
     'native_ctest':a58['native_ctest'],
     'native_physical_post_sc_candidate_bridge_tested':True,
     'complete_protocol_observation_verified':False,
     'general_resource_entry_stay_exit_verified':False,
     'task_terminal_tail_sc_certified':False,
     'carla_sumo_live_sync_verified':False,
     'eight_supervision_labels_authorized':False,
     'model_reality_conformance_verified':False}
(p/'phase6c_a59_0_acceptance.json').write_text(json.dumps(out,indent=2)+'\n')
print(json.dumps(out,indent=2))
PY
printf 'A59_0_CONDITIONAL_GATE_PASS report=%s\n' "$REPORT_DIR"
