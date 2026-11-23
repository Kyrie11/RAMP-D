#!/usr/bin/env bash
# A59/1b-0J: release, zero-skip Python, 3 native CTests, independent JUnit.
# No CARLA world is accessed or modified by this acceptance script.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPORT_DIR="${REPORT_DIR:-$ROOT/reports/phase6c_a59_1b0j_$(date -u +%Y%m%dT%H%M%SZ)}"
[ ! -e "$REPORT_DIR" ] || { echo REFUSE_EXISTING_REPORT_DIR >&2; exit 4; }
mkdir -p "$REPORT_DIR"
export PYTHONPATH="$ROOT/python${PYTHONPATH:+:$PYTHONPATH}"
export PYTEST_DISABLE_PLUGIN_AUTOLOAD=1
PHASE=release
trap 'rc=$?; if [ "$rc" -ne 0 ]; then printf "{\"status\":\"ERROR\",\"failed_stage\":\"%s\",\"exit_code\":%d}\n" "$PHASE" "$rc" > "$REPORT_DIR/acceptance_a59_1b0j.json"; fi' EXIT
python "$ROOT/scripts/verify_release.py" | tee "$REPORT_DIR/release.log"
PHASE=targeted
python -m pytest -q "$ROOT/tests/test_a64_smoke_and_handoff.py" \
  --junitxml="$REPORT_DIR/targeted.xml" | tee "$REPORT_DIR/targeted.log"
PHASE=full
python -m pytest -q "$ROOT/tests" --junitxml="$REPORT_DIR/full.xml" | tee "$REPORT_DIR/full.log"
PHASE=native
[ -n "${A5_NATIVE_BUILD_DIR:-}" ] || { echo MISSING_FRESH_NATIVE_BUILD_DIR >&2; exit 4; }
[ -f "${RAMPD_INTERVAL_LIB:-}" ] || { echo MISSING_NATIVE_MPFR_BACKEND >&2; exit 4; }
ctest --test-dir "$A5_NATIVE_BUILD_DIR" --output-on-failure --output-junit "$REPORT_DIR/native.xml" | tee "$REPORT_DIR/native.log"
PHASE=summary
python - "$REPORT_DIR" <<'PY'
import json,pathlib,sys,xml.etree.ElementTree as ET
r=pathlib.Path(sys.argv[1])
def count(filename):
    root=ET.parse(r/filename).getroot()
    suites=([root] if root.tag=='testsuite' else list(root.findall('testsuite')))
    if not suites:raise RuntimeError('INVALID_JUNIT:'+filename)
    vals={k:sum(int(s.get(k,'0')) for s in suites) for k in ('tests','skipped','failures','errors')}
    if any(vals[k] for k in ('skipped','failures','errors')):
        raise RuntimeError('NO_ACCEPTANCE_WITH_FAILURES_OR_SKIPS:'+filename+str(vals))
    return vals['tests']
counts={k:count(k+'.xml') for k in ('targeted','full','native')}
if counts['targeted']<12 or counts['full']<776 or counts['native']!=3:
    raise RuntimeError('INSUFFICIENT_COVERAGE:'+str(counts))
a={'phase':'6C-A59/1b-0J','status':'CONDITIONAL_CONTROL_SMOKE_AND_SLAB_HANDOFF_TESTS_PASS',
   **counts,'target_server_live_carla_control_trial_performed':False,
   'validated_physical_error_enclosure':False,'mixed_native_picard_post_certified':False,
   'goal_conditioned_sc_certified':False,'eight_supervision_labels_certified':False}
(r/'acceptance_a59_1b0j.json').write_text(json.dumps(a,indent=2)+'\n')
print(json.dumps(a,indent=2))
PY
