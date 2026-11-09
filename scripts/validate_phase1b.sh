#!/usr/bin/env bash
# Every failure is fatal; CTest's zero-tests success code is explicitly rejected.
set -euo pipefail
export LC_ALL=C
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
PYTHON_BIN="${PYTHON_BIN:-python}"
BUILD_DIR="${BUILD_DIR:-$ROOT/build_phase1b}"
REPORT_DIR="${REPORT_DIR:-$ROOT/reports/phase1b_$(date -u +%Y%m%dT%H%M%SZ)}"
mkdir -p "$BUILD_DIR" "$REPORT_DIR"
BUILD_DIR="$(cd "$BUILD_DIR" && pwd)"
REPORT_DIR="$(cd "$REPORT_DIR" && pwd)"
export PYTHONPATH="$ROOT/python${PYTHONPATH:+:$PYTHONPATH}"
export RAMPD_INTERVAL_LIB="$BUILD_DIR/librampd_interval.so"
exec > >(tee "$REPORT_DIR/validation.log") 2>&1
printf 'ROOT=%s\nBUILD_DIR=%s\nREPORT_DIR=%s\n' "$ROOT" "$BUILD_DIR" "$REPORT_DIR"
"$PYTHON_BIN" -c 'import sys; assert sys.version_info >= (3,10), sys.version; import pytest, mpmath; print(sys.version)'
cmake --version
ctest --version
cmake -S "$ROOT" -B "$BUILD_DIR" -DCMAKE_BUILD_TYPE=Release -DRAMPD_BUILD_TESTS=ON "$@"
cmake --build "$BUILD_DIR" --parallel "${JOBS:-2}"
(cd "$BUILD_DIR" && ctest -N) | tee "$REPORT_DIR/ctest_discovery.log"
"$PYTHON_BIN" - "$REPORT_DIR/ctest_discovery.log" <<'PY'
import re, sys
from pathlib import Path
text=Path(sys.argv[1]).read_text()
m=re.search(r'Total Tests:\s*(\d+)',text)
if not m or int(m.group(1)) < 3:
    raise SystemExit('FAIL: fewer than 3 native tests discovered. Zero tests is NOT PASS.')
for name in ('interval_cpp','picard_cpp','abi_cpp'):
    if name not in text: raise SystemExit('FAIL: missing native test '+name)
PY
(cd "$BUILD_DIR" && ctest --output-on-failure) | tee "$REPORT_DIR/ctest.log"
"$PYTHON_BIN" -m pytest -q tests --junitxml="$REPORT_DIR/pytest.xml" | tee "$REPORT_DIR/pytest.log"
"$PYTHON_BIN" scripts/environment_report.py --output "$REPORT_DIR/environment.json"
"$PYTHON_BIN" scripts/demo_phase1b.py --output "$REPORT_DIR/demo_certificate.json" | tee "$REPORT_DIR/demo.log"
"$PYTHON_BIN" scripts/replay_certificate.py "$REPORT_DIR/demo_certificate.json" | tee "$REPORT_DIR/replay.log"
"$PYTHON_BIN" scripts/audit_phase1b.py --output "$REPORT_DIR/empirical_audit.json" | tee "$REPORT_DIR/audit.log"
"$PYTHON_BIN" - "$REPORT_DIR" <<'PY'
from pathlib import Path
import json, sys, xml.etree.ElementTree as ET
p=Path(sys.argv[1]); root=ET.parse(p/'pytest.xml').getroot()
suites=[root] if root.tag=='testsuite' else list(root.iter('testsuite'))
counts={k:sum(int(s.attrib.get(k,0)) for s in suites) for k in ('tests','errors','failures','skipped')}
if counts['tests']<70 or any(counts[k] for k in ('errors','failures','skipped')):
    raise SystemExit('FAIL: incomplete Python test acceptance '+str(counts))
audit=json.loads((p/'empirical_audit.json').read_text())
env=json.loads((p/'environment.json').read_text())
bootstrap='bootstrap_public_API_declarations' in env['native_build']
summary=dict(status='BOOTSTRAP_TEST_PASS_REQUIRES_OFFICIAL_HEADERS' if bootstrap else 'LOCAL_ACCEPTANCE_PASS',
             phase='1B',native_tests=3,python=counts,official_mpfr_headers_used=not bootstrap,
             empirical_containment_misses=audit['containment_misses'],
             empirical_checked_state_vectors=audit['checked_state_vectors'],
             safety_verifier_implemented=False,report_directory=str(p))
(p/'acceptance_summary.json').write_text(json.dumps(summary,indent=2)+'\n')
print(json.dumps(summary,indent=2))
PY
printf '\nPASS: all mandatory Phase 1A regressions and Phase 1B checks completed.\nREPORT_DIR=%s\n' "$REPORT_DIR"
