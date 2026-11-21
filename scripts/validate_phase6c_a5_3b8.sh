#!/usr/bin/env bash
# A58 mathematical-fix and proof-obligation gate. No claim of real-world full support.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-python}"
REPORT_DIR="${REPORT_DIR:-$ROOT/reports/phase6c_a5_3b8_$(date -u +%Y%m%dT%H%M%SZ)}"
mkdir -p "$REPORT_DIR"
export A5_NATIVE_BUILD_DIR="${A5_NATIVE_BUILD_DIR:-$ROOT/build_phase6c_a5_3b8}"
export PYTHONPATH="$ROOT/python${PYTHONPATH:+:$PYTHONPATH}"
export PYTEST_DISABLE_PLUGIN_AUTOLOAD="${PYTEST_DISABLE_PLUGIN_AUTOLOAD:-1}"
STAGE=release_integrity
trap 'rc=$?; if [ "$rc" -ne 0 ]; then printf "{\"phase\":\"6C-A5/3b-8\",\"status\":\"ERROR\",\"stage\":\"%s\",\"returncode\":%s}\n" "$STAGE" "$rc" > "$REPORT_DIR/phase6c_a5_3b8_acceptance.json"; fi' EXIT
"$PYTHON_BIN" "$ROOT/scripts/verify_release.py" | tee "$REPORT_DIR/sha256.log"
STAGE=pure_reference
"$PYTHON_BIN" "$ROOT/scripts/validate_a58_pure.py" --junitxml="$REPORT_DIR/a58_pure.xml" | tee "$REPORT_DIR/a58_pure.log"
STAGE=incumbent_math_native_and_full_regression
# Retains original 653-test server baseline, C++ CTest and all older scopes.
REPORT_DIR="$REPORT_DIR/a57_full" bash "$ROOT/scripts/validate_phase6c_a5_3b7.sh" | tee "$REPORT_DIR/a57_full_run.log"
export RAMPD_INTERVAL_LIB="$A5_NATIVE_BUILD_DIR/librampd_interval.so"
STAGE=a58_native_safety
"$PYTHON_BIN" -m pytest -q "$ROOT/tests/test_phase6c_a58_native.py" \
  --junitxml="$REPORT_DIR/a58_native.xml" | tee "$REPORT_DIR/a58_native.log"
STAGE=summary
"$PYTHON_BIN" - "$REPORT_DIR" <<'PY'
import json,sys,pathlib,xml.etree.ElementTree as E
p=pathlib.Path(sys.argv[1])
def counts(f):
 t=E.parse(f).getroot(); ss=[t] if t.tag=='testsuite' else t.findall('testsuite')
 if not ss or any(int(s.get(k,'0')) for s in ss for k in ('errors','failures','skipped')):raise SystemExit('failed/skipped suite '+str(f))
 return sum(int(s.get('tests',0)) for s in ss)
n=counts(p/'a58_native.xml');pure=counts(p/'a58_pure.xml')
base=json.loads((p/'a57_full'/'phase6c_a5_3b7_acceptance_summary.json').read_text())
if n<6 or pure<19 or base['test_counts']['all_pytest']<679 or base['native_tests']!=3:
 raise SystemExit('A58 positive test manifest not met')
o={'phase':'6C-A5/3b-8','status':'CONDITIONAL_LOCAL_OBLIGATIONS_PASS',
 'base_server_suite':base['test_counts'],'native_ctest':3,'a58_pure':pure,'a58_native':n,
 'jerk_exact_reference_only':True,'physical_post_e2_safe_gate_conditional_only':True,
 'full_support_safecert':False,'dynamic_resource_topology_complete':False,
 'task_sc_terminal_tail_certified':False,'physical_carla_sumo_runtime':False,
 'real_world_counterfactual_validated':False,'roadwork_real_metric_labels':False}
(p/'phase6c_a5_3b8_acceptance.json').write_text(json.dumps(o,indent=2)+'\n')
print(json.dumps(o,indent=2))
PY
printf 'A58_CONDITIONAL_GATE_PASS report=%s\n' "$REPORT_DIR"
