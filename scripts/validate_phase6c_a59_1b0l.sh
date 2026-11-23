#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPORT_DIR="${REPORT_DIR:-$ROOT/reports/phase6c_a59_1b0l_$(date -u +%Y%m%dT%H%M%SZ)}"
[ ! -e "$REPORT_DIR" ] || { echo REFUSE_EXISTING_REPORT_DIR >&2; exit 4; }
mkdir -p "$REPORT_DIR"
export PYTHONPATH="$ROOT/python${PYTHONPATH:+:$PYTHONPATH}"
export PYTEST_DISABLE_PLUGIN_AUTOLOAD=1
PHASE=release
trap 'rc=$?; if [ "$rc" -ne 0 ]; then printf "{\"status\":\"ERROR\",\"stage\":\"%s\",\"exit_code\":%d}\n" "$PHASE" "$rc" > "$REPORT_DIR/a66_acceptance.json"; fi' EXIT
python "$ROOT/scripts/verify_release.py" | tee "$REPORT_DIR/release.log"
PHASE=targeted
python -m pytest -q "$ROOT/tests/test_a66_carla_and_hybrid.py" "$ROOT/tests/test_a66_cosim_clock_contract.py" "$ROOT/tests/test_a66_inventory.py" --junitxml="$REPORT_DIR/targeted.xml" | tee "$REPORT_DIR/targeted.log"
PHASE=full
python -m pytest -q "$ROOT/tests" --junitxml="$REPORT_DIR/full.xml" | tee "$REPORT_DIR/full.log"
PHASE=native
[ -n "${A5_NATIVE_BUILD_DIR:-}" ] || { echo MISSING_NATIVE_BUILD_DIR >&2; exit 4; }
[ -f "${RAMPD_INTERVAL_LIB:-}" ] || { echo MISSING_NATIVE_BACKEND >&2; exit 4; }
ctest --test-dir "$A5_NATIVE_BUILD_DIR" --output-on-failure --output-junit "$REPORT_DIR/native.xml" | tee "$REPORT_DIR/native.log"
PHASE=summary
python - "$REPORT_DIR" <<'PY'
import json,pathlib,sys,xml.etree.ElementTree as E
r=pathlib.Path(sys.argv[1])
def count(name):
    rt=E.parse(r/(name+'.xml')).getroot()
    suites=[rt] if rt.tag=='testsuite' else rt.findall('testsuite')
    if not suites:raise RuntimeError('NO_JUNIT_SUITES:'+name)
    out={k:sum(int(s.get(k,'0')) for s in suites) for k in ('tests','errors','failures','skipped')}
    if any(out[k] for k in ('errors','failures','skipped')):
        raise RuntimeError('FAILURES_OR_SKIPS:'+name+str(out))
    return out['tests']
res={k:count(k) for k in ('targeted','full','native')}
if res['targeted']<31 or res['full']<815 or res['native']!=3:
    raise RuntimeError('INSUFFICIENT_TEST_COVERAGE:'+str(res))
a={'phase':'6C-A59/1b-0L','status':'CONDITIONAL_A66_SOFTWARE_AND_CARLA_STEERING_DESCRIPTIVE_GATE_PASS',
   **res,'live_carla_steering_test_executed_here':False,
   'combined_trial_supplied_in_user_upload':False,
   'real_sumo_carla_cosim_executed_here':False,
   'validated_dynamic_error_enclosure':False,'full_mixed_native_post':False,
   'goal_conditioned_sc_certified':False,'eight_supervision_sources_certified':False}
(r/'a66_acceptance.json').write_text(json.dumps(a,indent=2)+'\n')
print(json.dumps(a,indent=2))
PY
