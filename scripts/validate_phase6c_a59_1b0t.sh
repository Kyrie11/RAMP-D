#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export REPORT_DIR="${REPORT_DIR:-$ROOT/reports/a74_$(date -u +%Y%m%dT%H%M%SZ)}"
bash "$ROOT/scripts/validate_phase6c_a59_1b0s.sh"
export PYTHONPATH="$ROOT/python${PYTHONPATH:+:$PYTHONPATH}" PYTEST_DISABLE_PLUGIN_AUTOLOAD=1
python "$ROOT/scripts/validate_a74_pure.py" --junitxml="$REPORT_DIR/a74_targeted.xml" | tee "$REPORT_DIR/a74_targeted.log"
python - "$REPORT_DIR" <<'PY'
import json,sys,pathlib
p=pathlib.Path(sys.argv[1]);r=json.loads((p/'a73_native_multi/review.json').read_text())
assert r['public_post']['status']=='CONDITIONAL_DECLARED_NATIVE_POST_SUPPORT'
assert r['missing_posterior_atom']['status']=='UNKNOWN'
(p/'a74_acceptance.json').write_text(json.dumps(dict(status='CONDITIONAL_NATIVE_POST_GATE_ONLY',full_sc_certified=False,phase6c_exit=False,formal_labels_authorized=False),indent=2)+'\n')
PY
