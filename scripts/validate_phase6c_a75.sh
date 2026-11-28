#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
: "${A5_NATIVE_BUILD_DIR:?fresh native build required}"
: "${RAMPD_INTERVAL_LIB:?fresh native shared library required}"
export REPORT_DIR="${REPORT_DIR:-$ROOT/reports/phase7bc_relation/native_$(date -u +%Y%m%dT%H%M%SZ)}"
bash "$ROOT/scripts/validate_phase6c_a59_1b0t.sh"
export PYTHONPATH="$ROOT/python${PYTHONPATH:+:$PYTHONPATH}" PYTEST_DISABLE_PLUGIN_AUTOLOAD=1
python "$ROOT/scripts/validate_a75_pure.py" --junitxml="$REPORT_DIR/a75_targeted.xml" | tee "$REPORT_DIR/a75_targeted.log"
python -m pytest -q "$ROOT/tests/test_sc_inner.py" --junitxml="$REPORT_DIR/a75_sc_inner.xml" | tee "$REPORT_DIR/a75_sc_inner.log"
python - "$REPORT_DIR" <<'PY'
import json,sys,pathlib
from rampd_core.a75_wait_game import synthesize,replay
p=pathlib.Path(sys.argv[1]);r,s=synthesize();assert replay(r,s,14)==12 and synthesize(horizon=11)[1] is None
(p/'a75_acceptance.json').write_text(json.dumps(dict(status='CONDITIONAL_NATIVE_AND_FINITE_SUBGATES_ONLY',finite_wait_rank=12,full_sc_certified=False,phase6c_exit=False,formal_labels_authorized=False),indent=2)+'\n')
PY
