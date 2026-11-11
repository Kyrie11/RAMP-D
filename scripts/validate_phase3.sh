#!/usr/bin/env bash
# Phase 1A-2 regression followed by public-backup synthesis/execution checks.
set -euo pipefail
export LC_ALL=C
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
PYTHON_BIN="${PYTHON_BIN:-python}"
BUILD_DIR="${BUILD_DIR:-$ROOT/build_phase3}"
REPORT_DIR="${REPORT_DIR:-$ROOT/reports/phase3_$(date -u +%Y%m%dT%H%M%SZ)}"
mkdir -p "$BUILD_DIR" "$REPORT_DIR"
BUILD_DIR="$(cd "$BUILD_DIR" && pwd)"
REPORT_DIR="$(cd "$REPORT_DIR" && pwd)"
export BUILD_DIR REPORT_DIR
export PYTHONPATH="$ROOT/python${PYTHONPATH:+:$PYTHONPATH}"
export RAMPD_INTERVAL_LIB="$BUILD_DIR/librampd_interval.so"
# Third-party pytest entry points are unrelated to the numerical core.
export PYTEST_DISABLE_PLUGIN_AUTOLOAD="${PYTEST_DISABLE_PLUGIN_AUTOLOAD:-1}"
exec > >(tee "$REPORT_DIR/phase3_validation.log") 2>&1
printf 'ROOT=%s\nBUILD_DIR=%s\nREPORT_DIR=%s\n' "$ROOT" "$BUILD_DIR" "$REPORT_DIR"

phase3_stage="phase2_regression"
finish_phase3() {
  local phase3_exit_status=$?
  trap - EXIT
  if [[ "$phase3_exit_status" -ne 0 ]]; then
    "$PYTHON_BIN" - "$REPORT_DIR" "$phase3_stage" "$phase3_exit_status" <<'PY' || true
from pathlib import Path
import json, sys
p = Path(sys.argv[1])
failure = {
    'status': 'PHASE3_VALIDATION_FAILED', 'phase': '3',
    'failed_stage': sys.argv[2], 'exit_code': int(sys.argv[3]),
    'full_support_certified': False, 'concrete_safety_certified': False,
    'target_server_acceptance': 'PENDING_EXTERNAL_REVIEW',
    'report_directory': str(p),
}
old = p / 'acceptance_summary.json'
if old.is_file():
    previous = json.loads(old.read_text())
    if previous.get('phase') == '2' and not (p / 'phase2_acceptance_summary.json').exists():
        (p / 'phase2_acceptance_summary.json').write_text(old.read_text())
    failure['preceding_summary'] = previous
(p / 'phase3_failure.json').write_text(json.dumps(failure, indent=2) + '\n')
old.write_text(json.dumps(failure, indent=2) + '\n')
print(json.dumps(failure, indent=2))
PY
  fi
  if ! "$PYTHON_BIN" "$ROOT/scripts/package_report_phase3.py" --report "$REPORT_DIR"; then
    printf 'FAIL: Phase 3 report packaging failed; inspect REPORT_DIR above.\n' >&2
    if [[ "$phase3_exit_status" -eq 0 ]]; then phase3_exit_status=1; fi
  fi
  exit "$phase3_exit_status"
}
trap finish_phase3 EXIT

# This includes a fresh native build, CTest discovery, every Python test,
# all earlier benchmarks and containment audits. No manuscript is required.
REPORT_DIR="$REPORT_DIR" BUILD_DIR="$BUILD_DIR" PYTHON_BIN="$PYTHON_BIN" \
  bash "$ROOT/scripts/validate_phase2.sh" "$@"
cp "$REPORT_DIR/acceptance_summary.json" "$REPORT_DIR/phase2_acceptance_summary.json"

phase3_stage="phase3_demo"
"$PYTHON_BIN" "$ROOT/scripts/demo_phase3.py" \
  --output "$REPORT_DIR/phase3_demo.json" \
  --graph "$REPORT_DIR/phase3_backup_graph.json" \
  --trace "$REPORT_DIR/phase3_trace.json" \
  | tee "$REPORT_DIR/phase3_demo.log"

phase3_stage="phase3_benchmark"
"$PYTHON_BIN" "$ROOT/scripts/benchmark_phase3.py" \
  --output "$REPORT_DIR/phase3_benchmark.json" \
  --repeats "${PHASE3_BENCHMARK_REPEATS:-3}" \
  | tee "$REPORT_DIR/phase3_benchmark.log"

phase3_stage="phase3_graph_replay"
phase3_replay_args=()
if [[ -n "${PHASE3_EXPECTED_CONTRACT_DIGEST:-}" ]]; then
  phase3_replay_args+=(--expected-contract-digest "$PHASE3_EXPECTED_CONTRACT_DIGEST")
fi
"$PYTHON_BIN" "$ROOT/scripts/replay_backup_graph.py" \
  "$REPORT_DIR/phase3_backup_graph.json" "${phase3_replay_args[@]}" \
  | tee "$REPORT_DIR/phase3_replay.json" "$REPORT_DIR/phase3_replay.log"

phase3_stage="phase3_acceptance_gates"
"$PYTHON_BIN" - "$REPORT_DIR" <<'PY'
from pathlib import Path
import json, math, sys, xml.etree.ElementTree as ET

p = Path(sys.argv[1])
summary = json.loads((p / 'phase2_acceptance_summary.json').read_text())
root = ET.parse(p / 'pytest.xml').getroot()
cases = list(root.iter('testcase'))
counts = {
    'tests': len(cases),
    'errors': sum(c.find('error') is not None for c in cases),
    'failures': sum(c.find('failure') is not None for c in cases),
    'skipped': sum(c.find('skipped') is not None for c in cases),
}
modules = ('test_public_control', 'test_analytic_bounds',
           'test_evidence_binding', 'test_backup_synthesis', 'test_backup_graph')
module_counts = {
    name: sum(name in c.attrib.get('classname', '').split('.') or
              Path(c.attrib.get('file', '')).stem == name for c in cases)
    for name in modules
}
if counts['tests'] < 200 or any(counts[k] for k in ('errors', 'failures', 'skipped')):
    raise SystemExit('FAIL: incomplete Phase 3 Python acceptance ' + str(counts))
if any(value == 0 for value in module_counts.values()):
    raise SystemExit('FAIL: missing Phase 3 regression module ' + str(module_counts))
if summary.get('phase') != '2' or summary.get('status') not in (
        'LOCAL_ACCEPTANCE_PASS', 'BOOTSTRAP_TEST_PASS_REQUIRES_OFFICIAL_HEADERS'):
    raise SystemExit('FAIL: prior Phase 2 acceptance did not pass')

demo = json.loads((p / 'phase3_demo.json').read_text())
bench = json.loads((p / 'phase3_benchmark.json').read_text())
replay = json.loads((p / 'phase3_replay.json').read_text())
required_kinds = {'brake_to_stop', 'hold_before_gate', 'yield', 'clear_merge'}
templates = demo.get('templates', [])
if (demo.get('status') != 'PHASE3_LOCAL_DEMO_PASS' or
        demo.get('full_support_certified') is not False):
    raise SystemExit('FAIL: invalid Phase 3 demo result or assurance claim')
if len(templates) != 4 or {r.get('kind') for r in templates} != required_kinds:
    raise SystemExit('FAIL: all four recovery templates must be evaluated')
for row in templates:
    if (row.get('status') != 'SYNTHESIZED_LOCAL' or
            not isinstance(row.get('accepted_candidates'), int) or
            isinstance(row['accepted_candidates'], bool) or row['accepted_candidates'] < 1 or
            not isinstance(row.get('selected_has_feedback'), bool)):
        raise SystemExit('FAIL: recovery template synthesis ' + str(row))
failures = demo.get('failure_cases', [])
if not failures or any(r.get('expected_rejection') is not True for r in failures):
    raise SystemExit('FAIL: a deliberate unsafe/unresolved fixture was not rejected')
brake = demo.get('brake_graph', {})
if (brake.get('retained_nodes') != 17 or brake.get('graph_replay') is not True or
        brake.get('execution_steps', 0) < 20 or
        brake.get('exact_terminal_v_zero') is not True or
        brake.get('exact_terminal_a_zero') is not True):
    raise SystemExit('FAIL: closed brake/hold graph or exact terminal stop ' + str(brake))
if (replay.get('ok') is not True or replay.get('retained_nodes') != 17 or
        replay.get('closed_graph') is not True or
        replay.get('full_support_certified') is not False or
        replay.get('current_scene_verified') is not False):
    raise SystemExit('FAIL: independent backup graph replay')

rows = bench.get('rows', [])
if len(rows) != 4 or {r.get('kind') for r in rows} != required_kinds:
    raise SystemExit('FAIL: incomplete Phase 3 benchmark kinds')
for row in rows:
    try:
        timings_ok = (math.isfinite(row['median_s']) and math.isfinite(row['p95_s']) and
                      0 <= row['median_s'] <= row['p95_s'])
        size_ok = (isinstance(row['candidates'], int) and not isinstance(row['candidates'], bool)
                   and isinstance(row['accepted'], int) and not isinstance(row['accepted'], bool)
                   and 1 <= row['accepted'] <= row['candidates'])
    except (KeyError, TypeError, ValueError):
        timings_ok = size_ok = False
    if row.get('status') != 'SYNTHESIZED_LOCAL' or not timings_ok or not size_ok:
        raise SystemExit('FAIL: invalid Phase 3 benchmark row ' + str(row))
if bench.get('full_support_certified', False) is not False:
    raise SystemExit('FAIL: benchmark overstates its assurance scope')

summary.update({
    'phase': '3', 'python': counts,
    'phase3_required_test_modules': module_counts,
    'phase2_regression_passed': True,
    'phase3_demo_status': demo['status'],
    'phase3_recovery_kinds': sorted(required_kinds),
    'phase3_template_accepted_candidates': {r['kind']: r['accepted_candidates'] for r in templates},
    'phase3_templates_with_selected_feedback': [r['kind'] for r in templates if r['selected_has_feedback']],
    'phase3_graph_retained_nodes': brake['retained_nodes'],
    'phase3_graph_closed': True,
    'phase3_graph_replay': True,
    'phase3_execution_steps': brake['execution_steps'],
    'phase3_exact_terminal_v_zero': True,
    'phase3_exact_terminal_a_zero': True,
    'phase3_expected_rejections': len(failures),
    'phase3_benchmark_kinds': len(rows),
    'assurance_scope': 'LOCAL_BICYCLE_STATIC_SCENE_DECLARED_OBSERVATIONS',
    'full_support_certified': False,
    'concrete_safety_certified': False,
    'safety_verifier_implemented': False,
    'current_scene_verified': False,
    'acceptance_scope': 'RUNNING_MACHINE_SOFTWARE_ACCEPTANCE',
    'target_server_acceptance': 'PENDING_EXTERNAL_REVIEW',
    'report_directory': str(p),
})
(p / 'acceptance_summary.json').write_text(json.dumps(summary, indent=2, allow_nan=False) + '\n')
print(json.dumps(summary, indent=2, allow_nan=False))
PY
phase3_stage="complete"
printf '\nPASS: Phase 1A-2 regressions and Phase 3 local backup validation completed.\nREPORT_DIR=%s\n' "$REPORT_DIR"
