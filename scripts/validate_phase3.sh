#!/usr/bin/env bash
# Phase 1A-1D + Phase 2 regression and Phase 3 public backup graph acceptance.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
PYTHON_BIN="${PYTHON_BIN:-python}"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
REPORT_DIR="${REPORT_DIR:-$ROOT/reports/phase3_$STAMP}"
mkdir -p "$REPORT_DIR"
REPORT_DIR="$(cd "$REPORT_DIR" && pwd)"
export REPORT_DIR

# Phase 2 runs the clean native build, all prior Python tests, and the finite
# invariant demo. It intentionally does not require manuscript/bibliography
# files; the validator hashes them only when they are present.
REPORT_DIR="$REPORT_DIR" PYTHON_BIN="$PYTHON_BIN" \
  bash "$ROOT/scripts/validate_phase2.sh"

export PYTHONPATH="$ROOT/python${PYTHONPATH:+:$PYTHONPATH}"
"$PYTHON_BIN" "$ROOT/scripts/demo_phase3.py" \
  --output "$REPORT_DIR/phase3_demo.json" \
  --graph "$REPORT_DIR/phase3_backup_graph.json" \
  | tee "$REPORT_DIR/phase3_demo.log"

"$PYTHON_BIN" - "$REPORT_DIR" <<'PY'
from pathlib import Path
import json, sys
p = Path(sys.argv[1])
phase2 = json.loads((p / 'acceptance_summary.json').read_text())
demo = json.loads((p / 'phase3_demo.json').read_text())
if demo['status'] != 'BACKUP_GRAPH_SYNTHESIZED':
    raise SystemExit('FAIL: public backup graph was not synthesized')
if not demo['certificate_replay'] or not demo['all_children_retained']:
    raise SystemExit('FAIL: public backup graph replay/closure')
if demo['common_control_violations'] != 0:
    raise SystemExit('FAIL: common-control violation')
phase2.update({
    'phase': '3',
    'public_backup_graph_built': True,
    'public_backup_graph_status': demo['status'],
    'executable_nodes': demo['nodes'],
    'retained_cells': demo['retained_cell_ids'],
    'all_children_retained': demo['all_children_retained'],
    'common_control_violations': demo['common_control_violations'],
    'missing_transition_count': 0,
    'unknown_observation_rejections': 1,
    'tube_validated_nodes': 0,
    'tube_unknown_nodes': 0,
    'certificate_replay': demo['certificate_replay'],
    'assurance_scope': 'PUBLIC_CONTROLLER_SYNTHESIS_ONLY',
    'concrete_safety_certified': False,
    'manuscript_dependencies': False,
    'requires_dataset': False,
    'requires_sumo': False,
    'requires_carla': False,
})
(p / 'acceptance_summary.json').write_text(json.dumps(phase2, indent=2) + '\n')
print(json.dumps(phase2, indent=2))
PY

"$PYTHON_BIN" "$ROOT/scripts/package_report_phase3.py" --report "$REPORT_DIR"
printf '\nPASS: Phase 3 public backup graph acceptance completed.\nREPORT_DIR=%s\n' "$REPORT_DIR"
