#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPORT_DIR="${REPORT_DIR:-$ROOT/reports/a59_1b0n_$(date -u +%Y%m%dT%H%M%SZ)}"
[ ! -e "$REPORT_DIR" ] || { echo REFUSE_EXISTING_REPORT_DIR >&2; exit 4; }
mkdir -p "$REPORT_DIR"
export PYTHONPATH="$ROOT/python${PYTHONPATH:+:$PYTHONPATH}"
export PYTEST_DISABLE_PLUGIN_AUTOLOAD=1
STAGE=release
trap 'rc=$?; if [ "$rc" -ne 0 ]; then printf "{\"status\":\"ERROR\",\"stage\":\"%s\",\"exit_code\":%d}\n" "$STAGE" "$rc" > "$REPORT_DIR/a68_acceptance.json"; fi' EXIT
python "$ROOT/scripts/verify_release.py" | tee "$REPORT_DIR/manifest.log"
STAGE=targeted
python -m pytest -q "$ROOT/tests/test_a68_parallel_three_tracks.py" --junitxml="$REPORT_DIR/targeted.xml" | tee "$REPORT_DIR/targeted.log"
STAGE=full
python -m pytest -q "$ROOT/tests" --junitxml="$REPORT_DIR/full.xml" | tee "$REPORT_DIR/full.log"
STAGE=native
[ -n "${A5_NATIVE_BUILD_DIR:-}" ] && [ -f "${RAMPD_INTERVAL_LIB:-}" ] || { echo NEW_NATIVE_BUILD_REQUIRED >&2; exit 4; }
ctest --test-dir "$A5_NATIVE_BUILD_DIR" --output-on-failure --output-junit "$REPORT_DIR/native.xml" | tee "$REPORT_DIR/native.log"
STAGE=three_tracks
python "$ROOT/scripts/a68_review_parallel_tracks.py" \
  --run "1=$ROOT/tests/fixtures/a68_combined_repeat1.json" \
  --run "2=$ROOT/tests/fixtures/a68_combined_repeat2.json" \
  --run "3=$ROOT/tests/fixtures/a68_combined_repeat3.json" \
  --output "$REPORT_DIR/three_tracks.json" | tee "$REPORT_DIR/three_tracks.log"
STAGE=summary
python - "$REPORT_DIR" <<'PY'
import json,pathlib,sys,xml.etree.ElementTree as ET
r=pathlib.Path(sys.argv[1]);stats={}
for label in ('targeted','full','native'):
    rt=ET.parse(r/(label+'.xml')).getroot()
    suites=([rt] if rt.tag=='testsuite' else rt.findall('testsuite'))
    if not suites:raise RuntimeError('MISSING_JUNIT_SUITE:'+label)
    counts={k:sum(int(s.get(k,'0')) for s in suites) for k in ('tests','failures','errors','skipped')}
    if any(counts[k] for k in ('failures','errors','skipped')):raise RuntimeError('NONZERO_JUNIT_FAILURES:'+label+str(counts))
    stats[label]=counts
if stats['targeted']['tests']<42 or stats['full']['tests']<875 or stats['native']['tests']!=3:
    raise RuntimeError('INSUFFICIENT_TEST_COVERAGE:'+str(stats))
tr=json.loads((r/'three_tracks.json').read_text())
if tr['physical']['status']!='DESCRIPTIVE_THREE_REPEAT_PROTOCOL_REPRODUCED_MODEL_REVIEW' or any(tr['evidence_supervision']['formal_masks'].values()):
    raise RuntimeError('A68_PURE_EVIDENCE_GATE_NOT_AS_EXPECTED')
summary={'phase':'6C-A59/1b-0N','status':'CONDITIONAL_A68_THREE_TRACK_LOCAL_SOFTWARE_GATE_PASS',
         'counts':stats,'carla_repeats_diagnostic':'3/3 deterministic, anomalous braking NOT calibrated',
         'real_carla_ticked_in_this_gate':False,'real_sumo_ticked_in_this_gate':False,
         'new_native_library_built_by_this_script':False,
         'exact_affine_reference_checked':True,'full_hybrid_native_picard_post_verified':False,
         'traffic_authority_physically_replayed':False,'vehicle_dynamic_error_support_certified':False,
         'teacher_and_eight_formal_labels_certified':False}
(r/'a68_acceptance.json').write_text(json.dumps(summary,indent=2,ensure_ascii=False)+'\n')
print(json.dumps(summary,indent=2,ensure_ascii=False))
PY
