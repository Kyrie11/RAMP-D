#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPORT_DIR="${REPORT_DIR:-$ROOT/reports/a59_1b0o_$(date -u +%Y%m%dT%H%M%SZ)}"
[ ! -e "$REPORT_DIR" ] || { echo REFUSE_EXISTING_REPORT_DIR >&2; exit 4; }
mkdir -p "$REPORT_DIR"
export PYTHONPATH="$ROOT/python${PYTHONPATH:+:$PYTHONPATH}"
export PYTEST_DISABLE_PLUGIN_AUTOLOAD=1
STAGE=manifest
trap 'rc=$?; if [ "$rc" -ne 0 ]; then printf "{\"status\":\"ERROR\",\"stage\":\"%s\",\"exit_code\":%d}\n" "$STAGE" "$rc" > "$REPORT_DIR/a69_acceptance.json"; fi' EXIT
python "$ROOT/scripts/verify_release.py" | tee "$REPORT_DIR/manifest.log"
STAGE=a69
python -m pytest -q "$ROOT/tests/test_a69_three_tracks.py" --junitxml="$REPORT_DIR/a69.xml" | tee "$REPORT_DIR/a69.log"
STAGE=full
python -m pytest -q "$ROOT/tests" --junitxml="$REPORT_DIR/full.xml" | tee "$REPORT_DIR/full.log"
STAGE=native
[ -n "${A5_NATIVE_BUILD_DIR:-}" ] && [ -f "${RAMPD_INTERVAL_LIB:-}" ] || { echo NEW_NATIVE_BUILD_REQUIRED >&2; exit 4; }
ctest --test-dir "$A5_NATIVE_BUILD_DIR" --output-on-failure --output-junit "$REPORT_DIR/native.xml" | tee "$REPORT_DIR/native.log"
STAGE=carla-replay
python "$ROOT/scripts/a69_review_three_tracks.py" \
  --repeat "1=$ROOT/tests/fixtures/a68_combined_repeat1.json" \
  --repeat "2=$ROOT/tests/fixtures/a68_combined_repeat2.json" \
  --repeat "3=$ROOT/tests/fixtures/a68_combined_repeat3.json" \
  --output "$REPORT_DIR/three_tracks.json" | tee "$REPORT_DIR/three_tracks.log"
STAGE=summary
python - "$REPORT_DIR" <<'PY'
import json,pathlib,sys,xml.etree.ElementTree as ET
r=pathlib.Path(sys.argv[1]); stats={}
for name in ('a69','full','native'):
    x=ET.parse(r/(name+'.xml')).getroot()
    nodes=[x] if x.tag=='testsuite' else x.findall('testsuite')
    if not nodes:raise RuntimeError('NO_JUNIT_SUITES:'+name)
    counts={k:sum(int(n.get(k,'0')) for n in nodes) for k in ('tests','failures','errors','skipped')}
    if any(counts[k] for k in ('failures','errors','skipped')):raise RuntimeError('NONZERO_FAILURES:'+name+str(counts))
    stats[name]=counts
if stats['a69']['tests']<34 or stats['full']['tests']<909 or stats['native']['tests']!=3:
    raise RuntimeError('INSUFFICIENT_COVERAGE:'+str(stats))
t=json.loads((r/'three_tracks.json').read_text())
if t['physical']['carla_repeated_control']['status']!='DESCRIPTIVE_THREE_REPEAT_PROTOCOL_REPRODUCED_MODEL_REVIEW':
    raise RuntimeError('CARLA_REPLAY_INCOMPLETE')
if t['physical']['brake_one_factor_sweep']['status']!='REVIEW' or any(t['evidence']['eight_supervised_label_masks'].values()):
    raise RuntimeError('A69_FAIL_CLOSED_NOT_ENFORCED')
result=dict(phase='6C-A59/1b-0O',status='CONDITIONAL_THREE_TRACK_SOFTWARE_ACCEPTANCE',counts=stats,
    math_joint_reference_only=True,full_native_hybrid_post=False,
    carla_three_fixed_protocol_repeats=True,carla_brake_factor_sweep_complete=False,
    vehicle_error_support_certified=False,sumo_carla_cosim_live=False,
    complete_teacher_replayed=False,full_sc=False,formal_loss_labels_produced=0)
(r/'a69_acceptance.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))
PY
