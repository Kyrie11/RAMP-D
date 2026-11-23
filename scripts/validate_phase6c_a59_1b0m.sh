#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPORT_DIR="${REPORT_DIR:-$ROOT/reports/a59_1b0m_$(date -u +%Y%m%dT%H%M%SZ)}"
[ ! -e "$REPORT_DIR" ] || { echo REFUSE_EXISTING_REPORT_DIR >&2; exit 4; }
mkdir -p "$REPORT_DIR"
export PYTHONPATH="$ROOT/python${PYTHONPATH:+:$PYTHONPATH}"
export PYTEST_DISABLE_PLUGIN_AUTOLOAD=1
STAGE=release
trap 'rc=$?; if [ "$rc" -ne 0 ]; then printf "{\"status\":\"ERROR\",\"stage\":\"%s\",\"exit_code\":%d}\n" "$STAGE" "$rc" > "$REPORT_DIR/a67_acceptance.json"; fi' EXIT
python "$ROOT/scripts/verify_release.py" | tee "$REPORT_DIR/manifest.log"
STAGE=targeted
python -m pytest -q "$ROOT/tests/test_a67_combined_and_byte_binding.py" --junitxml="$REPORT_DIR/targeted.xml" | tee "$REPORT_DIR/targeted.log"
STAGE=full
python -m pytest -q "$ROOT/tests" --junitxml="$REPORT_DIR/full.xml" | tee "$REPORT_DIR/full.log"
STAGE=native
[ -n "${A5_NATIVE_BUILD_DIR:-}" ] && [ -f "${RAMPD_INTERVAL_LIB:-}" ] || { echo NEW_NATIVE_BUILD_REQUIRED >&2; exit 4; }
ctest --test-dir "$A5_NATIVE_BUILD_DIR" --output-on-failure --output-junit "$REPORT_DIR/native.xml" | tee "$REPORT_DIR/native.log"
STAGE=summary
python - "$REPORT_DIR" <<'PY'
import json,pathlib,sys,xml.etree.ElementTree as E
r=pathlib.Path(sys.argv[1]);stats={}
for name in ('targeted','full','native'):
    rt=E.parse(r/(name+'.xml')).getroot()
    suites=[rt] if rt.tag=='testsuite' else rt.findall('testsuite')
    if not suites:raise RuntimeError('MISSING_JUNIT_SUITE:'+name)
    c={k:sum(int(s.get(k,'0')) for s in suites) for k in ('tests','failures','errors','skipped')}
    if any(c[k] for k in ('failures','errors','skipped')):raise RuntimeError('NONZERO_JUNIT_FAILURES:'+name+str(c))
    stats[name]=c
if stats['targeted']['tests']<18 or stats['full']['tests']<833 or stats['native']['tests']!=3:
    raise RuntimeError('INSUFFICIENT_TEST_COVERAGE:'+str(stats))
a={'phase':'6C-A59/1b-0M','status':'CONDITIONAL_A67_SOFTWARE_GATE_PASS',
   'counts':stats,'live_carla_combined_executed_in_this_gate':False,
   'full_hybrid_native_post_certified':False,'dynamic_error_enclosure_certified':False,
   'world_model_and_guard_replayed':False,'terminal_sc_policy_certified':False,
   'all_eight_supervision_sources_certified':False}
(r/'a67_acceptance.json').write_text(json.dumps(a,indent=2)+'\n')
print(json.dumps(a,indent=2))
PY
