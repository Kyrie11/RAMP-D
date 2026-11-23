# RAMP-D — Phase 6C-A59/1b-0J / CARLA controlled smoke and rational Post-handoff preflight

## 1. Last submitted evidence (2026-11-23)

`town06_start_site_audit(1).json`: 2,164 original straight candidates, 2,152 projected start-lane-identity usable, 11 projected junctions and 1 identity mismatch. Valid selected `(road_id,section_id,lane_id)=(48,0,-6)`.

`town06_readiness_a63(1).json`: CARLA 0.9.16 `Town06_Opt`, Tesla Model 3 actor, controlled 0.05 s ticks, 20 settling frames, immediate footprint and wheel-height proxy pass, actual controlled maneuvers **not attempted** (`trial_captured_count=0`). Review is `DESCRIPTIVE_PRETRIAL_EVIDENCE_COMPLETE_NOT_CERTIFIED`; vehicle friction, actuator lag, model error, physical collision safety remain unvalidated.

The preceding free-fall hypothesis is now supported as a contributing failure mechanism by the earlier negative vertical velocity and current settled proxy; no measured tire contact force is available. The road-ID projection error was independently demonstrated on Town06 candidate Road 48 Lane -7 and eliminated at the selected Lane -6.

## 2. Implemented in this release

- `scripts/a60_carla_actor_trials.py --mode smoke --smoke-speed 5 --smoke-maneuver brake` performs a single grounded, lane-checked target-speed controlled attempt. The previous `--mode trials` 27-trial defaults and `--mode readiness` are retained.
- `a64_carla_smoke_evidence.audit_single_control_smoke()` independently rejects incomplete control frames, the wrong actor, missing actual wheel-angle channels, ungrounded state, missing control excitation, time/frame discontinuity, lane failures and false speed due to vertical motion. Even a successful review has **no** model-error-bound, actuator-calibration or training-label authority.
- `a64_hybrid_handoff.audit_slab_handoffs()` verifies all declared world/time slabs, and that a subsequent outer initial state contains the preceding endpoint enclosure. Inputs use exact rational endpoints. This **does not validate** an arbitrary box's Picard derivation or correct Guard/resources/observations. It provides an anti-unsoundness necessary condition for the next native integration milestone.
- 12 new independent Python tests (including mutated bad logs/boxes). Existing suite retained.

## 3. What the next mathematically complete milestone must do (A59/1b-1)

For every hidden protocol world and every exact time slab, call validated MPFR/Picard integration using the correct right-continuous effectivity/ACK/agent/vehicle disturbance sets, preserving all prior endpoint outer sets. Read continuous swept geometry and resource entry/stay/exit authority in the same slab. Fail to UNKNOWN for missing Guard versions, unknown conflict edges, missing actors, event inside an unsegmented step or unsound input box. Merge *complete* observation-equivalent successors and replay every finite task-accepting policy tail with strictly decreasing completion rank. Independent negative tests must include missing ACK, rule effective at an internal boundary, resource capacity failure, hidden-world omission and late observation leakage. Only then consider SC certification.

## 4. CARLA measurement program (A5/3c, in parallel)

Run a **single** 5 m/s brake smoke first, then 5 m/s short steering and combined smoke, preserving separate files and steering-profile parameters. If those genuinely complete, run nine combinations at repeat=1, then repeat=3 for 27. Do not erase or override lane-exit failures; record friction, weather, OpenDRIVE hash, actor metadata, wheel steering, applied throttle/brake and time/frame provenance. Use separate calibration and held-out validation seeds/conditions. The CARLA `tire_friction` scalar must never be called a guaranteed physical coefficient of road friction. Calibration is valid for its *simulation parameter envelope* only unless real-vehicle conformance evidence exists.

## 5. Parallel mathematical and simulator acceptance, M1–M13

| Matrix | Immediate executable gate | Remaining hard closure |
|---|---|---|
| M1 Native validated tubes | Native CTest and exact rational slab endpoint checks | Full per-slab native certificate, correct disturbances |
| M2 Hybrid event clock | Rational event-time partition, full boundary completeness | Real ACK and receipt timeline with event ordering |
| M3 Ego actuator & geometry | Real grounded metadata + single response smoke | Multi-condition effective braking/steering/lag outer envelope |
| M4 Actor response | Waymax/IDM scenario inventory | Correlated joint response coverage and falsification |
| M5 Resource geometry | Per-slab continuous swept footprint necessary screening | Complete polygons, entry/stay/exit topology |
| M6 Guard authority | Multiworld guard snapshot obligations | Proven effective permission, capacity and conflict edges |
| M7 Control interlock | Controller memory and typed ACK check | Physically measured command/actuation acknowledgements |
| M8 Hidden protocol | Complete declared world slab cardinality | Exhaustive supported event/observation branches |
| M9 Public observation | Nonanticipative per-slab group check | CARLA visibility/sensor frames, receipt and masking |
| M10 SC progress | Endpoint handoff and conditional rank adapter | Task accepting, finite verified tails, rank descent |
| M11 Independent teacher | Refuse inference from candidate search failure | Exact finite policy class exhaustive negative proof |
| M12 Simulator conformance | CARLA grounded-actor and SUMO raw trace audits | Live SUMO traffic signal, shared geometry and co-simulation clock |
| M13 Eight supervised heads | Mask unknowns; preserve raw provenance | Source-by-source validated label factory and heldout checks |

Label policy: `event` ≠ reported onset, `joint` logged action ≠ counterfactual, `occupancy` requires geometry+time, `observation` requires public receipts/visibility, `viability/margin/deadline` require independent finite SC proof and reachability, and `causal` requires matched paired interventions. Unknown is not a negative label.

## 6. Server commands

On a **new** unpacked source tree with MPFR development headers:

```bash
conda activate mfrp
cd /home/senzeyu2/code/RAMP-D_A59_1b0J
cmake -S . -B build_a59_1b0j -DCMAKE_BUILD_TYPE=Release
cmake --build build_a59_1b0j -j 4
export A5_NATIVE_BUILD_DIR="$PWD/build_a59_1b0j"
export RAMPD_INTERVAL_LIB="$A5_NATIVE_BUILD_DIR/librampd_interval.so"
bash scripts/validate_phase6c_a59_1b0j.sh
```

Only on an **isolated CARLA** Town06 0.9.16 server with nobody else ticking:

```bash
mkdir -p reports/a64_carla
python scripts/a60_carla_actor_trials.py --mode smoke \
  --host 127.0.0.1 --port 2000 --blueprint vehicle.tesla.model3 \
  --confirm-isolated-world --confirm-exclusive-tick \
  --site-spacing 2 --site-prefer-longest --fixed-delta 0.05 \
  --smoke-speed 5 --smoke-maneuver brake \
  --output reports/a64_carla/town06_5ms_brake_raw.json
python scripts/a64_review_carla_smoke.py \
  --input reports/a64_carla/town06_5ms_brake_raw.json \
  --output reports/a64_carla/town06_5ms_brake_review.json
```

Successful independent smoke review requires `DESCRIPTIVE_SINGLE_CONTROL_SMOKE_CAPTURED_NOT_CALIBRATED`, never `CERTIFIED`. Review failure preserves raw information and must be fixed before a nine-combination run. If physical lane exit occurs, do not weaken lane constraints merely to obtain completion.

## 7. Information required next

One raw single-control smoke plus its independent review; a fresh full server regression folder; then short steer/combined smoke and repeated 5/10/15 m/s responses. For full SUMO/CARLA mapping: the actual co-simulation OpenDRIVE `.xodr` and SUMO `.net.xml`, vehicle identity and signals correspondence, and control timesteps. For 511NY/ROADWork: exact field dictionary and event provenance/geometry annotator specification, not another generic dataset URL.
