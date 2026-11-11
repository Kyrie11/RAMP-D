#!/usr/bin/env bash
# Full Phase 1A-1D regression plus Phase 2 finite information-state tests.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
PYTHON_BIN="${PYTHON_BIN:-python}"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
REPORT_DIR="${REPORT_DIR:-$ROOT/reports/phase2_$STAMP}"
BUILD_DIR="${BUILD_DIR:-$ROOT/build_phase1d}"
mkdir -p "$REPORT_DIR"
REPORT_DIR="$(cd "$REPORT_DIR" && pwd)"
export REPORT_DIR BUILD_DIR
# Phase 1D validator performs clean MPFR build, CTest discovery, all Python
# tests (including Phase 2), Phase 1B/1C/1D regressions, and geometry audits.
REPORT_DIR="$REPORT_DIR" BUILD_DIR="$BUILD_DIR" PYTHON_BIN="$PYTHON_BIN" \
  bash "$ROOT/scripts/validate_phase1d.sh"
export PYTHONPATH="$ROOT/python${PYTHONPATH:+:$PYTHONPATH}"
export RAMPD_INTERVAL_LIB="$BUILD_DIR/librampd_interval.so"
"$PYTHON_BIN" "$ROOT/scripts/demo_phase2.py" \
  --output "$REPORT_DIR/phase2_demo.json" \
  --certificate "$REPORT_DIR/phase2_demo_certificate.json" \
  | tee "$REPORT_DIR/phase2_demo.log"
"$PYTHON_BIN" "$ROOT/scripts/replay_invariant_certificate.py" \
  "$REPORT_DIR/phase2_demo_certificate.json" --allow-prefix demo- \
  | tee "$REPORT_DIR/phase2_replay.log"
"$PYTHON_BIN" "$ROOT/scripts/benchmark_phase2.py" \
  --sizes "${PHASE2_BENCHMARK_SIZES:-50,100,250,500,1000,2000}" \
  --output "$REPORT_DIR/phase2_benchmark.json" \
  | tee "$REPORT_DIR/phase2_benchmark.log"
"$PYTHON_BIN" - "$REPORT_DIR" <<'PY'
from pathlib import Path
import json, sys, xml.etree.ElementTree as ET
p=Path(sys.argv[1])
summary=json.loads((p/'acceptance_summary.json').read_text())
root=ET.parse(p/'pytest.xml').getroot()
suites=[root] if root.tag=='testsuite' else list(root.iter('testsuite'))
counts={k:sum(int(s.attrib.get(k,0)) for s in suites) for k in ('tests','errors','failures','skipped')}
demo=json.loads((p/'phase2_demo.json').read_text())
bench=json.loads((p/'phase2_benchmark.json').read_text())
if counts['tests'] < 120 or any(counts[k] for k in ('errors','failures','skipped')):
    raise SystemExit('FAIL: Phase 2 Python acceptance '+str(counts))
if demo['status']!='FIXPOINT_CONVERGED' or demo['retained_cell_ids']!=['A','L'] or not demo['certificate_replay']:
    raise SystemExit('FAIL: Phase 2 demo/fixed-point replay')
if any(r['status']!='FIXPOINT_CONVERGED' or r['retained']!=r['cells'] for r in bench['rows']):
    raise SystemExit('FAIL: Phase 2 finite-game benchmark')
summary.update({
  'phase':'2', 'python':counts,
  'phase2_status':'FIXPOINT_CONVERGED',
  'phase2_demo_retained_cell_ids':demo['retained_cell_ids'],
  'phase2_certificate_replay':demo['certificate_replay'],
  'phase2_benchmark_sizes':[r['cells'] for r in bench['rows']],
  'phase2_benchmark_all_fixtures_retained':True,
  'phase2_assurance_scope':'FINITE_ABSTRACTION_ONLY',
  'concrete_safety_certified':False,
  'safety_verifier_implemented':False,
  'report_directory':str(p)})
(p/'acceptance_summary.json').write_text(json.dumps(summary,indent=2)+'\n')
print(json.dumps(summary,indent=2))
PY
"$PYTHON_BIN" "$ROOT/scripts/package_report_phase2.py" --report "$REPORT_DIR"
printf '\nPASS: Phase 1A-1D regression and Phase 2 finite abstraction tests completed.\nREPORT_DIR=%s\n' "$REPORT_DIR"
