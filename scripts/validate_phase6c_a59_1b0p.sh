#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPORT_DIR="${REPORT_DIR:-$ROOT/reports/a70_$(date -u +%Y%m%dT%H%M%SZ)}"
[ ! -e "$REPORT_DIR" ] || { echo REFUSE_EXISTING_REPORT_DIR >&2; exit 4; }
mkdir -p "$REPORT_DIR"
export PYTHONPATH="$ROOT/python${PYTHONPATH:+:$PYTHONPATH}"
export PYTEST_DISABLE_PLUGIN_AUTOLOAD=1
STAGE=manifest
trap 'rc=$?; if [ "$rc" -ne 0 ]; then printf "{\"status\":\"ERROR\",\"stage\":\"%s\",\"exit_code\":%d}\n" "$STAGE" "$rc" > "$REPORT_DIR/a70_acceptance.json"; fi' EXIT
python "$ROOT/scripts/verify_release.py" | tee "$REPORT_DIR/manifest.log"
STAGE=targeted
python -m pytest -q "$ROOT/tests/test_a70_three_tracks.py" --junitxml="$REPORT_DIR/targeted.xml" | tee "$REPORT_DIR/targeted.log"
STAGE=full-sharded
# Four distinct processes cover every test file exactly once. Running the
# historical monolith in this environment exhausted a local execution budget
# without a JUnit exit report; sharding does not omit or relax any test.
mapfile -t TEST_FILES < <(find "$ROOT/tests" -maxdepth 1 -name 'test_*.py' -type f | sort)
[ "${#TEST_FILES[@]}" -gt 0 ] || { echo NO_TEST_FILES >&2; exit 4; }
SHARD_SIZE=$(( (${#TEST_FILES[@]} + 3) / 4 ))
for shard in 0 1 2 3; do
  begin=$((shard * SHARD_SIZE))
  [ "$begin" -lt "${#TEST_FILES[@]}" ] || break
  group=("${TEST_FILES[@]:begin:SHARD_SIZE}")
  STAGE="full-shard-$shard"
  python -m pytest -q "${group[@]}" --junitxml="$REPORT_DIR/full_${shard}.xml" | tee "$REPORT_DIR/full_${shard}.log"
done
STAGE=native
[ -n "${A5_NATIVE_BUILD_DIR:-}" ] && [ -f "${RAMPD_INTERVAL_LIB:-}" ] || { echo NEW_NATIVE_BUILD_REQUIRED >&2; exit 4; }
ctest --test-dir "$A5_NATIVE_BUILD_DIR" --output-on-failure --output-junit "$REPORT_DIR/native.xml" | tee "$REPORT_DIR/native.log"
STAGE=picard
python "$ROOT/scripts/a70_replay_native_microcase.py" --output-dir "$REPORT_DIR/native_microcase" | tee "$REPORT_DIR/native_microcase.log"
STAGE=carla-review
python "$ROOT/scripts/a70_review_brake_timecourses.py" \
 --arm b15="$ROOT/tests/fixtures/a70_brake_b15.json" \
 --arm b30="$ROOT/tests/fixtures/a70_brake_b30.json" \
 --arm b45="$ROOT/tests/fixtures/a70_brake_b45.json" \
 --output "$REPORT_DIR/brake_timecourse.json" | tee "$REPORT_DIR/brake_timecourse.log"
STAGE=summary
python - "$REPORT_DIR" <<'PY'
import json,pathlib,sys,xml.etree.ElementTree as ET
p=pathlib.Path(sys.argv[1]);stats={}
for name in ('targeted','full_0','full_1','full_2','full_3','native'):
  root=ET.parse(p/(name+'.xml')).getroot()
  nodes=[root] if root.tag=='testsuite' else root.findall('testsuite')
  if not nodes:raise RuntimeError('EMPTY_JUNIT:'+name)
  counts={k:sum(int(n.get(k,'0')) for n in nodes) for k in ('tests','failures','errors','skipped')}
  if any(counts[k] for k in ('failures','errors','skipped')):raise RuntimeError('NONZERO_TEST_OUTCOMES:'+name+str(counts))
  stats[name]=counts
if stats['targeted']['tests']<31 or sum(stats[k]['tests'] for k in ('full_0','full_1','full_2','full_3'))<940 or stats['native']['tests']!=3:
  raise RuntimeError('MISSING_EXPECTED_COVERAGE:'+str(stats))
m=json.loads((p/'native_microcase/manifest_report.json').read_text())
b=json.loads((p/'brake_timecourse.json').read_text())
if m['replayed_world_slabs']!=4 or m['full_sc'] or b['status']!='DESCRIPTIVE_TIMECOURSES_RECOMPUTED_MODEL_UNRESOLVED' or b['safe_training_labels_allowed']:
  raise RuntimeError('A70_FAIL_CLOSED_REQUIREMENTS_FAILED')
r=dict(phase='6C-A59/1b-0P',status='CONDITIONAL_A70_THREE_TRACK_SOFTWARE_ACCEPTANCE',counts=stats,
 native_6d_mixed_clock_segments_replayed=4,full_hybrid_resource_post=False,
 physical_brake_three_arm_timecourses=True,physical_error_enclosure_certified=False,
 full_sc=False,all_eight_formal_labels_certified=False)
(p/'a70_acceptance.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r,indent=2))
PY
