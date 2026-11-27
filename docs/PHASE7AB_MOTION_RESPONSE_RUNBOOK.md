# Server runbook — same v1.0.0.dev0

Do not overwrite earlier code/reports; unpack to a fresh directory.

```bash
conda activate mfrp
python scripts/verify_release.py
bash scripts/validate_learning_pilot.sh
bash scripts/validate_cleanup_regression.sh
```

Optional Shapely for 2D diagnostics: `python -c 'import shapely; print(shapely.__version__)'` (local 2.1.2). If absent install supported Shapely in the existing data environment. No MPFR required for learning.

## P0: fresh dev, fixed old diagnostic roster excluded
```bash
W=/data0/senzeyu2/dataset/waymo_open_dataset_motion_v_1_3_1/uncompressed/scenario
OLD=/actual/path/to/factual_200_fixedval
python scripts/prepare_factual_dataset.py --scenario-root "$W" \
  --base-manifest "$OLD/manifest.json" --fresh-validation \
  --train-limit 500 --validation-limit 100 --max-shards 40 --horizon 30 \
  --output reports/factual_500_freshdev
C=reports/factual_500_freshdev
python scripts/diagnose_motion_state.py --cache "$C" --output reports/motion_state_fresh.json
```
Inspect accepted/rejected; old 10 identities/digests/locations excluded; train identities kept. Exact identity only; no global log-family proof. This is new dev, not untouched final test. Prefer same device for all variants. If resource-limited run seed17 first, then 7/27. No need rebuild large inventory.

```bash
for seed in 7 17 27; do
  python scripts/train_factual.py --cache "$C" --output "reports/radial_${seed}" \
    --motion-context --objective radial_laplace --selection nll --modes 3 \
    --epochs 20 --batch-size 4 --seed "$seed" --device cuda
  python scripts/train_factual.py --cache "$C" --output "reports/local_radial_${seed}" \
    --motion-context --local-history --objective radial_laplace --selection nll \
    --modes 3 --epochs 20 --batch-size 4 --seed "$seed" --device cuda
done
python scripts/audit_factual_checkpoint.py --cache "$C" --run reports/local_radial_17 --output reports/local_radial_17_audit.json
```
CPU substitute if needed. For optional modes, append `--anchor-cv` (first entire scene CV; K>=2) and optionally `--trajectory-modes` (not together with `--query-modes`). Do not add both when comparing local history. To reproduce ranker use SAME old cache and uploaded base run, without changing calibration families:
```bash
R=/actual/path/to/mode_ranker
python scripts/train_mode_ranker.py --cache "$OLD" --base-run "$R" --rank-features motion --rank-epochs 60 --output reports/ranker_motion
```
NLL measured for each density; no comparing different density scale numbers without common scoring. Report Top-1, whole-scene oracle, CV/DCA, speed strata, macro, AP and number of positives. Freeze representation if no benefit beyond DCA; not necessary to win forecasting SOTA for planning paper.

## P1: actual raw route and explicit response clocks
```bash
for profile in nominal early delayed_effect late_receipt no_ego_delivery; do
  python scripts/run_rule_response.py --manifest "$C/manifest.json" --extend-route --prepend-route \
    --recipient-policy projected_nearest --clock-profile "$profile" --reaction-delay 0.3 \
    --visual-range 25 --limit 50 --steps 60 --plots --output "reports/response_${profile}"
done
python scripts/export_projected_evidence.py --pairs reports/response_nominal/pairs.jsonl \
  --output reports/response_nominal_evidence.jsonl --geometry-output reports/response_nominal_2d.jsonl
```
Visual range and .3s lag are scenario factors, not measured values. To isolate each factor omit both, then `--reaction-delay 0.3` only, then both. `--physical-on` and `--physical-off` (relative seconds, both supplied with visual-range) allow different physical windows. No actual physical blocking. `--recipient-policy all_current_nearest` is legacy comparator. On archived paired logs, use `--pair-input /actual/path/pairs.jsonl` instead of manifest, with same clock profile preserved and no extend/prepend. Parent source digest retained; not raw replay. In old cache restore widths with `--cache "$OLD"` if available; otherwise geometry unknown. 2D ribbon width explicitly declared default 3.5m, not map-derived lane boundary. Do not enable training. Report both full/truncated, actor exclusions, response/nonresponse, collision/violation kinds, clock-boundary UNKNOWN, no-event absent vs unknown. Include geometry and timing plots for 5–10 accepted and rejected scene families.

## P1: Native independent
```bash
cmake -S . -B build_native -DCMAKE_BUILD_TYPE=Release
cmake --build build_native -j 4
export A5_NATIVE_BUILD_DIR="$PWD/build_native"
export RAMPD_INTERVAL_LIB="$PWD/build_native/librampd_interval.so"
bash scripts/validate_native_regression.sh
ctest --test-dir build_native --output-on-failure
```

Return manifest/summary, all factual train/audit reports, motion-state report, response summary plus a few full pairs and BEVs, sampled 2D counts, Native logs. No need upload full WOMD shards or huge inventory. Real co-sim next needs same-map ground landmarks, road/lane/boundary mapping, controller state/ACK and actual per-agent observations. WZDx versioned historical feed snapshots if available; no need new generic papers to finish the core. 
