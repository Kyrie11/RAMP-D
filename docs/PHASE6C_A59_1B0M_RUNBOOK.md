# A59/1b-0M — server validation & incremental CARLA 0.9.16 runbook

## 1) New checkout, no stale CMakeCache
```bash
conda activate mfrp
mkdir -p /home/senzeyu2/code/RAMP-D_A59_1b0M
unzip -q RAMP-D_Phase6C_A59_1b0M.zip -d /home/senzeyu2/code/RAMP-D_A59_1b0M
cd /home/senzeyu2/code/RAMP-D_A59_1b0M
cmake -S . -B build_a59_1b0m -DCMAKE_BUILD_TYPE=Release
cmake --build build_a59_1b0m -j 4
export A5_NATIVE_BUILD_DIR="$PWD/build_a59_1b0m"
export RAMPD_INTERVAL_LIB="$A5_NATIVE_BUILD_DIR/librampd_interval.so"
python scripts/verify_release.py
bash scripts/validate_phase6c_a59_1b0m.sh
```
Expected: **>=833 Python**, **>=18 targeted**, **3/3 CTest**, no failures or skips. Preserve entire new report directory. If CMake finds stale paths, delete only the *new scratch build* after checking no source files are inside; do not override old acceptance reports.

## 2) Review the original combined trace without running CARLA
```bash
mkdir -p reports/a67_carla
python scripts/a67_review_carla_combined.py \
  --input /path/to/town06_5ms_combined_raw.json \
  --output reports/a67_carla/combined_uploaded_review.json
```
Expected: `DIAGNOSTIC_REPEAT_ELIGIBLE_MODEL_REVIEW_NOT_CALIBRATED`; gross torque-only-model discrepancy remains a REVIEW reason and none of the eight guaranteed supervision sources is certified.

## 3) Three *diagnostic repeats* of the same 5 m/s combined protocol
**Only** in isolated Town06 CARLA instance, no other ticking client, actor, Traffic Manager or synchronous bridge. `--confirm...` flags are user assertions, not measurement of isolation.
```bash
for run in 1 2 3; do
  python scripts/a60_carla_actor_trials.py --mode smoke \
    --host 127.0.0.1 --port 2000 --blueprint vehicle.tesla.model3 \
    --confirm-isolated-world --confirm-exclusive-tick \
    --site-spacing 2.0 --site-prefer-longest --fixed-delta 0.05 \
    --smoke-speed 5 --smoke-maneuver combined \
    --steer-fraction 0.03 --steer-pulse-s 0.15 \
    --combined-brake-fraction 0.45 \
    --output "reports/a67_carla/combined_5ms_045_repeat${run}.json" || break
done
python scripts/a67_review_combined_repeats.py \
  --run 1=reports/a67_carla/combined_5ms_045_repeat1.json \
  --run 2=reports/a67_carla/combined_5ms_045_repeat2.json \
  --run 3=reports/a67_carla/combined_5ms_045_repeat3.json \
  --output reports/a67_carla/combined_repeats_review.json
```
If any run fails, do **not** run the reviewer with absent paths; preserve failing JSON and audit independently. If repeated normalized responses are identical, that's reproducibility of a deterministic simulation only; it does NOT establish the uncertainty support.

## 4) Graded brake diagnostics: never pool distinct protocols
Run only after the 3-repeat pilot is understood. Separate raw JSON and review for each command. Use exactly one trial per brake fraction:
```bash
for brake in 0.15 0.30 0.45; do
  python scripts/a60_carla_actor_trials.py --mode smoke \
    --host 127.0.0.1 --port 2000 --blueprint vehicle.tesla.model3 \
    --confirm-isolated-world --confirm-exclusive-tick \
    --site-spacing 2.0 --site-prefer-longest --fixed-delta 0.05 \
    --smoke-speed 5 --smoke-maneuver combined \
    --steer-fraction 0.03 --steer-pulse-s 0.15 \
    --combined-brake-fraction "$brake" \
    --output "reports/a67_carla/combined_grade_${brake}.json" || break
done
```
The expected vehicle response is **not predeclared PASS**. For every file run `a67_review_carla_combined.py` using unique report filenames. Large accelerations, incomplete capture, or lane departure remain REVIEW. User should upload all raw output, all review JSON, full acceptance, and optionally synchronized bird's-eye video if numeric/visual discrepancy persists.

## 5) Parallel next stage (does not wait for 3 runs)
A59/1b-1: add actual Native per-slab MPFR integration, full world/Guard/resource/observation replay and goal-tail acceptance. SUMO: fresh directories and all missing control summaries. Waymax: full state/actuation conversion and counterfactual support. 511NY/ROADWork: explicit report-vs-physical event clocks. CARLA–SUMO: real physically matching network, unique tick, map registration and positive/negative ACK tests.
