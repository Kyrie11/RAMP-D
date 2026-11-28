#!/usr/bin/env bash
# Regression of the naming/archival migration, not a Native or simulator gate.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
PY="${PYTHON_BIN:-python}"
export PYTEST_DISABLE_PLUGIN_AUTOLOAD=1
OUT="${REPORT_DIR:-$ROOT/reports/phase7bc_relation/cleanup_$(date -u +%Y%m%dT%H%M%SZ)}"
if [ -e "$OUT" ]; then echo "REFUSE_EXISTING_REPORT_DIR: $OUT" >&2; exit 4; fi
mkdir -p "$OUT"
"$PY" scripts/verify_release.py | tee "$OUT/release_integrity.log"
for harness in validate_a75_pure validate_phase6c_a_dependency_free validate_a58_pure validate_a59_pure validate_a71_pure validate_sc_discrete_only; do
  env -u RAMPD_INTERVAL_LIB "$PY" "scripts/${harness}.py" --junitxml="$OUT/${harness}.xml" | tee "$OUT/${harness}.log"
done
"$PY" -m pytest -q tests/test_release_integrity.py --junitxml="$OUT/release_integrity_tests.xml" | tee "$OUT/release_integrity_tests.log"
printf '%s\n' 'CLEANUP_PURE_REGRESSION_PASS (NOT_NATIVE_OR_FULL_SC)' | tee "$OUT/status.txt"
