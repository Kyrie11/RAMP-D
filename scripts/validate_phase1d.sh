#!/usr/bin/env bash
# Full Phase 1A-1D regression, geometric enclosure, separation replay and audits.
set -euo pipefail
export LC_ALL=C
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
PYTHON_BIN="${PYTHON_BIN:-python}"
BUILD_DIR="${BUILD_DIR:-$ROOT/build_phase1d}"
REPORT_DIR="${REPORT_DIR:-$ROOT/reports/phase1d_$(date -u +%Y%m%dT%H%M%SZ)}"
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
import re,sys
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
"$PYTHON_BIN" scripts/audit_phase1b.py --output "$REPORT_DIR/empirical_audit_phase1b.json" | tee "$REPORT_DIR/audit_phase1b.log"
"$PYTHON_BIN" scripts/benchmark_phase1c.py --output "$REPORT_DIR/phase1c_benchmark.json" --repeats "${BENCHMARK_REPEATS:-5}" | tee "$REPORT_DIR/benchmark_phase1c.log"
"$PYTHON_BIN" scripts/benchmark_phase1d.py --output "$REPORT_DIR/phase1d_benchmark.json" --repeats "${BENCHMARK_REPEATS:-5}" --iterations "${BENCHMARK_ITERATIONS:-100}" | tee "$REPORT_DIR/benchmark_phase1d.log"
"$PYTHON_BIN" scripts/audit_phase1d.py --output "$REPORT_DIR/footprint_audit.json" --samples "${FOOTPRINT_AUDIT_SAMPLES:-2000}" | tee "$REPORT_DIR/footprint_audit.log"
"$PYTHON_BIN" - "$REPORT_DIR" <<'PY'
from pathlib import Path
import json,re,sys,xml.etree.ElementTree as ET
p=Path(sys.argv[1]); root=ET.parse(p/'pytest.xml').getroot(); suites=[root] if root.tag=='testsuite' else list(root.iter('testsuite'))
counts={k:sum(int(s.attrib.get(k,0)) for s in suites) for k in ('tests','errors','failures','skipped')}
if counts['tests'] < 100 or any(counts[k] for k in ('errors','failures','skipped')):
    raise SystemExit('FAIL: incomplete Python acceptance '+str(counts))
env=json.loads((p/'environment.json').read_text()); boot='bootstrap_public_API_declarations' in env['native_build']
b1=json.loads((p/'phase1c_benchmark.json').read_text()); rows1={r['method']:r for r in b1['rows']}
if not rows1['adaptive_width_cap']['width_subdivisions'] or not all(r['status']=='VALIDATED' and r['witness_replay'] for r in b1['rows']):
    raise SystemExit('FAIL: Phase 1C regression benchmark')
if rows1['adaptive_width_cap']['max_accepted_width_ratio']>1.0: raise SystemExit('FAIL: Phase 1C width cap')
b2=json.loads((p/'phase1d_benchmark.json').read_text()); rows2={r['method']:r for r in b2['rows']}
if rows2['aabb_only']['status']!='UNKNOWN': raise SystemExit('FAIL: AABB overlap must remain UNKNOWN in diagonal test')
for name in ('oriented_candidate_axes','dense_16_plus_oriented'):
    if rows2[name]['status']!='SEPARATED' or not rows2[name]['witness_replay']:
        raise SystemExit('FAIL: Phase 1D oriented separation/replay '+name)
audit=json.loads((p/'footprint_audit.json').read_text())
if audit['misses']!=0: raise SystemExit('FAIL: footprint containment audit miss')
summary=dict(status='BOOTSTRAP_TEST_PASS_REQUIRES_OFFICIAL_HEADERS' if boot else 'LOCAL_ACCEPTANCE_PASS',
 phase='1D',native_tests=3,python=counts,official_mpfr_headers_used=not boot,
 phase1c_adaptive_width_regression=True,phase1d_benchmark_methods=len(b2['rows']),
 phase1d_aabb_overlap_status=rows2['aabb_only']['status'],
 phase1d_oriented_separation_status=rows2['oriented_candidate_axes']['status'],
 phase1d_all_separation_witnesses_replayed=all(rows2[n]['witness_replay'] for n in ('oriented_candidate_axes','dense_16_plus_oriented')),
 phase1d_footprint_projection_checks=audit['checked_projections'],
 phase1d_footprint_projection_misses=audit['misses'],
 safety_verifier_implemented=False,report_directory=str(p))
(p/'acceptance_summary.json').write_text(json.dumps(summary,indent=2)+'\n'); print(json.dumps(summary,indent=2))
PY
"$PYTHON_BIN" - "$REPORT_DIR" <<'PY'
from pathlib import Path
import hashlib,json,sys
root=Path.cwd(); out={}
for base in ('cpp','python','tests','scripts','docs','configs'):
 for p in sorted((root/base).rglob('*')):
  if p.is_file() and '__pycache__' not in p.parts: out[str(p.relative_to(root))]=hashlib.sha256(p.read_bytes()).hexdigest()
# The validator hashes executable/configuration inputs that define the test
# harness.  The paper and bibliography are documentation inputs and are
# intentionally optional: validation must remain runnable when a source
# package omits the manuscript or uses a different filename.
for name in ('CMakeLists.txt','pyproject.toml','PROGRESS.json'):
 p=root/name; out[name]=hashlib.sha256(p.read_bytes()).hexdigest()
for name in ('AnonymousSubmission2027_Phase2.tex','aaai2027_Phase2.bib'):
 p=root/name
 if p.is_file():
  out[name]=hashlib.sha256(p.read_bytes()).hexdigest()
Path(sys.argv[1],'source_sha256.json').write_text(json.dumps(out,indent=2)+'\n')
PY
printf '\nPASS: Phase 1A-1D numerical and geometry checks completed.\nREPORT_DIR=%s\n' "$REPORT_DIR"
