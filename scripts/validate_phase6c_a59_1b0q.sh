#!/usr/bin/env bash
# Mandatory existing rigorous acceptance AND A71 parallel controls.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
: "${RAMPD_INTERVAL_LIB:?set the NEW native library path}"
: "${A5_NATIVE_BUILD_DIR:?set the NEW native CMake build path}"
: "${REPORT_DIR:=$ROOT/reports/a71_$(date -u +%Y%m%dT%H%M%SZ)}"
[ ! -e "$REPORT_DIR" ] || { echo REFUSE_EXISTING_REPORT_DIR >&2; exit 4; }
export REPORT_DIR
# Old gate owns creation of REPORT_DIR, full repo tests and native microcase.
bash "$ROOT/scripts/validate_phase6c_a59_1b0p.sh"
export PYTHONPATH="$ROOT/python${PYTHONPATH:+:$PYTHONPATH}"
export PYTEST_DISABLE_PLUGIN_AUTOLOAD=1
python -m pytest -q "$ROOT/tests/test_a71_parallel_pure.py" \
 --junitxml="$REPORT_DIR/a71_targeted.xml" | tee "$REPORT_DIR/a71_targeted.log"
python "$ROOT/scripts/a71_audit_native_polygons.py" \
 --native-dir "$REPORT_DIR/native_microcase" \
 --resource-file "$ROOT/configs/a71_declared_microcase_far_polygons.json" \
 --length 4.8 --width 2.2 --output "$REPORT_DIR/a71_polygons_far.json"
# Near-resource scenario must NOT be accepted; use the JSON reasons as evidence.
set +e
python "$ROOT/scripts/a71_audit_native_polygons.py" \
 --native-dir "$REPORT_DIR/native_microcase" \
 --resource-file "$ROOT/configs/a71_declared_microcase_near_polygons.json" \
 --length 4.8 --width 2.2 --output "$REPORT_DIR/a71_polygons_near.json"
near_rc=$?
set -e
python - "$REPORT_DIR" "$near_rc" <<'PY'
import json,sys,pathlib,xml.etree.ElementTree as ET
p=pathlib.Path(sys.argv[1]);near_rc=int(sys.argv[2]);
sub=ET.parse(p/'a71_targeted.xml').getroot();nodes=[sub] if sub.tag=='testsuite' else sub.findall('testsuite');
num=sum(int(n.get('tests','0')) for n in nodes)
if num<29 or any(int(n.get(k,'0')) for k in ('errors','failures','skipped') for n in nodes):
 raise RuntimeError('A71_TARGETED_NOT_ALL_PASS')
f=json.loads((p/'a71_polygons_far.json').read_text());n=json.loads((p/'a71_polygons_near.json').read_text())
if f['status']!='CONDITIONAL_DECLARED_NATIVE_POLYGON_EXCLUSION' or n['status']!='UNKNOWN' or near_rc!=4 or not n['possible_contacts']:
 raise RuntimeError('A71_POLYGON_POSITIVE_NEGATIVE_NOT_REPRODUCED')
r={'schema':'rampd.a71.release_acceptance.v1','status':'CONDITIONAL_A71_THREE_TRACK_SOFTWARE_ACCEPTANCE',
   'a71_targeted_tests':num,'native_polygon_far_conditional':True,'native_polygon_near_unknown':True,
   'full_sc_certified':False,'full_real_physics_certified':False,'waymax_live_run':False,
   'sumo_live_run':False,'formal_supervision_labels_authorized':False}
(p/'a71_acceptance.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r,indent=2))
PY
