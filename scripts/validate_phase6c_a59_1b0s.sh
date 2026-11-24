#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
: "${A5_NATIVE_BUILD_DIR:?require fresh native CMake directory}"
: "${RAMPD_INTERVAL_LIB:?require freshly built MPFR shared library}"
export REPORT_DIR="${REPORT_DIR:-$ROOT/reports/a73_$(date -u +%Y%m%dT%H%M%SZ)}"
[ ! -e "$REPORT_DIR" ] || { echo REFUSE_EXISTING_REPORT_DIR >&2; exit 4; }
bash "$ROOT/scripts/validate_phase6c_a59_1b0r.sh"
export PYTHONPATH="$ROOT/python${PYTHONPATH:+:$PYTHONPATH}" PYTEST_DISABLE_PLUGIN_AUTOLOAD=1
python "$ROOT/scripts/validate_a73_pure.py" --junitxml="$REPORT_DIR/a73_targeted.xml" | tee "$REPORT_DIR/a73_targeted.log"
python "$ROOT/scripts/a73_native_multi_microcase.py" --output-dir "$REPORT_DIR/a73_native_multi"
python - "$REPORT_DIR" <<'PY'
import json,sys,pathlib,xml.etree.ElementTree as ET
p=pathlib.Path(sys.argv[1]); r=json.loads((p/'a73_native_multi/review.json').read_text());x=ET.parse(p/'a73_targeted.xml').getroot();n=[x] if x.tag=='testsuite' else x.findall('testsuite');nt=sum(int(t.get('tests','0')) for t in n)
assert nt>=41 and all(int(t.get(k,'0'))==0 for k in ('errors','failures','skipped') for t in n)
assert r['positive']['status']=='CONDITIONAL_DECLARED_NATIVE_MULTI_ACTOR_GEOMETRY_GUARD_SCREEN' and r['positive']['expected_actor_slabs']==8
assert r['closed_guard']['status']=='UNKNOWN' and any('UNRESOLVED_GUARD' in e for e in r['closed_guard']['reasons'])
result=dict(status='CONDITIONAL_A73_DECLARED_SOFTWARE_NATIVE_GATE_ONLY',targeted_passed=nt,full_sc_certified=False,physical_model_calibrated=False,eight_formal_labels_authorized=False,real_simulators_executed=False)
(p/'a73_acceptance.json').write_text(json.dumps(result,indent=2)+'\n');print(result)
PY
