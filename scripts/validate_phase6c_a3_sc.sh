#!/usr/bin/env bash
# Phase 6C-A3: Phase 4/5 import repair + finite SC/rank/conditional-margin gate.
# Native ABI and pytest are MANDATORY; fail rather than invent a PASS.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
PYTHON_BIN="${PYTHON_BIN:-python}"
BUILD_DIR="${BUILD_DIR:-$ROOT/build_phase1d}"
REPORT_DIR="${REPORT_DIR:-$ROOT/reports/phase6c_a3_$(date -u +%Y%m%dT%H%M%SZ)}"
mkdir -p "$REPORT_DIR"
export PYTHONPATH="$ROOT/python${PYTHONPATH:+:$PYTHONPATH}"
export PYTEST_DISABLE_PLUGIN_AUTOLOAD="${PYTEST_DISABLE_PLUGIN_AUTOLOAD:-1}"
"$PYTHON_BIN" -c 'import sys,pytest; assert sys.version_info >= (3,10),sys.version; print("Python:",sys.version)'
if [[ -z "${RAMPD_INTERVAL_LIB:-}" ]]; then
  RAMPD_INTERVAL_LIB="$BUILD_DIR/librampd_interval.so"
  export RAMPD_INTERVAL_LIB
fi
if [[ ! -f "$RAMPD_INTERVAL_LIB" ]]; then
  echo "Building native MPFR backend at $BUILD_DIR"
  cmake -S "$ROOT" -B "$BUILD_DIR" -DCMAKE_BUILD_TYPE=Release -DRAMPD_BUILD_TESTS=ON
  cmake --build "$BUILD_DIR" --parallel "${JOBS:-4}"
fi
if [[ ! -f "$BUILD_DIR/CTestTestfile.cmake" ]]; then
  echo "ERROR: missing native CTest manifest in $BUILD_DIR" >&2
  exit 4
fi
(
 cd "$BUILD_DIR"
 ctest -N
) | tee "$REPORT_DIR/ctest_discovery.log"
"$PYTHON_BIN" - "$REPORT_DIR/ctest_discovery.log" <<'PY'
import re,sys
from pathlib import Path
text=Path(sys.argv[1]).read_text()
m=re.search(r'Total Tests:\s*(\d+)',text)
if not m or int(m.group(1))<3 or any(x not in text for x in ('interval_cpp','picard_cpp','abi_cpp')):
    raise SystemExit('ERROR: native CTest discoverability contract failed')
PY
(cd "$BUILD_DIR" && ctest --output-on-failure) | tee "$REPORT_DIR/ctest.log"
"$PYTHON_BIN" - <<'PY'
import rampd_core
from rampd_core.protocol import build_coverage_ledger
from rampd_core.safe_continuation import compute_sc_inner
print("BACKEND",rampd_core.backend_name())
print("API",build_coverage_ledger.__name__,compute_sc_inner.__name__)
PY
"$PYTHON_BIN" -m pytest -q \
  tests/test_sc_inner.py \
  tests/test_phase4_protocol.py \
  tests/test_phase4_full.py \
  tests/test_phase5_cegar.py \
  --junitxml="$REPORT_DIR/pytest.xml" | tee "$REPORT_DIR/pytest.log"
"$PYTHON_BIN" scripts/validate_phase6c_a_dependency_free.py \
  --junitxml="$REPORT_DIR/phase6c_a2_pytest.xml" | tee "$REPORT_DIR/phase6c_a2_pytest.log"
"$PYTHON_BIN" - "$REPORT_DIR" <<'PY'
from pathlib import Path
import json,sys,xml.etree.ElementTree as ET
p=Path(sys.argv[1])
def counts(name):
    root=ET.parse(p/name).getroot()
    rows=list(root.iter('testcase'))
    return {'tests':len(rows),'failed':sum(x.find('failure') is not None for x in rows),
            'errors':sum(x.find('error') is not None for x in rows),
            'skipped':sum(x.find('skipped') is not None for x in rows)}
a=counts('pytest.xml'); b=counts('phase6c_a2_pytest.xml')
if a['tests']<13 or b['tests']<67 or any(a[k] or b[k] for k in ('failed','errors','skipped')):
    raise SystemExit('ERROR: incomplete regression gate '+str((a,b)))
s={'phase':'6C-A3_SC_RANK','status':'PASS_NATIVE_ABI_AND_FINITE_SC_REGRESSION',
   'new_and_phase4_5_python':a,'phase6c_a2_dependency_free':b,
   'native_ctest_minimum':3,
   'proof_scope':'FINITE_ABSTRACTION_CONDITIONAL_ON_REPLAYED_EXTERNAL_WITNESSES',
   'full_support_certified':False,'real_data_both_pass':False,
   'terminal_tail_full_replay_verified':False,'ccg_full_implementation':False,
   'carla_sumo_used':False}
(p/'acceptance_summary.json').write_text(json.dumps(s,sort_keys=True,indent=2)+'\n')
print(json.dumps(s,sort_keys=True,indent=2))
PY
"$PYTHON_BIN" - "$REPORT_DIR" <<'PY'
from pathlib import Path
import sys,zipfile
folder=Path(sys.argv[1]); outfile=folder.parent/'RAMP-D_Phase6C_A3_server_report.zip'
with zipfile.ZipFile(outfile,'w',zipfile.ZIP_DEFLATED) as z:
    for p in sorted(folder.glob('*')):
        if p.is_file():z.write(p,p.name)
print('REPORT_ARCHIVE',outfile)
PY
printf 'PHASE6C_A3_STATUS=PASS_NATIVE_REGRESSION_ONLY; dataset_pair=UNVERIFIED; full_support=false\n'
