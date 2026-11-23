# CARLA A60 controlled-response experiments: site preflight and validity guidance

This change is an **optional geometry-site selection / read-only preflight** update.
It does **not** modify `drive_trial()`, `observe()`, vehicle metadata,
5/10/15 m/s speed grid, brake/steer/combined commands, 3 repeats, 0.05 s
fixed delta, or the strict 22 x 5 m / 5-degree / non-junction site gate.
No existing actor is driven, map reloaded, or other client's tick claimed.

## Why the initial Town10HD_Opt attempt failed

`REVIEW_NO_STRAIGHT_DRIVING_LANE_FOR_CONTROLLED_TRIAL` means none of the
sampled candidates passed this exact **110 m** centerline test:
1. Starting waypoint belongs to a driving lane and is not in a junction;
2. 22 successive `waypoint.next(5.0)` calls each return **exactly one** successor;
3. The successors remain driving/non-junction;
4. Each successor's yaw differs from the starting yaw by <= 5 degrees.

The prior 155 spawns + 1280 generated waypoints were exhausted on the active
map. This **does not prove** there are no qualifying sites anywhere, nor does
it establish that an eligible 110 m site is long enough for a 22 s maximum
acceleration phase plus a 2 s maneuver phase. It is not a vehicle failure.

## 1. Read-only, no isolation acknowledgment needed

```bash
python scripts/a60_carla_actor_trials.py \
  --mode site-audit --host 127.0.0.1 --port 2000 \
  --site-spacing 2.0 \
  --output reports/a59_1a_carla/town10_sites_2m.json
```

Site audit does not spawn actors, tick a frame, or change global settings.
To sample more densely (still NOT a complete mathematical enumeration):

```bash
python scripts/a60_carla_actor_trials.py \
  --mode site-audit --host 127.0.0.1 --port 2000 \
  --site-spacing 0.5 \
  --output reports/a59_1a_carla/town10_sites_half_meter.json
```

Inspect `site_audit.rejection_counts`, `best_verified_step_distance_m`,
`best_extended_straight_probe_m`, `verified_step_distance_counts_ge_m`,
`eligible_candidates_checked` and `top_candidate_waypoints`. Distances are
sampled steps only, not guaranteed collision-free rolling lengths.

**Decision:** If no qualifying 110 m sites appear, do not reduce the criteria
silently. Select a separate long-straight geometry calibration environment
(e.g. CARLA Town06 if installed), or publish an explicitly modified experiment
with a separately defined protocol and limitations. Town10HD_Opt remains a
useful *urban protocol/planning* evaluation map.

## 2. Experiment on a suitable map

On a truly **dedicated, empty CARLA server**, and after checking that Town06
is actually installed, deliberately load Town06 using your own CARLA
administration workflow. `a60_carla_actor_trials.py` never loads a map.
Switching maps destroys/recreates world actors and settings; never do that
in a shared simulation or another owner's run.

First audit that new map; only if eligible candidates exist, run a 1-repeat
smoke experiment:

```bash
python scripts/a60_carla_actor_trials.py \
  --mode trials --host 127.0.0.1 --port 2000 \
  --blueprint vehicle.tesla.model3 \
  --confirm-isolated-world --confirm-exclusive-tick \
  --site-spacing 2.0 --site-prefer-longest \
  --fixed-delta 0.05 --repeats 1 \
  --output reports/a59_1a_carla/model3_9_smoke.json
```

The opt-in `--site-prefer-longest` examines eligible sites and picks the
longest segment probed (up to 300 m, always under the same 5 degree / no
junction / unique successor conditions). It may spend more time on map
queries. It changes *only the spawn location*, **not** control histories.
The original first-eligible selection remains the default.

Review the 9-trial JSON first and ensure all individual trials say `CAPTURED`;
only then run the original 3-repeat, 27-trial grid, with new filenames:

```bash
python scripts/a60_carla_actor_trials.py \
  --mode trials --host 127.0.0.1 --port 2000 \
  --blueprint vehicle.tesla.model3 \
  --confirm-isolated-world --confirm-exclusive-tick \
  --site-spacing 2.0 --site-prefer-longest \
  --fixed-delta 0.05 --repeats 3 \
  --output reports/a59_1a_carla/model3_27_longsite.json

python scripts/a60_review_carla_logs.py \
  --input reports/a59_1a_carla/model3_27_longsite.json \
  --output reports/a59_1a_carla/model3_27_longsite_review.json \
  --repeats 3
```

`RAW_CARLA_TRIALS_CAPTURED_NOT_CERTIFIED` is a capture status. An individual
trial can still be `REVIEW_TARGET_NOT_REACHED` or `REVIEW_OFF_DRIVABLE_LANE`.
The independent reviewer is mandatory for assessing data completeness.

## 3. Recommended *future protocol upgrades* (not applied here)

1. **A verified distance budget:** Acceleration until trigger (up to 22 s) and
   2 s of active control must both fit; require clearance based on measured
   actual rolling distance, pre-trigger road membership and junction proximity.
   Exactly 110 m of waypoint clearance alone is insufficient.
2. **Phase validity:** Check road, collisions and frame-contiguity in both the
   approach and post-trigger phases. The current code only checks that the
   actor is on a driving lane / outside a junction in the 2 s response phase.
3. **Calibration semantics:** `steer` changes throttle to 0.17 after target
   speed; it is not constant-speed steering. Separate longitudinal and lateral
   model identification is needed before fitting deceleration, response lag,
   steer saturation, and friction-circle parameters.
4. **Reproducibility:** Capture surface friction, map/weather/physics and actor
   configuration; add held-out seeds, repeats, confidence procedures, and
   disturbance assumptions. Three repeats cannot provide rigorous worst-case
   physical bounds. Separate raw observations from certified guarantees.
5. **Urban validation:** Town10HD_Opt can be used later for actual rule,
   traffic-light, visibility, and decision-continuation tests; do not conflate
   those with isolated vehicle dynamics identification.

**Integrity:** The historical `MANIFEST.sha256` is not silently rewritten.
`verify_release.py` for this modified checkout can detect a changed script.
This update was tested with offline fake CARLA map objects, *not* the user's
live CARLA server or CARLA binaries.
