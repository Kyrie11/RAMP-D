# Phase 6C-A59/1a — server reproduction and CARLA evidence collection

Run in a fresh, independent checkout. Do not overwrite previous reports, source
or valid raw trace evidence. In particular, the ZIP contains no build outputs.

```bash
conda activate mfrp
mkdir -p /home/senzeyu2/code/RAMP-D_A59_1a
unzip -q RAMP-D_Phase6C_A59_1a.zip -d /home/senzeyu2/code/RAMP-D_A59_1a
cd /home/senzeyu2/code/RAMP-D_A59_1a
python scripts/verify_release.py
bash scripts/validate_phase6c_a59_1a.sh
```

Expected: previously server-accepted A59/0 replays, CTest 3, A59/1a pure
**19/19**, native **4/4**, all pytest **718/718**; zero skipped/failed. Result
`CONDITIONAL_A59_1A_SUBGATES_PASS` **only**; full physical/protocol SC and
real-world conformance flags remain false. Do not replace a failed step with
`|| true` or a manufactured PASS.

## 1. The already-running CARLA server (any map)

The CARLA command starts a map/server but need not spawn an actor. You can
perform a zero-mutation inventory first:

```bash
mkdir -p reports/a59_1a_carla
python scripts/a60_carla_actor_trials.py --mode inventory \
  --host 127.0.0.1 --port 2000 \
  --output reports/a59_1a_carla/inventory.json
```

Check `existing_dynamic_actors`, `actor_metadata` and `carla_server_version`.
If no vehicles, this is expected for a fresh, traffic-free CARLA map. To capture
**the running CARLA blueprint**, on a dedicated empty world only:

```bash
python scripts/a60_carla_actor_trials.py --mode capture \
  --host 127.0.0.1 --port 2000 --blueprint vehicle.tesla.model3 \
  --confirm-isolated-world \
  --output reports/a59_1a_carla/model3_actor_metadata.json
```

`capture` spawns the *owned* Model 3 actor, reads physics and bbox, then
destroys it. No control, tick or actual actuator calibration is performed.
An empty world is required for mutation; the script refuses if it sees other
vehicles/walkers/sensors. Actor metadata includes raw wheel geometry and
wheel torques, NOT guaranteed stopping deceleration.

## 2. 5/10/15 m/s repeated command-response experiments

**Only** on a dedicated CARLA 0.9.16 server (any map) with no other CARLA simulation
client ticking, no Traffic Manager, no connected SUMO bridge, no NPCs and no
active sensors; precondition must be verified by the operator. This program
acquires a best-effort local Linux lock, but cannot rule out an arbitrary
remote competing tick client. Do not run while an existing experiment is active.
It will temporarily set CARLA synchronous mode and fixed step 0.05s, then
restore the original settings on exit. It never calls `load_world()` or
controls an actor belonging to another client. The trigger speed controller
is a simple test harness; it is **not** an autonomous-driving planner.

```bash
python scripts/a60_carla_actor_trials.py --mode trials \
  --host 127.0.0.1 --port 2000 --blueprint vehicle.tesla.model3 \
  --confirm-isolated-world --confirm-exclusive-tick \
  --fixed-delta 0.05 --repeats 3 \
  --output reports/a59_1a_carla/model3_trials_raw.json
```

Expected 3 maneuvers (`brake`, `steer`, `combined`) × 3 speeds (5, 10, 15 m/s)
× 3 repeats = **27** separate actor runs. Every run records the exact CARLA
sim frame/time, preceding control, observed control, longitudinal/lateral
acceleration, angular velocity, body pose and speed. It samples raw front wheel
steer angle when supported. Each run resets by destroying *its own actor*;
there is no teleport-based fake dynamics reset. On the active map, the test lane must be straight,
non-junction, and the vehicle must remain on drivable road. Missing the target
speed, no eligible stretch, foreign ticks or leaving the lane gives REVIEW.

Audit logged evidence **after** the experiment:

```bash
python scripts/a60_review_carla_logs.py \
  --input reports/a59_1a_carla/model3_trials_raw.json \
  --output reports/a59_1a_carla/model3_review.json --repeats 3
```

Expected REVIEW unless all required raw signals/speeds/repetitions are present.
`SAMPLED_ACTOR_RESPONSE_LOGS_CAPTURED_UNCALIBRATED` means only sampled data
coverage, **never** certified actuator response, friction bounds, real vehicle
physical accuracy or disturbance inclusion. The reviewer rejects fake named
manoeuvres with no applied brake/steer command, missing samples or a skipped
CARLA frame.

Upload these three JSON files and the A59/1a acceptance directory ZIP. Include
any REVIEW traceback and do not delete unsuccessful runs. If CARLA spawning
fails, include the inventory report and complete error; do NOT restart the
CARLA server or modify a competing client's world to force a successful run.

## 3. Separate, pending simulator / dataset obligations

Previous A58 raw SUMO has 12 independently inspected trajectories but only
3 fully matching control summary files; the missing 9 need new clean work
and output directories. This A59/1a package retains `a59_0` forensic scripts
and runbook for that task. Do not mark SUMO logical opposite-direction edges
as physically one lane or `lower_friction_proxy` as a calibrated tire mu.

The next A59/1b mathematical step must close: continuous permission-change
splits, authority/version/priority resolution, general multi-resource
enter/stay/exit/conflicts, actual publicly observable messages/sensors,
independent task acceptance tail and an exact tiny-game oracle. Only then
should the A5/3c sync bridge and evidence-gated teacher factory be considered
for formal labels.
