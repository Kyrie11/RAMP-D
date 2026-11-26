#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
export PYTHONPATH="$ROOT/python${PYTHONPATH:+:$PYTHONPATH}" PYTEST_DISABLE_PLUGIN_AUTOLOAD=1
OUT="${REPORT_DIR:-$ROOT/reports/learning_pilot_$(date -u +%Y%m%dT%H%M%SZ)}"
if [ -e "$OUT" ]; then echo 'report dir exists' >&2; exit 4; fi
mkdir -p "$OUT"
python scripts/verify_release.py | tee "$OUT/integrity.log"
python -m pytest -q tests/test_learning_pilot.py tests/test_cosim_map_registration.py --junitxml="$OUT/learning.xml" | tee "$OUT/learning.log"
printf '%s\n' 'LEARNING_PILOT_SOFTWARE_PASS_NOT_DATASET_TRAINING_OR_SC' | tee "$OUT/status.txt"
