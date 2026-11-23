# A59/1b-0L: exact server commands, fresh isolated worktree

1. Unzip the release ZIP into **a new empty directory**. In conda `mfrp`, run `python scripts/verify_release.py`. Configure fresh CMake build: `cmake -S . -B build_a59_1b0l -DCMAKE_BUILD_TYPE=Release && cmake --build build_a59_1b0l -j 4`. Export `A5_NATIVE_BUILD_DIR="$PWD/build_a59_1b0l"` and `RAMPD_INTERVAL_LIB="$A5_NATIVE_BUILD_DIR/librampd_interval.so"`. Run `bash scripts/validate_phase6c_a59_1b0l.sh` (full 815 or more Python, 3 CTest expected). Preserve complete report dir. Do not re-use a transplanted CMakeCache.
2. Re-audit uploaded single steer file (reference shown only; supply its **real** path): `python scripts/a66_review_carla_lateral.py --input /path/town06_steer_raw.json --output reports/a66_steer_independent.json`. This is a **descriptive**, not safety-certified acceptance.
3. Report missing/available controls: `python scripts/a66_inventory_carla_controls.py --brake /path/town06_5ms_brake_raw.json --steer /path/town06_steer_raw.json --output reports/a66_control_inventory.json`. Do not pass a combined flag before an actual combined file exists.
4. Only with CARLA 0.9.16 Town06 on port 2000 and **no other client advancing time**: run the one-case combined trial. The script temporarily sets synchronous timing and restores world settings; it creates and destroys only its owned actor.

```bash
mkdir -p reports/a66_carla
python scripts/a60_carla_actor_trials.py \
  --mode smoke --host 127.0.0.1 --port 2000 \
  --blueprint vehicle.tesla.model3 \
  --confirm-isolated-world --confirm-exclusive-tick \
  --site-spacing 2.0 --site-prefer-longest --fixed-delta 0.05 \
  --smoke-speed 5 --smoke-maneuver combined \
  --steer-fraction 0.03 --steer-pulse-s 0.15 \
  --output reports/a66_carla/town06_5ms_combined_raw.json
python scripts/a64_review_carla_smoke.py \
  --input reports/a66_carla/town06_5ms_combined_raw.json \
  --output reports/a66_carla/town06_5ms_combined_a64.json
python scripts/a66_review_carla_lateral.py \
  --input reports/a66_carla/town06_5ms_combined_raw.json \
  --output reports/a66_carla/town06_5ms_combined_a66.json
python scripts/a65_plot_carla_lane.py \
  --input reports/a66_carla/town06_5ms_combined_raw.json \
  --output reports/a66_carla/town06_5ms_combined_lane.png
```

5. Upload the combined raw JSON + A64/A66 results + plot and complete server test report. If trial REVIEW, save the raw failure, and **do not overwrite** or silently adapt steering intensity. Keep brake 5 m/s diagnostic separate. If a simulator crash occurs, also upload CARLA terminal/log metadata; optional synchronized bird's-eye camera video helps diagnose, but is not a required or sufficient safety witness.
6. Parallel to this CARLA evidence, do not wait to execute SUMO fresh-dir audit and work on exact clock protocol, Guard resource topology and Waymax control adaptation. They require their own independent acceptance records.
