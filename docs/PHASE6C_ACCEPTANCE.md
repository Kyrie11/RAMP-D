# Phase 6C acceptance report: scoped candidate, NOT full paper reproduction

## Objective -> implementation -> test -> failed cases -> verdict

**Objective**: follow `PHASE6_PLAN.md` for 6C while respecting latest TeX. Reopen Phase6B source contracts, sample train and validation, introduce a leakage-free prediction proposal baseline, a non-certifying soft rule-priority hook and CARLA/SUMO synchronized clock smoke.

**Code**: `python/rampd_core/{record_adapters,scene_schema,phase6c,clock_ledger}.py`, `scripts/{evaluate_phase6c,smoke_phase6c_cosim,validate_phase6c,validate_phase6c_pure}.py`, `tests/{test_phase6b_record_adapters,test_phase6c}.py` plus corrected 6A audit and 6B script.

**Tests**: dedicated 6A–6C synthetic regression **29/29 PASS** via `scripts/validate_phase6c_pure.sh`. This bypasses only unavailable package-native initialization; it does not run or mock any MPFR arithmetic. Syntax/compile checks pass. Official AV2 real Parquet, full native regression, and true co-sim run **not yet exercised** in this local environment. Original uploaded server result remains WOMD validation PASS (3 scenes), AV2 validation SKIP.

**Failure analysis**: see `docs/PHASE6C_FAILURE_LOG.md` and `docs/PHASE6C_MATHEMATICAL_AUDIT.md`. Parser identity mismatches are fixed at code level, but server confirmation is pending. The co-sim wrapper verifies fixed ticks and frame monotonicity, and records (but does not prove correct identity/geometry of) bridged agent counts; sensor/receipt clocks require another iteration.

**Verdict**: `PHASE6C_SCOPED_CANDIDATE_READY_FOR_SERVER_VALIDATION`, not full 6C accepted and not ICAPS final-method reproduction. Explicit: `full_support_certified=false`, `task_winning_certified=false`, `model_trained=false`, `rulenet_trained=false`, `real_scene_closed_loop_planning_certified=false`.

## On-server minimal command sequence

```bash
# Inside newly extracted project directory; use your tested mfrp environment.
conda activate mfrp
python -m pip install -r requirements-test.txt
python -m pip install pyarrow     # only if parquet engine missing; do not disturb existing working deps

# First repeat repaired Phase6B real-data check:
PYTHON_BIN="$(command -v python)" bash scripts/validate_phase6b.sh

# For code-only diagnostic without simulators (will correctly end SKIP):
PYTHON_BIN="$(command -v python)" bash scripts/validate_phase6c.sh

# To run the bounded official CARLA 0.9.16 / SUMO 1.20 smoke,
# separately start CARLA 0.9.16 (no other synchronous client or bridge):
# ./CarlaUE4.sh /Game/Carla/Maps/Town04 -RenderOffScreen -carla-rpc-port=2000
# Ensure SUMO_HOME points to a real SUMO 1.20 installation with tools.
# Ensure config matches CARLA Town04 and references valid SUMO net/routes:
export SUMO_HOME=/path/to/your/sumo/home
export CARLA_COSIM_DIR=/path/to/CARLA_0.9.16/Co-Simulation/Sumo
export SUMO_CONFIG="$CARLA_COSIM_DIR/examples/Town04.sumocfg"
export CARLA_MAP=Town04
export SIM_DT=0.05
export COSIM_STEPS=20
PYTHON_BIN="$(command -v python)" bash scripts/validate_phase6c.sh
```

If no `build_phase3/CTestTestfile.cmake` exists, **build native according to the previous validated Phase3/Phase4 workflow**, not with a fake MPFR header. A reported SKIP is actionable: review `phase6c_acceptance_summary.json`, `phase6c_dataset_gate.json`, `phase6c_cosim_smoke.json` and `all_pytest.log`, packaged into `reports/RAMP-D_Phase6C_server_report.zip`.

## Post-smoke follow-up priority

(1) Fix any true server AV2 parsing or Town04 synchronization failures. (2) Introduce real train-only learned joint action-conditioned predictor and RuleNet soft features, no proof support truncation. (3) Calibrate ego geometry and add protocol/sensor four-clock logging, paired interventions and occupancy from real polygons. (4) Implement certified task tails, ranked inner winning set and ICG based on identical common prefixes; this is indispensable for the revised manuscript. (5) Add exact small finite-game oracle for negative viability, true dynamic scheduling, runtime/method ablations, then continuous real-scene verification under declared calibration. Do not treat the order as authority to skip a failed earlier gate.
