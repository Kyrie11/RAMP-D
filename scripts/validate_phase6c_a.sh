#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
mkdir -p reports
PYTHON_BIN="${PYTHON_BIN:-python}"

"$PYTHON_BIN" scripts/validate_phase6c_a_dependency_free.py \
  --junitxml reports/phase6c_a_pytest.xml | tee reports/phase6c_a_pytest.log
"$PYTHON_BIN" -m compileall -q python/rampd_core tests
bash -n scripts/validate_phase6b.sh

"$PYTHON_BIN" - <<'PY'
import json
import xml.etree.ElementTree as ET
from pathlib import Path
root = ET.parse('reports/phase6c_a_pytest.xml').getroot()
if root.tag == 'testsuites':
    suites = list(root)
else:
    suites = [root]
summary = {key: sum(int(s.attrib.get(key, 0)) for s in suites)
           for key in ('tests', 'failures', 'errors', 'skipped')}
summary.update({
    'status': 'PASS' if summary['failures'] == 0 and summary['errors'] == 0 else 'ERROR',
    'scope': 'PHASE6B_PURE_PYTHON_ADAPTERS_AND_PHASE6C_A_CONTRACTS_ONLY',
    'native_backend_tested': False,
    'real_data_tested': False,
    'simulators_used': False,
    'full_support_certified': False,
})
Path('reports/phase6c_a_acceptance_summary.json').write_text(
    json.dumps(summary, indent=2, sort_keys=True) + '\n'
)
print(json.dumps(summary, indent=2, sort_keys=True))
if summary['status'] != 'PASS':
    raise SystemExit(1)
PY

echo "PHASE6C_A_STATUS=PASS report=$ROOT/reports/phase6c_a_acceptance_summary.json"
