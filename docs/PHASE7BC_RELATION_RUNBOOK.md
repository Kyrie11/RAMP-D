# Phase7BC relation — server runbook (1.0.0.dev0)
All new outputs must be under `reports/phase7bc_relation/`. Use fresh output subdirectories; keep previous reports and source. Commands are Bash. The declarations in this pilot are not real-world or Native proof.

```bash
conda activate mfrp
mkdir -p /home/senzeyu2/code/RAMP-D_relation
cd /home/senzeyu2/code/RAMP-D_relation
unzip -q /path/to/RAMP-D_v1.0.0-dev_phase7bc_relation.zip
R="$PWD/reports/phase7bc_relation"
mkdir -p "$R"
set -o pipefail
python scripts/verify_release.py | tee "$R/release_integrity.log"
REPORT_DIR="$R/learning_regression" bash scripts/validate_learning_pilot.sh
REPORT_DIR="$R/cleanup_regression" bash scripts/validate_cleanup_regression.sh
```

## 1. Independently trained source-relation heads (main experiment)
CPU, fixed budget, training families 0–5, heldout 6–8. In matched evaluation public protocol durations are seen in training; shifted durations are 24 green / 4 clear ticks. The config is assumed publicly disclosed, not controller private progress. H=8 ticks (4 s). No new factual training. Run 3 seeds if resources allow; seed 7 is the local pilot.

```bash
for seed in 7 17 27; do
  python scripts/run_relation_pilot.py --output "$R/relation_${seed}" --epochs 15 --seed "$seed" | tee "$R/relation_${seed}.log"
  python scripts/replay_relation_pilot.py --run "$R/relation_${seed}" --output "$R/relation_${seed}_replay.json"
done
python scripts/run_relation_pilot.py --output "$R/no_protocol" --epochs 15 --heads event observation --variants gated --hide-protocol
for source in neighbor resource; do
  python scripts/run_relation_pilot.py --output "$R/no_${source}" --epochs 15 --heads start --variants flat --drop-source "$source"
done
```
No private per-actor receipts enter features. The start label refers to currently stationary non-ego non-terminal vehicles moving within H in the affine model, not human intent. For Event/Observation report NLL, change AP, conditional-time MAE. For Occupancy report BCE and future occupancy-change AP against geometric CV. For start compare public-context histogram (training-only) and AP/Brier. Do not choose the model from shifted metrics alone; treat these families as development, not final test. Select flat/uniform/gated only after replicated comparisons; no real-world or formal-head authorization.

## 2. Auditable event mark, future confirmed permit, finite mathematical reference
```bash
python scripts/run_shared_resource_pilot.py --families 8 --heterogeneous --transition-heads --protocol-shift --finite-teacher --marked-evidence --output "$R/shared_marked"
```
`marked_evidence.jsonl` contains first-change time, conditional next command/observed permit, future true confirmed A/B permit and ego-observed A permit. No change in H masks mark; None with valid observation mark is loss of confirmed permission (not proof of actual physical red). Evidence-only; future confirmed entry permit is not collision-free access or SC. `finite_criticality.json` gives exact leave-one-world changes within the bounded WAIT/GO model. No formal ICG authorization.

## 3. Recheck existing three delivery archives against original manifest
```bash
C=/actual/path/to/factual_500_freshdev
D=/actual/path/to/previous/reports
python scripts/audit_delivery_collection.py --zero "$D/delivery_0.zip" --half "$D/delivery_0.5.zip" --full "$D/delivery_1.zip" --manifest "$C/manifest.json" --output "$R/delivery_source_audit.json"
python scripts/check_route_hypotheses.py --manifest "$C/manifest.json" --limit 50 --output "$R/route_hypotheses.json"
```
Use the exact archive paths or paths to the three pairs.jsonl. `--manifest` rereads only requested source records, verifies their bytes and reconstructs the normalized map and original projected initial actor roster, sizes and closure arc. If absent, fail, do not substitute another scene. `--inventory` is normalized-source-only (not raw byte verification). Map alternatives use exact shared endpoints and bounded topology enumeration; cap/unexplored counts are not completeness. Do not use logged future to choose route. For new runs explicitly set physical window and use same initial families:
```bash
for p in 0 0.5 1; do
  python scripts/run_rule_response.py --manifest "$C/manifest.json" --extend-route --prepend-route --strict-route --recipient-policy route_equipped --recipient-probability "$p" --recipient-seed 7 --clock-profile no_ego_delivery --reaction-delay .3 --visual-range 25 --physical-on .8 --physical-off 4 --limit 50 --steps 60 --plots --output "$R/delivery_${p}"
  python scripts/export_projected_evidence.py --pairs "$R/delivery_${p}/pairs.jsonl" --output "$R/delivery_${p}_evidence.jsonl" --geometry-output "$R/delivery_${p}_geometry.jsonl"
done
```
Scope is projected longitudinal model. Preserve rejects and early route ends, do not promote to physical simulation.

## 4. Optional frozen external factual evaluation (no training)
This is an exact-record-disjoint new evaluation, not a full geographic/recording-family proof. Keep the 99 old dev scenes out. The manifest construction must use a fresh validation split with original exclusions, and the original training quota must not shrink. Example (adjust max-shards to available corpus):
```bash
W=/data0/senzeyu2/dataset/waymo_open_dataset_motion_v_1_3_1/uncompressed/scenario
C=/actual/path/to/factual_500_freshdev
python scripts/prepare_factual_dataset.py --scenario-root "$W" --base-manifest "$C/manifest.json" --fresh-validation --train-limit 500 --validation-limit 300 --max-shards 60 --horizon 30 --output "$R/factual_external"
for seed in 7 17 27; do
  python scripts/evaluate_frozen_factual.py --original-cache "$C" --cache "$R/factual_external" --run "/actual/path/to/local_radial_${seed}" --output "$R/external_${seed}.json"
done
```
If original manifest quota differs, use its actual training count. The exact source/cache configuration and checkpoint SHA must match; this path uses validation only, no optimization. No result until server actual cache is prepared. For final paper, freeze a never-inspected test roster, check driving/geo families independently, report group/bootstrap and more horizons. Logged ego query is factual offline, not deployable clairvoyance.

## 5. Native and real physical adapter (P0, separate from learning)
```bash
cmake -S . -B build_relation_native -DCMAKE_BUILD_TYPE=Release 2>&1 | tee "$R/native_config.log"
cmake --build build_relation_native -j 4 2>&1 | tee "$R/native_build.log"
export A5_NATIVE_BUILD_DIR="$PWD/build_relation_native"
export RAMPD_INTERVAL_LIB="$PWD/build_relation_native/librampd_interval.so"
REPORT_DIR="$R/native_regression" bash scripts/validate_native_regression.sh
ctest --test-dir build_relation_native --output-on-failure | tee "$R/ctest.log"
```
MPFR/GMP dev headers required; no fallback. Need actual CARLA/SUMO common polygon, complete actor roster, physical footprints, controller version/readback, timing and continuous swept clear evidence. `sampled_polygon_occupancy` accepts actual polygon footprints for sampled checks only, always returns `prior_swept_empty=None`. Cannot synthesize continuous empty from samples. Neither simulator is installed here. A complete Native SC, actual ICG, continuous margin or critical-mode formal teacher remains pending.

## Return small evidence first
`release_integrity.log`, JUnit/logs, `relation_*/summary.json`, `relation_*_replay.json`, ablation summaries, `shared_marked/summary.json`, `finite_criticality.json`, delivery source audit and route hypotheses summary/selected plots, external evaluation reports, Native reports and CTest. No large raw TFRecord required unless selected source debugging. Everything remains under `$R`.
