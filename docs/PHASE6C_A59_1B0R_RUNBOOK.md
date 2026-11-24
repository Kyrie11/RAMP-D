# A72 / Phase6C-A59/1b-0R 服务器运行手册（严格源/证书域隔离）

## 0. 全新部署、编译和门槛（不能拿旧 CMakeCache 冒充新 build）

```bash
conda activate mfrp
mkdir -p /home/senzeyu2/code/RAMP-D_A59_1b0R
unzip -q RAMP-D_Phase6C_A59_1b0R.zip -d /home/senzeyu2/code/RAMP-D_A59_1b0R
cd /home/senzeyu2/code/RAMP-D_A59_1b0R
python scripts/verify_release.py
cmake -S . -B build_a72 -DCMAKE_BUILD_TYPE=Release
cmake --build build_a72 -j 4
export A5_NATIVE_BUILD_DIR="$PWD/build_a72"
export RAMPD_INTERVAL_LIB="$PWD/build_a72/librampd_interval.so"
bash scripts/validate_phase6c_a59_1b0r.sh
```

Expected: previous A71 complete mathematical/native gate + new A72 23+ targeted tests, far `CONDITIONAL_DECLARED_POLYGON_EXCLUSION`, near `UNKNOWN` and nonzero exit 4, all eight formal labels masked. **Do not** conflate a toy/native mathematical PASS with a full SC `CERTIFIED`.

## 1. 已完成 SUMO 12-run 结果的独立重放（不重跑也能验原始 source）

```bash
python scripts/a72_review_parallel.py \
  --sumo-campaign /home/senzeyu2/code/a71_sumo_campaign_20261124 \
  --output reports/a72_sumo_12_replay.json
```

Use the actual root containing `sumo_baseline_17.json`, `sumo_dense_23.json`, etc. Do not use a parent directory or an old A58 folder. Expect 12 runs × 9000 ticks, no contradictory logical occupancy, per-run TraCI command/readback truth and departures=arrivals. `setRedYellowGreenState`/getter are simulator state, **not** physically observed signal/barrier ACK. This is a logical two-directed-edge corridor, **not** metric one-lane sharing. Real shared-resource next target: authoritative OpenDRIVE/SUMO net pair, unique CARLA tick owner, car-ID registry, physical resource polygons, time-offset/tick alignment, end-to-end signal/actor state, fail closed on disagreement. Do not alter the already-completed A71 source logs.

## 2. Waymax: 30/60/120 existing synthetic lookahead + NEW real-scenario inventory

```bash
python scripts/a72_review_parallel.py \
  --waymax-arm 30:reports/a71_waymax_idm_pair_30.json \
  --waymax-arm 60:reports/a71_waymax_idm_pair_60.json \
  --waymax-arm 120:reports/a71_waymax_idm_pair_120.json \
  --output reports/a72_waymax_lookahead_review.json

python scripts/a72_probe_real_waymax_scenes.py \
  --tf-example-file /data0/senzeyu2/dataset/waymo_open_dataset_motion_v_1_3_1/uncompressed/tf_example/validation/validation_tfexample.tfrecord-00149-of-00150 \
  --max-scenarios 5 \
  --output reports/a72_waymax_real_scenes_5.json
```

The existing `probe_waymax_response.py` uses WOMD to initialize state templates but overwrites both synthetic ego/follower paths before official IDM. Do **not** call those 30/60/120 files *real logged follower reactions*. New real inventory reads actual log trajectories without overwrite, but does not provide counterfactual rollouts. This validation shard is an appropriate first runtime smoke; **do not iterate all 150 validation shards or 1000 training shards until a real-scenario schema/provenance/metric evaluation passes**. For full map semantics and source scenario identities prefer bounded original WOMD Scenario protobuf. Use training only for fitting, validation for heldout evaluation; no same physical scene across splits.

## 3. 511NY: recover 1521 clean auxiliary rows and quarantine the one unknown Event Type

```bash
python scripts/a71_normalize_511ny_csv.py \
  --csv /data0/senzeyu2/dataset/TrafficIncidents/511NY/511_NY_Events.csv \
  --max-rows 10000 \
  --output reports/a72_511ny_normalized.jsonl
python scripts/a72_export_auxiliary_v2.py \
  --normalized-511ny reports/a72_511ny_normalized.jsonl \
  --output reports/a72_511ny_auxiliary.jsonl \
  --quarantine reports/a72_511ny_quarantine.jsonl
```

Expected for the user-supplied previous normalized file: 1522 lines, 1521 valid, exactly one missing Event Type quarantined. These rows may train a *reported incident category* auxiliary head; they contain no rule-effectivity, worker clearance or ego message receipt truth. The ID `SOURCE_ROW_...` is a row identifier, not a unique incident. Do not overwrite prior outputs; use a new directory for a retry.

## 4. ROADWork: official annotations.zip, images.zip, gtFine, not roadwork_files.json

```bash
python scripts/a72_roadwork_real_pipeline.py \
  --dataset-root /data0/senzeyu2/dataset/ROADWork \
  --max-templates 100 \
  --output-dir reports/a72_roadwork_real_100
```

Required: `/data0/.../ROADWork/annotations.zip` and `images.zip`/extracted `images`, `gtFine` from sem_seg_labels.zip. The file `roadwork_files.json` is an inventory, not GPS-grouped JSONL. New pipeline calls existing `audit_roadwork.py` image/mask alignment, `audit_a57_roadwork.py` original GPS/video family split, `export_a58_roadwork_templates.py`, then the A72 auxiliary exporter. If official annotations are missing, it FAILS immediately rather than emitting a misleading empty dataset. Exported labels are **image classes, sign attributes and visual-only travel alteration**, not metre-scale closure polygons, legal authoritativeness or hidden event clocks. Upload `pipeline_review.json`, `gps_split.json`, `alignment.json` plus a bounded example of JSONL, not all image files.

## 5. CARLA: controlled factorial 2x3 with replicates and solver phases

Existing: at 5 m/s, pure/combined 0.15 and 0.30 each have one run; combined 0.45 has at least one run. Begin with missing **pure 0.45** using the *same independently isolated Town06_Opt* map and mass/vehicle/weather/step settings:

```bash
python scripts/a60_carla_actor_trials.py \
  --mode smoke --host 127.0.0.1 --port 2000 \
  --blueprint vehicle.tesla.model3 \
  --confirm-isolated-world --confirm-exclusive-tick \
  --site-spacing 2.0 --site-prefer-longest --fixed-delta 0.05 \
  --smoke-speed 5 --smoke-maneuver brake \
  --brake-only-fraction 0.45 \
  --output reports/a72_carla/pure_b045_run01.json
```

Keep 0.15/0.30/0.45 × steer=0/.03 in distinct cell directories, then 3 independent runs per cell, no overwritten raw JSON. For coupled cells retain `--steer-fraction 0.03 --steer-pulse-s 0.15 --combined-brake-fraction X`; for pure cells use `--brake-only-fraction X` and check **actual applied steer=0 and throttle=0**. New A72 factorial audit uses strict post-trigger controller readbacks and checks distinct raw hashes, target speed and all actor metadata. Analyze nonzero speed, near-stop (<1 m/s), zero-speed solver separately. After replication, vary fixed_delta 0.05 vs 0.025 as a **different experiment** to probe contact solver artifacts, then vary friction and speed **one factor at a time**. None yields real-world guaranteed b without additional independent envelope assumptions.

For audit outputs, use the existing `scripts/a64_review_carla_smoke.py`, `scripts/a65_review_carla_physics.py` (if present in this checkout), and `scripts/a71_compare_carla_brake.py`; keep the raw captures immutable.

## 6. Required next upload

- A72 whole server validation directory (including CTest/JUnit, freshly rebuilt native backend and Native two-world far/near JSON).
- `a72_waymax_real_scenes_5.json` and 30/60/120 summary. If available, 1–3 actual WOMD Scenario protos or bounded scenario-index reports with source IDs.
- ROADWork real `pipeline_review.json`, alignment/gps reports and 5–10 image-group templates (official annotations.zip only if local pipeline fails and you can share it).
- SUMO 12-run A72 review (new runs unnecessary) and physical shared-lane/co-sim map files for future gate.
- Missing CARLA pure 0.45, then 2×3 × 3 replicate matrix, sensor/actuation metadata including physics substepping.

Recommended domain/theory inputs later: roadway *authoritative rule and controller ACK* specification, real map resource geometry, ego CARLA PhysicsControl full YAML/config (especially actual brake model/engine), independent bounded agent-response assumptions, accepted mission-tail formal contract. The two ROADWork papers and 511NY dictionary already suffice for current auxiliary semantics; no new generic review paper needed.
