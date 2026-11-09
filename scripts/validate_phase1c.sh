#!/usr/bin/env bash
# Complete Phase 1A/1B regression plus Phase 1C width-adaptive validation.
set -euo pipefail
export LC_ALL=C
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
PYTHON_BIN="${PYTHON_BIN:-python}"
BUILD_DIR="${BUILD_DIR:-$ROOT/build_phase1c}"
REPORT_DIR="${REPORT_DIR:-$ROOT/reports/phase1c_$(date -u +%Y%m%dT%H%M%SZ)}"
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
s=Path(sys.argv[1]).read_text(); m=re.search(r'Total Tests:\s*(\d+)',s)
if not m or int(m.group(1)) < 3: raise SystemExit('FAIL: fewer than 3 native tests discovered')
for n in ('interval_cpp','picard_cpp','abi_cpp'):
    if n not in s: raise SystemExit('FAIL: missing native test '+n)
PY
(cd "$BUILD_DIR" && ctest --output-on-failure) | tee "$REPORT_DIR/ctest.log"
"$PYTHON_BIN" -m pytest -q tests --junitxml="$REPORT_DIR/pytest.xml" | tee "$REPORT_DIR/pytest.log"
"$PYTHON_BIN" scripts/environment_report.py --output "$REPORT_DIR/environment.json"
"$PYTHON_BIN" scripts/demo_phase1b.py --output "$REPORT_DIR/demo_certificate.json" | tee "$REPORT_DIR/demo.log"
"$PYTHON_BIN" scripts/replay_certificate.py "$REPORT_DIR/demo_certificate.json" | tee "$REPORT_DIR/replay.log"
"$PYTHON_BIN" scripts/audit_phase1b.py --output "$REPORT_DIR/empirical_audit.json" | tee "$REPORT_DIR/audit.log"
"$PYTHON_BIN" scripts/benchmark_phase1c.py --output "$REPORT_DIR/phase1c_benchmark.json" --repeats "${BENCHMARK_REPEATS:-5}" | tee "$REPORT_DIR/benchmark.log"
"$PYTHON_BIN" - "$REPORT_DIR" <<'PY'
from pathlib import Path
import json, re, sys, xml.etree.ElementTree as ET
p=Path(sys.argv[1]); root=ET.parse(p/'pytest.xml').getroot()
suites=[root] if root.tag=='testsuite' else list(root.iter('testsuite'))
counts={k:sum(int(s.attrib.get(k,0)) for s in suites) for k in ('tests','errors','failures','skipped')}
if counts['tests'] < 83 or any(counts[k] for k in ('errors','failures','skipped')):
    raise SystemExit('FAIL: incomplete Python acceptance '+str(counts))
audit=json.loads((p/'empirical_audit.json').read_text())
env=json.loads((p/'environment.json').read_text())
boot='bootstrap_public_API_declarations' in env['native_build']
bench=json.loads((p/'phase1c_benchmark.json').read_text())
rows={r['method']:r for r in bench['rows']}
if not rows['adaptive_width_cap']['width_subdivisions']:
    raise SystemExit('FAIL: benchmark did not exercise adaptive width splits')
if not all(r['status']=='VALIDATED' and r['witness_replay'] for r in bench['rows']):
    raise SystemExit('FAIL: benchmark method did not validate/replay')
if rows['adaptive_width_cap']['max_accepted_width_ratio'] > 1.0:
    raise SystemExit('FAIL: accepted adaptive segment exceeded width policy')
summary=dict(status='BOOTSTRAP_TEST_PASS_REQUIRES_OFFICIAL_HEADERS' if boot else 'LOCAL_ACCEPTANCE_PASS',
 phase='1C',native_tests=3,python=counts,official_mpfr_headers_used=not boot,
 phase1b_empirical_containment_misses=audit['containment_misses'],
 phase1b_empirical_checked_state_vectors=audit['checked_state_vectors'],
 phase1c_benchmark_methods=len(bench['rows']),
 phase1c_width_subdivisions=rows['adaptive_width_cap']['width_subdivisions'],
 phase1c_adaptive_max_accepted_width_ratio=rows['adaptive_width_cap']['max_accepted_width_ratio'],
 all_benchmark_witnesses_replayed=all(r['witness_replay'] for r in bench['rows']),
 safety_verifier_implemented=False,report_directory=str(p))
(p/'acceptance_summary.json').write_text(json.dumps(summary,indent=2)+'\n')
print(json.dumps(summary,indent=2))
PY
"$PYTHON_BIN" - "$REPORT_DIR" <<'PY'
from pathlib import Path
import hashlib, json, sys
root=Path.cwd(); out={}
for name in ('CMakeLists.txt','python/rampd_core/reachability.py','python/rampd_core/certificate.py',
             'tests/test_adaptive_subdivision.py','scripts/benchmark_phase1c.py','scripts/validate_phase1c.sh'):
 p=root/name; out[name]=hashlib.sha256(p.read_bytes()).hexdigest()
Path(sys.argv[1],'source_sha256.json').write_text(json.dumps(out,indent=2)+'\n')
PY
printf '\nPASS: Phase 1A regressions, Phase 1B validated integration and Phase 1C adaptive-width checks completed.\nREPORT_DIR=%s\n' "$REPORT_DIR"
