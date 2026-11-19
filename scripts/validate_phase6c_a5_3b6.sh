#!/usr/bin/env bash
# A5/3b-6 incumbent occupancy + clock support + label audits; scoped only.
# Acceptance is scoped. Cannot claim A5 full task-winning or full-support safety.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-python}"
BUILD_DIR="${A5_NATIVE_BUILD_DIR:-$ROOT/build_phase6c_a5_3b6}"
REPORT_DIR="${REPORT_DIR:-$ROOT/reports/phase6c_a5_3b6_$(date -u +%Y%m%dT%H%M%SZ)}"
mkdir -p "$REPORT_DIR"
export PYTEST_ADDOPTS=""
# Record all stderr (including Python import and shell errors) even if an early
# pipeline fails before its own report file is generated.
exec 2> >(tee -a "$REPORT_DIR/stderr.log" >&2)

STAGE=release_integrity
trap 'rc=$?; if [ "$rc" -ne 0 ]; then printf "{\"phase\":\"6C-A5/3b-6\",\"status\":\"ERROR\",\"returncode\":%s,\"stage\":\"%s\"}\n" "$rc" "$STAGE" > "$REPORT_DIR/phase6c_a5_3b6_acceptance_summary.json"; fi' EXIT
export PYTHONPATH="$ROOT/python${PYTHONPATH:+:$PYTHONPATH}"
export PYTEST_DISABLE_PLUGIN_AUTOLOAD="${PYTEST_DISABLE_PLUGIN_AUTOLOAD:-1}"
"$PYTHON_BIN" "$ROOT/scripts/verify_release.py" 2>&1 | tee "$REPORT_DIR/release_integrity.log"
STAGE=finite_audit
"$PYTHON_BIN" -m pytest -q "$ROOT/tests/test_a5_native_discovery.py" \
  "$ROOT/tests/test_phase6c_a5_finite.py" "$ROOT/tests/test_a5_exact_time.py" \
  --junitxml="$REPORT_DIR/finite_audit.xml" | tee "$REPORT_DIR/finite_audit.log"
STAGE=label_regression
"$PYTHON_BIN" "$ROOT/scripts/validate_phase6c_a_dependency_free.py" \
  "$ROOT/tests/test_phase6c_a5_logged_labels.py" \
  "$ROOT/tests/test_phase6c_a53_schedule.py" "$ROOT/tests/test_phase6c_a53_rule_models.py" \
  "$ROOT/tests/test_phase6c_a53b_interlock.py" "$ROOT/tests/test_phase6c_a53b_timestamp.py" \
  "$ROOT/tests/test_phase6c_a53b2_data_incident.py" "$ROOT/tests/test_phase6c_a53b2_wzdx.py" \
  "$ROOT/tests/test_phase6c_a53b_quality.py" "$ROOT/tests/test_phase6c_a53b_external_sources.py" \
  "$ROOT/tests/test_phase6c_a53b3_clocks.py" "$ROOT/tests/test_phase6c_a53b3_roadwork.py" "$ROOT/tests/test_phase6c_a53b3_waymax.py" "$ROOT/tests/test_phase6c_a54_models.py" "$ROOT/tests/test_phase6c_a55_preflight.py" "$ROOT/tests/test_phase6c_a56.py" \
  --junitxml="$REPORT_DIR/label_regression.xml" | tee "$REPORT_DIR/label_regression.log"
# Always rerun CMake configuration. On this gate, use a distinct build folder;
# no previous build is removed and no source checkout is overwritten.
STAGE=cmake_configure
cmake -S "$ROOT" -B "$BUILD_DIR" -DRAMPD_BUILD_TESTS=ON -DCMAKE_BUILD_TYPE=Release \
  2>&1 | tee "$REPORT_DIR/cmake_configure.log"
STAGE=cmake_build
cmake --build "$BUILD_DIR" -j "${A5_BUILD_JOBS:-4}" 2>&1 | tee "$REPORT_DIR/cmake_build.log"
export RAMPD_INTERVAL_LIB="$BUILD_DIR/librampd_interval.so"
STAGE=native_ctest
"$PYTHON_BIN" "$ROOT/scripts/check_native_ctest.py" "$BUILD_DIR" \
  --log "$REPORT_DIR/native_ctest.log" | tee "$REPORT_DIR/native_summary.json"
STAGE=a5_math_regression
"$PYTHON_BIN" -m pytest -q "$ROOT/tests/test_phase6c_a5_bridge.py" \
  "$ROOT/tests/test_phase6c_a5_task_tail.py" \
  "$ROOT/tests/test_phase6c_a53_mission.py" \
  "$ROOT/tests/test_phase6c_a53b_segmented.py" "$ROOT/tests/test_phase6c_a53b2_actors.py" \
  "$ROOT/tests/test_phase6c_a53b3_occupancy.py" "$ROOT/tests/test_phase6c_a54_message_native.py" "$ROOT/tests/test_phase6c_a55_native_sat.py" \
  "$ROOT/tests/test_phase6c_a5_finite.py" \
  "$ROOT/tests/test_sc_inner.py" \
  "$ROOT/tests/test_sc_a4_proof_audit.py" \
  "$ROOT/tests/test_phase4_protocol.py" \
  "$ROOT/tests/test_phase4_full.py" \
  "$ROOT/tests/test_picard.py" \
  "$ROOT/tests/test_footprint.py" \
  --junitxml="$REPORT_DIR/a5_math_regression.xml" | tee "$REPORT_DIR/a5_math_regression.log"
STAGE=all_pytest
"$PYTHON_BIN" -m pytest -q "$ROOT/tests" --junitxml="$REPORT_DIR/all_pytest.xml" \
  | tee "$REPORT_DIR/all_pytest.log"
STAGE=summary
"$PYTHON_BIN" - "$REPORT_DIR" <<'PY'
import json,sys,pathlib,xml.etree.ElementTree as ET
p=pathlib.Path(sys.argv[1])
counts={}
for name in ('finite_audit','label_regression','a5_math_regression','all_pytest'):
    root=ET.parse(p/(name+'.xml')).getroot()
    suites=[root] if root.tag=='testsuite' else root.findall('testsuite')
    if not suites or any(int(s.get(k,'0')) for s in suites for k in ('errors','failures','skipped')):
        raise SystemExit('failed/skipped/missing test suite: '+name)
    counts[name]=sum(int(s.get('tests','0')) for s in suites)
    if counts[name]<=0: raise SystemExit('empty test suite: '+name)
if counts['all_pytest']<634 or counts['label_regression']<199: raise SystemExit('regression count smaller than A56 expected baseline')
summary={"phase":"6C-A5/3b-6", "status":"DECLARED_JOINT_GUARD_AND_SIM_PREFLIGHT_PASS",
         "scope":"DECLARED_FINITE_PRECOMPILED_MESSAGE_HISTORY_AND_RECTANGULAR_RESOURCE_MISSION",
         "test_counts":counts,"native_tests":3,"rational_endpoint_replay_tested":True,
         "synthetic_task_tail_verified":True,"declared_absolute_mission_verified":True,
         "declared_actor_envelopes_tested":True,"incumbent_resource_proof_tested":True,"single_switch_schedule_fixture_tested":True,"message_partition_fixture_tested":True,"declared_history_message_mission_tested":True,"dynamic_guard_declared_joint_cases_tested":True,"simulator_preflight_fixtures_tested":True,"sumo_runtime_verified":False,"waymax_response_runtime_verified":False,"full_message_support_integrated":False,"real_roadwork_audited":False,"incident_reference_fixtures_tested":True,"rule_reference_fixtures_tested":True,"simulator_labels_generated":False,"learned_model_trained":False,
         "real_scene_full_support_certified":False,
         "real_task_terminal_tail_verified":False,
         "model_completeness_outside_declared_toy_world":False,
         "training_complete":False, "datasets_used":False, "simulators_used":False}
(p/'phase6c_a5_3b6_acceptance_summary.json').write_text(json.dumps(summary,indent=2)+'\n')
print(json.dumps(summary,indent=2))
PY
echo "A5_3B6_SCOPED_GATE_PASS report=$REPORT_DIR"
