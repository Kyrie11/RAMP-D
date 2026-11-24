# RAMP-D Phase6C A59/1b-0P reproducibility and next experiments

## 1) Fresh native build and four-shard acceptance

```bash
conda activate mfrp
mkdir -p /home/senzeyu2/code/RAMP-D_A59_1b0P
unzip -q RAMP-D_Phase6C_A59_1b0P.zip -d /home/senzeyu2/code/RAMP-D_A59_1b0P
cd /home/senzeyu2/code/RAMP-D_A59_1b0P
cmake -S . -B build_a59_1b0p -DCMAKE_BUILD_TYPE=Release
cmake --build build_a59_1b0p -j 4
export A5_NATIVE_BUILD_DIR="$PWD/build_a59_1b0p"
export RAMPD_INTERVAL_LIB="$A5_NATIVE_BUILD_DIR/librampd_interval.so"
python scripts/verify_release.py
bash scripts/validate_phase6c_a59_1b0p.sh
```

Expected: new A70 regression >=31/31; 4-file-shard complete repository >=940/940 with all zero skipped/error/failure; native CTest 3/3; four actual 6D MPFR/Picard conditional microcase certificates; true uploaded three-arm CARLA differential evidence. Never reuse historical CMakeCache across directories. Keep all JUnit, logs and certificates.

## 2) Independent local 6D Native split proof check

```bash
python scripts/a70_replay_native_microcase.py \
 --output-dir reports/a70_native_two_worlds_01
```

This does **not** prove traffic resource permission, all hidden worlds or terminal acceptance. It should produce four Native MPFR certificates and a manifest with `full_sc=false`. A missing library or failed Picard certificate MUST fail.

## 3) Reaudit REAL uploaded 0.15 / 0.30 / 0.45 combined controls

```bash
python scripts/a70_review_brake_timecourses.py \
 --arm b15=/path/to/combined_b0.15.json \
 --arm b30=/path/to/combined_b0.30.json \
 --arm b45=/path/to/combined_b0.45.json \
 --output reports/a70_brake_timecourse_raw_upload.json
```

Expected `DESCRIPTIVE_TIMECOURSES_RECOMPUTED_MODEL_UNRESOLVED`, different speed-regime peak reasons, formal labels disabled. Do not use maximum deceleration as real-vehicle guaranteed braking or a zero uncertainty bound.

## 4) Next minimum discriminating CARLA experiments: brake-only controls

Keep isolated Town06 0.9.16 (no other tick owners), fixed 0.05 s, same map/site, weather, model physics, 5 m/s trigger and start state. First collect **one** 0.15 brake-only smoke before expanding. This is not the old 0.70 default.

```bash
mkdir -p reports/a70_carla
python scripts/a60_carla_actor_trials.py \
 --mode smoke --host 127.0.0.1 --port 2000 \
 --blueprint vehicle.tesla.model3 \
 --confirm-isolated-world --confirm-exclusive-tick \
 --site-spacing 2.0 --site-prefer-longest \
 --fixed-delta 0.05 --smoke-speed 5 \
 --smoke-maneuver brake --brake-only-fraction 0.15 \
 --output reports/a70_carla/brakeonly_b015_01.json
python scripts/a64_review_carla_smoke.py \
 --input reports/a70_carla/brakeonly_b015_01.json \
 --output reports/a70_carla/brakeonly_b015_01_review.json
```

If it captures valid physical commands, run 0.30 and 0.45 brake-only in separate unique paths; then add 2 independent runs per cell. The six conditions (brake 0.15/0.30/0.45 × steering none/0.03) require their own 3 repeats, not pooled; see original 3 existing combined arms. Keep both successful and REVIEW traces. **Do not run on active traffic clients or real roads.**

Only after the 5 m/s factorial is intelligible, change one dimension at a time: speed 10 then 15 m/s, separately tire friction configuration, separately actuator/observation latency, with explicit physics provenance and matched control timing. Capture wheel angular speed/contact, collision sensor, physics settings, and optionally synchronized top-down video to diagnose >20m/s² simulated deceleration. Do not interpret video as formal swept geometry.

## 5) In parallel without waiting for CARLA

1. On the math server, extend A70 full 6D Native segmented transport to **general polygon resources** with entry/stay/exit, full agent sweeps and effective authority/ACK semantics, then independent observation+SC terminal tail replay. Model-relative positive/negative small examples must include all seven named failure cases. No `CERTIFIED` without all conjuncts.
2. On SUMO, rerun **9 lost control-summary jobs in distinct fresh directories**, provide 12/12 control summaries, raw trajectories, signal commands, actual phase and clearance logs. The previous alternating-edge simulation is a logical resource test, not proof of an actual one-lane geometry.
3. On CARLA/SUMO, use matched OpenDRIVE and SUMO net, one master tick, stable actor identity, consistent coordinate transform, and explicitly sourced signal ACK. Produce separate acceptance files for each obligation. Do not assume Town06 calibration map is joint-co-sim-ready.
4. Waymax: test nominal jerk→acceler/curvature conversion and discrete model error against Waymax episodes, identify response domain/support, never treat factual logs as all counterfactual reactions.
5. 511NY/ROADWork: preserve `report_time != effective_time != receipt_time`, image bbox vs metric closure geometry. Source-lineage and spatial uncertainty audit precedes any event or observation training label.

## 6) Upload next time

- Full report directory `reports/a70_*`: targeted/full_0..3 native JUnit, native_microcase manifest+certificates, machine acceptance.
- 3× (brake-only) ×3 speed-5 replicates if available, and existing combined three levels, including source actor/physics/clock/logs.
- SUMO nine fresh rerun control summaries, raw traces, phase/ACK/roster logs, and map net geometry.
- If available Waymax probe data and joint OpenDRIVE/net mappings; sensor receipt/visibility and traffic source timestamps.

No current artifacts justify certified safety labels or all M1–M13 closed.
