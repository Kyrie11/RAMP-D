# A59/1b-0N server reproduction and next diagnostics

## 1. Fresh checkout and new Native build

```bash
conda activate mfrp
mkdir -p /home/senzeyu2/code/RAMP-D_A59_1b0N
unzip -q RAMP-D_Phase6C_A59_1b0N.zip -d /home/senzeyu2/code/RAMP-D_A59_1b0N
cd /home/senzeyu2/code/RAMP-D_A59_1b0N
cmake -S . -B build_a59_1b0n -DCMAKE_BUILD_TYPE=Release
cmake --build build_a59_1b0n -j 4
export A5_NATIVE_BUILD_DIR="$PWD/build_a59_1b0n"
export RAMPD_INTERVAL_LIB="$A5_NATIVE_BUILD_DIR/librampd_interval.so"
python scripts/verify_release.py
bash scripts/validate_phase6c_a59_1b0n.sh
```

Expected: >=875 pytest, >=42 A68, 3 CTest, zero failures/errors/skips. The A68 fixture comparison is diagnostic and DOES NOT exercise CARLA or SUMO in this gate. Preserve the complete report directory and source release hash.

## 2. Replay your three real repeat logs independently

```bash
python scripts/a68_review_parallel_tracks.py \
  --run 1=/path/to/combined_repeat1.json \
  --run 2=/path/to/combined_repeat2.json \
  --run 3=/path/to/combined_repeat3.json \
  --output reports/a68_uploaded_three_track_review.json
```

Never overwrite existing reports; choose a new output path. Model-mismatch warnings remain REVIEW even when protocol is consistent.

## 3. Next CARLA diagnostic: separate 5m/s brake fractions

Only on an isolated Town06 server with **one** synchronized tick client and no other active actor/Traffic Manager. These confirmation flags are user assertions; the script is not an independent operating-system owner registry. Do NOT run this loop when another simulation is active. Exit on first failure, preserve raw JSON.

```bash
mkdir -p reports/a68_carla_brake_sweep
for brake in 0.15 0.30 0.45; do
  python scripts/a60_carla_actor_trials.py --mode smoke \
    --host 127.0.0.1 --port 2000 --blueprint vehicle.tesla.model3 \
    --confirm-isolated-world --confirm-exclusive-tick \
    --site-spacing 2.0 --site-prefer-longest --fixed-delta 0.05 \
    --smoke-speed 5 --smoke-maneuver combined \
    --steer-fraction 0.03 --steer-pulse-s 0.15 \
    --combined-brake-fraction "$brake" \
    --output "reports/a68_carla_brake_sweep/brake_${brake}.json" || break
done
```

This version fixes a prior A64/A67 hardcoded `brake>=0.20` excitation threshold; grades down to 0.05 must be checked against each trial's actual declared intervention. Old A67 raw files missing the fraction are accepted only as *descriptive legacy evidence* if all post-trigger brake commands are constant, with explicit provenance.

Each fraction is its own protocol; the strict A68 *repeat* auditor is specifically for 0.45 and **must not pool these three files**. Use the existing A64/A66/A67 single-run reviewer for each, inspect actual command and wheel angles, and upload the raw JSON, errors and review outputs. If stage fails, do not force `CAPTURED`. A camera/video is only needed when telemetry conflicts with the scene geometry; footage is not a continuous-time safety proof.

## 4. Independent parallel projects

Waymax numeric check (requires your Waymax/JAX environment):
```bash
python scripts/probe_waymax_dynamics.py --output reports/a68_waymax_discrete_parity.json
```

SUMO: follow `docs/PHASE6C_A59_0_RUNBOOK.md` to regenerate all 12 controller summary reports in *fresh directories*, especially nine previously missing original summaries. Confirm actual lane topology, physical footprints, timing/ACK; do not reuse the old broken work dirs.

Traffic/Guard: feed exact signal controller commands, acknowledgments, resource occupancy and public receipts into A61/A62/A66 and A68; symbolic `CONDITIONAL` results are not physical ACK. CARLA/SUMO: choose a separately verified common map, capture SUMO .net and CARLA OpenDRIVE + transformation, unique frame/actor ownership and observed signal state. 511NY/ROADWork: upload timestamp semantics, geographic coverage and any manually verified polygon if available; do not infer physical onset from reports.

## 5. Evidence needed for next round

Upload the `validate_phase6c_a59_1b0n.sh` report directory and new A68 three-track review, separate CARLA 0.15/0.30/0.45 raw files and their single-run reviews; SUMO 12 controller reports plus net/route configs; Waymax probe output; if available live signal ACK/clock maps and CARLA/SUMO map registration. No formal `L_viability`/`L_margin`/`L_deadline`/`L_causal` can be inferred from these alone.
