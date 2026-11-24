# A71 server runbook — execute independent mathematics, physics and evidence gates

Use a NEW checkout, do NOT reuse CMake cache and do NOT delete the previous reports.

```bash
conda activate mfrp
mkdir -p /home/senzeyu2/code/RAMP-D_A59_1b0Q
unzip -q RAMP-D_Phase6C_A59_1b0Q.zip -d /home/senzeyu2/code/RAMP-D_A59_1b0Q
cd /home/senzeyu2/code/RAMP-D_A59_1b0Q
cmake -S . -B build_a71 -DCMAKE_BUILD_TYPE=Release
cmake --build build_a71 -j 4
export A5_NATIVE_BUILD_DIR="$PWD/build_a71"
export RAMPD_INTERVAL_LIB="$A5_NATIVE_BUILD_DIR/librampd_interval.so"
python scripts/verify_release.py
bash scripts/validate_phase6c_a59_1b0q.sh
```

A71 gate runs older A70 baseline (all tests in 4 shards, CTest and genuine two-world/four-slab Native MPFR/Picard microcase), then 29+ A71 pure tests, then native polygon far (conditional) and near (UNKNOWN) with real certificate replay. If any fail, retain REPORT_DIR and ALL logs and upload. Do NOT interpret conditional polygon exclusion as actual resource permission, SC viability or a trained label.

## A. CARLA control pairing and next factorial design

Pure 0.15 user-supplied and historical combined 0.15 are both independent source files. Run:

```bash
python scripts/a71_compare_carla_brake.py \
 --pure /path/to/brakeonly_b015_01.json \
 --combined /path/to/combined_b0.15.json \
 --output reports/a71_brake_vs_combined_015.json
```

For next real CARLA Town06 on dedicated port 2000, after verifying no other tick clients, first execute pure `brake` 0.30 and 0.45 with `--brake-only-fraction 0.30` and `0.45`, and reproduce pure 0.15. Hold steer to zero. Existing combined b0.15, b0.30, b0.45 correspond to steer 0.03 for 0.15s. Run each of 6 cells 3× with separate filenames; do not erase failures. A representative **pure brake** command:

```bash
python scripts/a60_carla_actor_trials.py \
 --mode smoke --host 127.0.0.1 --port 2000 \
 --blueprint vehicle.tesla.model3 \
 --confirm-isolated-world --confirm-exclusive-tick \
 --site-spacing 2.0 --site-prefer-longest --fixed-delta 0.05 \
 --smoke-speed 5 --smoke-maneuver brake --brake-only-fraction 0.30 \
 --output reports/a71_carla_brakeonly_b030_run01.json
```

The live runtime modifies the CARLA synchronous clock and spawns an actor; use only on a truly isolated experiment world. Keep actual PhysicsControl/wheels, weather, actor ID, before/after simulation clock, plan view and road lane evidence. Compare moving>=1m/s response separately from the low-speed stop/contact spike. Never derive real-world guaranteed deceleration or friction from one CARLA trace.

## B. SUMO/Traffic-Guard 12 new actual runs

```bash
bash scripts/a71_run_sumo_matrix.sh /home/senzeyu2/code/a71_sumo_campaign_20261124
```

Choose a directory that DOES NOT EXIST; do not choose the same one again. The runner performs 4 traffic profiles × 3 seeds (17,23,41), records raw roster, vehicles, signal command/readback each tick and independent per-run audit. Expected: `a71_campaign.json`, 12 reports `sumo_*.json`, 12 `*.signal_review.json`, each `.work/signal_trace.jsonl`. If any fail, preserve all raw evidence and console logs; the `a71_campaign` status must be REVIEW. This is a LOGICAL two-directed-edge corridor: signal readback is not a field barrier ACK, and does not prove one common physical lane, task tail or co-simulation.

For true shared resource next provide the SUMO `network.xml`, `routes.xml`, signal link indices and OpenDRIVE for the CARLA world. First do map/coordinate tests offline, then one tick master and actor-control authority in real co-simulation; do not transfer the current logical PASS to real shared lane.

## C. Waymax official IDM actual single-shard smoke and offline check

The existing historical `probe_waymax_response.py` uses an actual WOMD TFExample shard as the data loader and then creates an explicit **synthetic** pair of vehicles; neither the input shard nor IDM outputs prove real human pair-response. Use an existing TFExample training/validation `.tfrecord` shard, e.g. under `/data0/senzeyu2/dataset/waymo_open_dataset_motion_v_1_3_1/`, confirm actual file path first:

```bash
python scripts/probe_waymax_response.py --tf-example-file /path/to/one_actual_tfexample_shard.tfrecord \
 --steps 25 --lookahead-points 30 --ego-length 4.5 --follower-length 4.5 \
 --initial-offset 15 --profile constant --output reports/a71_waymax_idm_pair.json
python scripts/a71_review_waymax_idm.py \
 --input reports/a71_waymax_idm_pair.json --output reports/a71_waymax_idm_independent.json
```

Also run `--lookahead-points 60` and `120` into **different** output names. Compare net-space `initial_net_gap_idm_accel_mps2` vs geometric bumper gap; different lookahead is NOT proof of broad real-world behavior bounds. Save versions (`waymax`, `jax`, `dm-env`), source hash and any failing traceback.

## D. Actual 511NY CSV and ROADWork grouped templates -> auxiliary data

For uploaded/located 511NY CSV with `Event Type, Organization Name, State, Facility Name, Create Time, Close Time, Latitude, Longitude` equivalent case-insensitive headers:

```bash
python scripts/a71_normalize_511ny_csv.py --csv /path/to/511NY_Events.csv \
 --max-rows 10000 --output reports/a71_511ny_normalized.jsonl
python scripts/a71_export_auxiliary_sources.py \
 --normalized-511ny reports/a71_511ny_normalized.jsonl \
 --output reports/a71_511ny_auxiliary.jsonl
```

Any date parse failure, DST fold/gap or negative reported lifetime is quarantined. These are only REPORT time labels, NOT physical effectivity, road authority or receipt.

Use the historical grouped ROADWork JSONL source created by `scripts/a58_roadwork_templates.py` (do not pass raw COCO annotations directly to an adapter expecting the grouped schema):

```bash
python scripts/a71_export_auxiliary_sources.py \
 --roadwork-templates /path/to/roadwork_grouped_templates.jsonl \
 --output reports/a71_roadwork_auxiliary.jsonl
```

Image boxes stay pixels; empty annotations do not guarantee no workzone; no metric obstacle, formal safety certificate, event effectivity or eight formal head labels can be inferred from these auxiliary data alone.

## E. Source priorities to upload after running

Provide the entire `a71_acceptance.json` report directory (including Native CTest logs and four certificates), `a71_sumo_campaign_*` complete roster/signal traces, Waymax synthetic pair+independent audit, 511NY/ROADWork normalized JSONL + source audits (a small bounded sample suffices initially), CARLA pure 0.30/0.45 original JSONs. For real CARLA/SUMO registration also provide actual OpenDRIVE and SUMO `.net.xml` plus authority/ID mapping; for brake physics, actual PhysicsControl config and tire/suspension/solver settings help distinguish near-stop solver response. No requirement to upload entire WOMD or 511NY full dataset.
