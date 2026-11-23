#!/usr/bin/env bash
# Phase 6C-A59/1b-0: geometry/clock/conflict prerequisite; never a SC certificate.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-python}"
REPORT_DIR="${REPORT_DIR:-$ROOT/reports/phase6c_a59_1b0_$(date -u +%Y%m%dT%H%M%SZ)}"
if [ -e "$REPORT_DIR" ]; then echo "REVIEW_EXISTING_REPORT_DIR=$REPORT_DIR" >&2; exit 4; fi
mkdir -p "$REPORT_DIR"
export PYTHONPATH="$ROOT/python${PYTHONPATH:+:$PYTHONPATH}"
export PYTEST_DISABLE_PLUGIN_AUTOLOAD="${PYTEST_DISABLE_PLUGIN_AUTOLOAD:-1}"
export A5_NATIVE_BUILD_DIR="${A5_NATIVE_BUILD_DIR:-$ROOT/build_phase6c_a59_0}"
STAGE=release
trap 'rc=$?; if [ "$rc" -ne 0 ]; then printf "{\"phase\":\"6C-A59/1b-0\",\"status\":\"ERROR\",\"stage\":\"%s\",\"returncode\":%s}\n" "$STAGE" "$rc" > "$REPORT_DIR/phase6c_a59_1b0_acceptance.json"; fi' EXIT
"$PYTHON_BIN" "$ROOT/scripts/verify_release.py" | tee "$REPORT_DIR/release.log"
STAGE=incumbent_a59_1a
REPORT_DIR="$REPORT_DIR/incumbent_a59_1a" bash "$ROOT/scripts/validate_phase6c_a59_1a.sh" | tee "$REPORT_DIR/incumbent_a59_1a.log"
export RAMPD_INTERVAL_LIB="$A5_NATIVE_BUILD_DIR/librampd_interval.so"
STAGE=a59_1b0_pure
"$PYTHON_BIN" -m pytest -q "$ROOT/tests/test_a61_carla_geometry_and_gate.py" \
  --junitxml="$REPORT_DIR/a59_1b0_pure.xml" | tee "$REPORT_DIR/a59_1b0_pure.log"
STAGE=full_pytest
"$PYTHON_BIN" -m pytest -q "$ROOT/tests" \
  --junitxml="$REPORT_DIR/full_pytest.xml" | tee "$REPORT_DIR/full_pytest.log"
STAGE=optional_carla_offline
if [ -n "${CARLA_TRIAL_JSON:-}" ]; then
  "$PYTHON_BIN" "$ROOT/scripts/a61_review_physical_evidence.py" \
    --input "$CARLA_TRIAL_JSON" --output "$REPORT_DIR/carla_descriptive_review.json" \
    --repeats "${CARLA_REPEATS:-3}" | tee "$REPORT_DIR/carla_descriptive_review.log"
fi
STAGE=summary
"$PYTHON_BIN" - "$REPORT_DIR" <<'PY'
import json,pathlib,sys,xml.etree.ElementTree as E
root=pathlib.Path(sys.argv[1])
def check(p):
    x=E.parse(p).getroot();ss=[x] if x.tag=='testsuite' else x.findall('testsuite')
    if not ss or any(int(s.get(y,'0')) for s in ss for y in ('failures','errors','skipped')):
        raise SystemExit('tests fail/skip or empty: '+str(p))
    return sum(int(s.get('tests','0')) for s in ss)
prior=json.loads((root/'incumbent_a59_1a'/'phase6c_a59_1a_acceptance.json').read_text())
pure=check(root/'a59_1b0_pure.xml');full=check(root/'full_pytest.xml')
if prior['status']!='CONDITIONAL_A59_1A_SUBGATES_PASS' or pure<15 or full<740:
    raise SystemExit('INSUFFICIENT_A59_1B0_REGRESSION_EVIDENCE')
r={'phase':'6C-A59/1b-0','status':'CONDITIONAL_EVIDENCE_PREPROCESSOR_AND_REGRESSION_PASS',
   'full_pytest':full,'new_pure_tests':pure,'incumbent_a59_1a':True,
   'actor_geometry_reconstruction_implemented':True,
   'carla_0916_wheel_steer_enum_corrected':True,
   'carla_pre_tick_metadata_staleness_corrected':True,
   'exact_joint_clock_partition_preprocessor_implemented':True,
   'declared_rectangular_multiresource_conflict_screen_implemented':True,
   'actual_hybrid_native_picard_substep_integrated':False,
   'full_protocol_and_public_observation_support_certified':False,
   'general_polygon_resource_and_terminal_SC_certified':False,
   'carla_sumo_real_synchronization_certified':False,
   'vehicle_dynamics_error_envelope_certified':False,
   'eight_supervision_labels_certified':False,
   'no_training_viability_or_deadline_labels_emitted':True}
(root/'phase6c_a59_1b0_acceptance.json').write_text(json.dumps(r,indent=2)+'\n')
print(json.dumps(r,indent=2))
PY
printf 'A59_1B0_CONDITIONAL_PASS report=%s\n' "$REPORT_DIR"
