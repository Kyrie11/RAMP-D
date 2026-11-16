#!/usr/bin/env bash
# Map semantics gate (pure-Python) + optional real sample gate.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
PYTHON_BIN="${PYTHON_BIN:-python3}"
mkdir -p reports
"$PYTHON_BIN" scripts/validate_phase6c_a_dependency_free.py \
  --junitxml reports/phase6c_a2_pytest.xml | tee reports/phase6c_a2_pytest.log
"$PYTHON_BIN" -m compileall -q python/rampd_core tests
bash -n scripts/validate_phase6b.sh
bash -n scripts/validate_phase6B.sh
printf 'PHASE6C_A2_LOCAL_STATUS=PASS; native=false; real_data=false; formal_certificate=false\n'
printf 'Run MAX_RECORDS=1 bash scripts/validate_phase6b.sh for real WOMD+AV2 map smoke.\n'
