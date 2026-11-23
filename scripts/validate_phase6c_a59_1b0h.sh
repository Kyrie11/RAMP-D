#!/usr/bin/env bash
# A59/1b-0H fail-closed CARLA readiness and hybrid evidence-table acceptance.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPORT_DIR="${REPORT_DIR:-$ROOT/reports/phase6c_a59_1b0h_$(date -u +%Y%m%dT%H%M%SZ)}"
[ ! -e "$REPORT_DIR" ] || { echo "REFUSE_REUSE_REPORT_DIR" >&2; exit 4; }
mkdir -p "$REPORT_DIR"
export PYTHONPATH="$ROOT/python${PYTHONPATH:+:$PYTHONPATH}"
export PYTEST_DISABLE_PLUGIN_AUTOLOAD="${PYTEST_DISABLE_PLUGIN_AUTOLOAD:-1}"
STAGE=release
trap 'rc=$?; if [ "$rc" -ne 0 ]; then printf "{\"status\":\"ERROR\",\"failed_stage\":\"%s\",\"exit_code\":%d}\n" "$STAGE" "$rc" > "$REPORT_DIR/acceptance_a59_1b0h.json"; fi' EXIT
python "$ROOT/scripts/verify_release.py" | tee "$REPORT_DIR/release.log"
STAGE=hotfix_tests
python -m pytest -q "$ROOT/tests/test_a62_carla_readiness.py" "$ROOT/tests/test_a62_hybrid_obligation_ledger.py" \
   --junitxml="$REPORT_DIR/hotfix.xml" | tee "$REPORT_DIR/hotfix.log"
STAGE=full_pytest
python -m pytest -q "$ROOT/tests" --junitxml="$REPORT_DIR/full.xml" | tee "$REPORT_DIR/full.log"
STAGE=native
if [ -z "${A5_NATIVE_BUILD_DIR:-}" ]; then
  echo 'REVIEW_MISSING_NATIVE_BUILD_DIR (specify a freshly configured native build)' > "$REPORT_DIR/native.log"
  exit 4
fi
ctest --test-dir "$A5_NATIVE_BUILD_DIR" --output-on-failure | tee "$REPORT_DIR/native.log"
STAGE=uploaded_smoke_independent_review
if [ -n "${A62_PREVIOUS_SMOKE_JSON:-}" ]; then
  # The user's existing failed experiment is a *negative test* expected to
  # result in REVIEW / exit 4. A PASS here would indicate false acceptance.
  set +e
  python "$ROOT/scripts/a62_review_carla_readiness.py" --input "$A62_PREVIOUS_SMOKE_JSON" \
     --output "$REPORT_DIR/previous_smoke_review.json" > "$REPORT_DIR/previous_smoke_stdout.log" 2>&1
  rc=$?
  set -e
  [ "$rc" -eq 4 ] || { echo "FAILED_NEGATIVE_SMOKE_GATE exit=$rc" >&2; exit 4; }
  python - "$REPORT_DIR/previous_smoke_review.json" <<'PY'
import json,sys
x=json.load(open(sys.argv[1]))
assert x['status']=='REVIEW' and x['physical_certified'] is False
assert x['actuator_calibrated'] is False
PY
fi
STAGE=summary
python - "$REPORT_DIR" <<'PY'
import json,pathlib,sys,xml.etree.ElementTree as ET
r=pathlib.Path(sys.argv[1])
def count(path):
    x=ET.parse(path).getroot(); suites=[x] if x.tag=='testsuite' else x.findall('testsuite')
    if not suites or any(int(s.get(k,'0')) for s in suites for k in ('skipped','errors','failures')):
        raise SystemExit('NO_ACCEPTANCE_FROMSKIPPED_OR_FAILED_TESTS')
    return sum(int(s.get('tests','0')) for s in suites)
hotfix=count(r/'hotfix.xml');full=count(r/'full.xml')
if hotfix<18 or full<758:raise SystemExit('INSUFFICIENT_REGRESSION_COVERAGE')
x={'phase':'6C-A59/1b-0H','status':'CONDITIONAL_READINESS_AND_OBLIGATION_LEDGER_TESTS_PASS',
   'full_pytest':full,'new_targeted_tests':hotfix,'native_ctest':3,
   'uploaded_smoke_known_failure_rejected':(r/'previous_smoke_review.json').exists(),
   'live_carla_new_capture_executed_by_this_script':False,
   'native_segmented_picard_post_certified':False,'full_sc_task_tail_certified':False,
   'calibrated_vehicle_error_envelope':False,'eight_supervision_heads_certified':False}
(r/'acceptance_a59_1b0h.json').write_text(json.dumps(x,indent=2)+'\n')
print(json.dumps(x,indent=2))
PY
