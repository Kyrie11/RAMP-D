#!/usr/bin/env bash
# A72 release: all A71 gates incl NEW Native + exact clock polygon + targeted.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
: "${A5_NATIVE_BUILD_DIR:?require fresh native CMake directory}"
: "${RAMPD_INTERVAL_LIB:?require freshly built MPFR shared library}"
export REPORT_DIR="${REPORT_DIR:-$ROOT/reports/a72_$(date -u +%Y%m%dT%H%M%SZ)}"
[ ! -e "$REPORT_DIR" ] || { echo REFUSE_EXISTING_REPORT_DIR >&2; exit 4; }
bash "$ROOT/scripts/validate_phase6c_a59_1b0q.sh"
export PYTHONPATH="$ROOT/python${PYTHONPATH:+:$PYTHONPATH}"
export PYTEST_DISABLE_PLUGIN_AUTOLOAD=1
python -m pytest -q "$ROOT/tests/test_a72_convergence.py" --junitxml="$REPORT_DIR/a72_targeted.xml" \
   | tee "$REPORT_DIR/a72_targeted.log"
python "$ROOT/scripts/a72_replay_native_clock_polygon.py" \
  --native-dir "$REPORT_DIR/native_microcase" \
  --resource-file "$ROOT/configs/a71_declared_microcase_far_polygons.json" \
  --output "$REPORT_DIR/a72_native_clock_far.json"
set +e
python "$ROOT/scripts/a72_replay_native_clock_polygon.py" \
  --native-dir "$REPORT_DIR/native_microcase" \
  --resource-file "$ROOT/configs/a71_declared_microcase_near_polygons.json" \
  --output "$REPORT_DIR/a72_native_clock_near.json"
near_rc=$?
set -e
python - "$REPORT_DIR" "$near_rc" <<'PY'
import json,sys,pathlib,xml.etree.ElementTree as ET
p=pathlib.Path(sys.argv[1]);rc=int(sys.argv[2]);far=json.loads((p/'a72_native_clock_far.json').read_text());near=json.loads((p/'a72_native_clock_near.json').read_text());x=ET.parse(p/'a72_targeted.xml').getroot()
n=[x] if x.tag=='testsuite' else x.findall('testsuite')
nt=sum(int(t.get('tests','0')) for t in n)
assert nt>=23 and all(int(t.get(k,'0'))==0 for k in ('errors','failures','skipped') for t in n)
assert far['status']=='CONDITIONAL_DECLARED_POLYGON_EXCLUSION' and far['native_certificate_replay_passed']
assert near['status']=='UNKNOWN' and near['geometry']['possible_contacts'] and rc==4
r=dict(status='CONDITIONAL_A72_SOFTWARE_AND_NATIVE_TOY_GATE_ONLY',targeted_passed=nt,
       native_clock_far_passed=True,native_near_unknown=True,
       full_sc_certified=False,physical_model_calibrated=False,
       sumo_live_tested_in_this_gate=False,waymax_real_scene_tested_in_this_gate=False,
       eight_formal_labels_authorized=False)
(p/'a72_acceptance.json').write_text(json.dumps(r,indent=2)+'\n');print(r)
PY
