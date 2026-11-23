#!/usr/bin/env bash
# A59/1b-0I: lane-identity reconciliation and CARLA abort evidence acceptance.
# This script never starts CARLA or edits a running CARLA server.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPORT_DIR="${REPORT_DIR:-$ROOT/reports/phase6c_a59_1b0i_$(date -u +%Y%m%dT%H%M%SZ)}"
[ ! -e "$REPORT_DIR" ] || { echo 'REFUSE_REUSE_REPORT_DIR' >&2; exit 4; }
mkdir -p "$REPORT_DIR"
export PYTHONPATH="$ROOT/python${PYTHONPATH:+:$PYTHONPATH}"
export PYTEST_DISABLE_PLUGIN_AUTOLOAD="${PYTEST_DISABLE_PLUGIN_AUTOLOAD:-1}"
STAGE=release
trap 'rc=$?; if [ "$rc" -ne 0 ]; then printf "{\"status\":\"ERROR\",\"failed_stage\":\"%s\",\"exit_code\":%d}\n" "$STAGE" "$rc" > "$REPORT_DIR/acceptance_a59_1b0i.json"; fi' EXIT
python "$ROOT/scripts/verify_release.py" | tee "$REPORT_DIR/release.log"
STAGE=targeted
python -m pytest -q "$ROOT/tests/test_a63_start_lane_contract.py" \
  "$ROOT/tests/test_a60_site_audit.py" "$ROOT/tests/test_a62_carla_readiness.py" \
  --junitxml="$REPORT_DIR/targeted.xml" | tee "$REPORT_DIR/targeted.log"
STAGE=full
python -m pytest -q "$ROOT/tests" --junitxml="$REPORT_DIR/full.xml" | tee "$REPORT_DIR/full.log"
STAGE=native
if [ -z "${A5_NATIVE_BUILD_DIR:-}" ]; then
  echo 'REVIEW_MISSING_NATIVE_BUILD_DIR: freshly configure the build first' >&2
  exit 4
fi
ctest --test-dir "$A5_NATIVE_BUILD_DIR" --output-on-failure | tee "$REPORT_DIR/native.log"
STAGE=summary
python - "$REPORT_DIR" <<'PY'
import json,pathlib,sys,xml.etree.ElementTree as ET
r=pathlib.Path(sys.argv[1])
def count(path):
    x=ET.parse(path).getroot(); a=[x] if x.tag=='testsuite' else x.findall('testsuite')
    if not a or any(int(s.get(k,'0'))>0 for s in a for k in ('skipped','errors','failures')):
        raise SystemExit('NO_ACCEPTANCE_IF_SKIPPED_FAILED_OR_ERRORED')
    return sum(int(s.get('tests','0')) for s in a)
targeted=count(r/'targeted.xml');full=count(r/'full.xml')
if targeted<24 or full<764:raise SystemExit('INSUFFICIENT_A59_1B0I_COVERAGE')
output={'phase':'6C-A59/1b-0I','status':'CONDITIONAL_START_LANE_SELECTION_TESTS_PASS',
  'targeted_tests':targeted,'full_tests':full,'native_ctest_expected':3,
  'live_carla_start_lane_accepted':False,'grounding_and_actuators_calibrated':False,
  'hybrid_native_picard_post_certified':False,
  'sc_certified':False,'eight_supervision_labels_certified':False}
(r/'acceptance_a59_1b0i.json').write_text(json.dumps(output,indent=2)+'\n')
print(json.dumps(output,indent=2))
PY
