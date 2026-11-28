# Phase7B/C server runbook

Keep version 1.0.0.dev0, unzip in new empty directory. No prior caches copied into release.

```bash
conda activate mfrp
mkdir -p /home/senzeyu2/code/RAMP-D_transition
cd /home/senzeyu2/code/RAMP-D_transition
unzip -q /path/to/RAMP-D_v1.0.0-dev_phase7bc_transition.zip
python scripts/verify_release.py
bash scripts/validate_learning_pilot.sh
bash scripts/validate_cleanup_regression.sh
```

## 1. Frozen fact model: no full retrain
```bash
C=/actual/path/to/factual_500_freshdev
R=/actual/path/to/local_radial_17
mkdir -p reports
python scripts/audit_factual_checkpoint.py --cache "$C" --run "$R" --output reports/factual_state_audit.json
python scripts/diagnose_motion_state.py --cache "$C" --checkpoint "$R" --output reports/frozen_motion_probe.json
```
Old model weights only with exact matching manifest and summary. Compare start/no-start ADE, start/deceleration AP, raw vs frozen token. No need more modeq or ranker training on same dev. Freeze independent test registry before any final evaluation; do not use new test for selecting architecture. Exact record identity is not geographic/parent split; upload manifest and summary first, not whole raw WOMD. For final test, prepare a fresh excluded validation manifest using existing fresh-validation option and verify exact train records; evaluating an old checkpoint requires a separately scoped frozen test evaluator (not the strict replay script above). Do not retrain on that test.

## 2. Transition experiments (CPU, model-only)
```bash
python scripts/run_shared_resource_pilot.py --families 8 --transition-heads --train-heads --output reports/shared_transition
python scripts/run_shared_resource_pilot.py --families 8 --transition-heads --heterogeneous --protocol-shift --finite-teacher --output reports/shared_heterogeneous
```
Existing output directories rejected. Compare change AP, Brier/NLL, time MAE for actual changed samples and geometry baseline; 0 means no change within H=8, 4 s. Neither finite teacher nor sampled occupation is Native proof. The shift has heldout initial families but only four runs, not broad generalization. Keep all failure/unknown masks. Expected 24/32 runs, six transition head comparisons (three heads, two feature variants), 4 shift runs, finite_teacher.json. No real-world/formal heads.

## 3. Source topology and delivery coverage
```bash
for p in 0 0.5 1; do
 python scripts/run_rule_response.py --manifest "$C/manifest.json" --extend-route --prepend-route --strict-route --recipient-policy route_equipped --recipient-probability "$p" --recipient-seed 7 --clock-profile no_ego_delivery --reaction-delay .3 --visual-range 25 --physical-on .8 --physical-off 4 --limit 50 --steps 60 --plots --output "reports/delivery_${p}"
done
```
Ego no digital delivery; 0/0.5/1 applies to modeled relevant non-ego actors. Not empirical. Use same initial families, preserve rejects. For law-only clock intervention hold physical-on/off, messages and plans fixed explicitly; use original pair spec reconfiguration for identical initial states. Source topology audit only with raw/normalized record, not cache. No forced route extension at branches. Export model evidence if desired: `python scripts/export_projected_evidence.py --pairs reports/delivery_0.5/pairs.jsonl --output reports/delivery_evidence.jsonl --geometry-output reports/delivery_geometry.jsonl`.

## 4. Native independent work
```bash
cmake -S . -B build_native -DCMAKE_BUILD_TYPE=Release
cmake --build build_native -j 4
export A5_NATIVE_BUILD_DIR="$PWD/build_native"
export RAMPD_INTERVAL_LIB="$PWD/build_native/librampd_interval.so"
bash scripts/validate_native_regression.sh
ctest --test-dir build_native --output-on-failure
```
MPFR/GMP development libraries required, no fake fallback. Need representative full 6D common action, complete multi-actor SafeTube, observation support, task-accepting rank tail and independent replay. Current finite reference is only exact for its scalar WAIT/GO domain; forced wait bound not ICG.

## Return files
P0 new factual audit and frozen probe, original manifest/summary; shared_heterogeneous/summary.json and finite_teacher.json, shared_transition/summary.json, native logs, delivery summaries with raw source route audit (pairs optional, keep rejected records). For actual next physical adapter: same-map SUMO/CARLA polygon, lane connections/landmark transforms, TLS actual state and tick authority, full footprint/roster and clear logs; 5–10 representative families, two directions and delayed/lost readback. No large inventory required.
