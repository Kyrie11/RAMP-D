# Phase 6C-A59/1a — engineering implementation, error analysis and acceptance

**Date:** 2026-11-22. **Basis:** User-supplied revised `AnonymousSubmission2027(1).tex`,
full A59/0 source archive, target-server build archive and
`phase6c_a59_0_20261122T092616Z.zip`.

## I. Actual previous server result

Uploaded A59/0 acceptance JSON proves `CONDITIONAL_A59_BOUNDARY_TESTS_PASS`:
695/695 full pytest, 11/11 A59 pure, 5/5 A59 native and 3/3 CTest.
The release-integrity log verified 330 files. This is a model-relative
*conditional* gate. The new A59/0 ZIP contained **no new CARLA actor JSON or
response logs**. The older A58 actor probe said `REVIEW_NO_VEHICLE_ACTOR`
with `vehicle_count=0`. Neither uploaded A59/0 report nor build archive
proves that an actor exists *right now* on the user's running Town04 server.
The posted `CarlaUE4.sh ... -RenderOffScreen -carla-rpc-port=2000` launches
CARLA and loads Town04, but does not itself spawn Tesla actors.

## II. Paper constraints not relaxed

`B=(ego,agents,hidden rule/controller,message histories,task progress)` is
joint support, not independently sampled marginals. An action is valid only
when `SafeTube(B,u)` is proved for all declared disturbances/actors and every
posterior that shares the same *public* observation is included in a
strictly lower-ranked task-winning support. Goal-accepting finite tail,
nonanticipation and finite completion rank must be independently replayed.
Rule-conditioned resources carry entry `alpha`, occupancy/clearance `beta`,
direction set, integer capacity and conflict geometry. Exogenous event onset,
legal effectivity, message issuance, delivery/receipt and public observation
may occur at different times. SUMO/CARLA commands are not physical ACKs.

The current first-party source remains *explicitly* conditional, not a
claim of complete mathematical safety or physical model calibration.

## III. Corrected or newly exposed engineering issues

1. **No CARLA actor evidence:** A58 captured zero actors; A59 only reran
   native/pytest. New isolated vehicle spawn/probe is needed. **No previous
   measured 5/10/15 m/s brake, steering or combined command-response data.**
2. **Native rule switch inside a step:** the A57/A58 Post assumes an old
   phase and changes the controller at the tick boundary. A rational clock
   ledger listing an internal effectivity time is insufficient: the motion,
   resource rule and controller must actually be segmented. New integration
   explicitly rejects the unsplit case.
3. **Crossing and reentry ambiguity:** passing a stop/reserve Guard does not
   prove per-actor full-body entry/stay/exit; an initially incumbent vehicle
   can leave and reenter after `alpha=false`. A59/1a audits each provided
   continuous slab with conservative MAY-contact and carries the unknown.
   A58 independently checks full-time ego collision/limits; it continues to
   reject resource contact pending complete dynamic legality integration.
4. **Source times versus physical times:** an externally logged incident
   timestamp is not the onset time; a same-tick issue/receipt needs a causal
   order and a split if used as a protocol transition. Across ticks, a
   receipt may refer to a documented *prior* issue, not an invented one.
5. **Proof scope:** `ResourceSlice` is only trusted in the new native entry
   path when rebuilt from Picard-replayed tubes plus declared actor envelopes.
   Caller-supplied slices are useful for math falsification, but cannot be
   promoted to real full-support physical proof.
6. **CARLA command is not physical actuation:** `max_brake_torque`, normalized
   `VehicleControl.brake` and `tire_friction` are raw configuration/control,
   not guaranteed deceleration, wheel slip, steering rate or model uncertainty.
   `get_control()` returns a control state, not a measured tire-force vector.
   Body pose/velocity/yaw response and separate wheel angles are sampled.
7. **SUMO evidence gap unchanged:** previous A58 audit replayed 12 logical
   traces, but 9 summaries were clobbered by a reused work directory. The
   user uploaded no new clean SUMO control summaries in the A59/0 package.
   These 9 therefore remain REVIEW, not converted to PASS here.
8. **Traffic authority and physical deployment pending:** rule precedence
   conditioned on jurisdiction/scope/version, queue-detector integrity,
   full clearance-interval occupancy, barrier deployment/ack, and
   independent actor/obstacle geometry are not certified by this substage.

## IV. Concrete edits and interfaces

- `python/rampd_core/a60_clock_resource.py`:
  `ClockEvent`, `audit_clock_events` with exact `Fraction` and previous tick
  history; `ResourcePermission`, `ResourceActor`, `ResourceSlice`,
  `audit_resource_transition`, replay-tube-backed
  `audit_native_resource_tubes`, and
  `native_sc_predecessor_a59_1`. The gate is a three-way conjunction of
  native rank screen, resource slab audit and exact model-clock audit;
  output at most `CONDITIONAL_A59_1_SUBGATE_CANDIDATE`.
- `python/rampd_core/a60_carla_evidence.py`:
  strict schema, 5/10/15 m/s × brake/steer/combined × repeats,
  finite signals, per-frame times, commanded maneuvers, isolated actor
  metadata and provenance; only
  `SAMPLED_ACTOR_RESPONSE_LOGS_CAPTURED_UNCALIBRATED` or `REVIEW`.
- `scripts/a60_carla_actor_trials.py`:
  default read-only inventory; separate opt-in isolated spawn metadata
  capture and synchronous 27-run actor trials. Never loads Town04 or controls
  another person's actor; restores old world settings if it changes them.
  An external remote tick client is not detectable, so the operator must
  ensure exclusivity. Runs are rejected when foreign ticks are detected.
- `scripts/a60_review_carla_logs.py`: independent strict quality review.
- `tests/test_phase6c_a59_1_pure.py`,
  `tests/test_phase6c_a59_1_native.py`:
  deliberate false-acceptance and tampered evidence tests.
- `scripts/validate_phase6c_a59_1a.sh`, this report, runbook,
  versioned PROGRESS and SHA-256 release manifest.

## V. Tests and failures

**Locally executed using the user's provided Linux
`build_phase6c_a59_0/librampd_interval.so`** (MPFR/GMP runtime available):

- Baseline full repository plus A59/1a: **718/718 Python pytest PASS**.
- A59/1a new pure: **19/19 PASS**.
- A59/1a native integrated Picard resource/clock SC: **4/4 PASS**.
- Extracted target-server `test_interval`, `test_picard`, `test_abi`
  executables: **3/3 PASS** after setting
  `LD_LIBRARY_PATH` to the uploaded native build directory.
- `python -m py_compile` on new modules/scripts: PASS.
- Live CARLA spawn/trial: **NOT RUN** in this sandbox; `carla` Python module
  and a live CARLA RPC server are not available here.
- New live SUMO, Waymax and CARLA/SUMO co-simulation: **NOT RUN** here.

**Actual development falsifications:**

- A test initially expected an exit-closed violation when a 2m footprint
  centered at x=10 overlaps resource [10,15] throughout the complete
  static slab. This expectation was incorrect: no exit is possible for that
  fixed pose. The test was corrected to a boundary-touching uncertain
  pose at x=9, correctly yielding UNKNOWN without changing the physical
  monitor to force a test PASS.
- Restored binary test executables initially failed to locate
  `librampd_interval.so` (`exit 127`) because the uploaded build directory
  was moved to a new container path. Setting `LD_LIBRARY_PATH` repaired the
  dynamic library search; the 3 tests then passed unmodified.
- A forged trial whose name said `brake` but whose applied command remained
  zero exposed a missing command-evidence check. This check was added; the
  negative test now remains REVIEW rather than passing on schema alone.

## VI. Long-term M1–M13 assurance matrix

| Gate | Current status | Next independent closure |
|---|---|---|
| M1 outward MPFR/Picard | Historical server accepted; local 3/3 native + Picard integrated | uncertainty/support calibration, independent numerical platform |
| M2 clock / causal order | A59/1a exact *model* ledger and internal-switch rejection | segmented hybrid dynamics; actual issue/receipt/time registration |
| M3 ego dynamics | kinematic jerk/steer-rate, nominal bounds; metadata/trial acquisition tool | actor-derived geometry, actuator identification, holdout residual outer bounds |
| M4 other drivers | declared actor differential envelopes; Waymax diagnosis | model coverage and interactions, curve leader and falsification |
| M5 continuous geometry/topology | conditional rectangular per-slab occupancy audit added | complete lane connectors/polygons/conflict pairs, dynamic entry/stay/exit |
| M6 rule permissions/capacity | alpha,beta,direction/capacity conservative audit added | resolved authority versions, exit conditions, multi-resource capacity |
| M7 control/Guard/interlock | declared finite Guard and barrier ACK contracts exist | physical detector coverage, real barrier spawn/settled ACK, shared lane |
| M8 hidden protocol | declared branch finite, nonanticipative SC screen | full rule/delivery/observation support enumeration |
| M9 public sensing | no live camera/LiDAR/occlusion evidence | sensor frame/clock/visibility and delivery-latency trials |
| M10 SC/tail | Native Post → rank conditional A59/1a subgate | independently verified goal-accepting tail + oracle + all posterior branches |
| M11 teacher | no complete independent teacher | CEGAR/full-support replayer, impossibility within finite policy class |
| M12 simulator conformance | 12 raw A58 logical SUMO traces; 3 matching summaries | nine missing SUMO controls; CARLA trials; physical co-sim / calibration |
| M13 8 supervision sources | schemas/plans but zero fully certified all-head labels | loss-wise masks, separate factual vs synthetic/intervened truth, heldout |

Gate is **CONDITIONAL** within declared finite models, not a measured safety
certificate. There is no justifiable single percentage of total project
completion because a complete protocol/task/physics guarantee is conjunctive.

## VII. Eight supervised targets — safe provenance constraints

| Loss | Current source and rule |
|---|---|
| `L_event` | SUMO/CARLA controller and event issue/receipt when observed; 511NY incident report = auxiliary prior, not physical effective/onset timestamp |
| `L_joint` | AV2/WOMD factual trajectories; Waymax/SUMO response simulations require falsification/holdout; logged trajectories are not counterfactual labels |
| `L_occupancy` | metric resources+actor bbox/tubes only after calibration; ROADWork image boxes are not meter-level occupancy |
| `L_observation` | CARLA sensors/occlusion/public observation with actual delayed ingress, not hidden event state |
| `L_viability` | complete finite goal-winning policy certificate for positives, proof over specified complete finite class for negatives; unresolved must be masked |
| `L_margin` | verified *lower* tube and terminal policy margins only, not predicted optimal V_H |
| `L_deadline` | same-prefix exact physical commitment and posterior distinction deadlines, never incident-report duration |
| `L_causal` | fixed exogenous event, controlled A/A and A/B intervention with reactive agents and comparable seeds; simulator counterfactual only |

## VIII. Formal next stage / requested uploads

A59/1b: implement event-segmented controlled hybrid Post; jurisdiction and
rule-version precedence; multiresource conflict entry, stay and exit;
complete public observation branch enumeration and independently replayer
terminal accepting strategy with exact tiny-oracle counterexamples. After
this, A5/3c-1: one-owner CARLA/SUMO tick and actor registry, coordinate
registration and actual physical shared corridor. Then A5/3c-2: empirical
vehicle conformance bounds, multi-speed friction/steer/brake/delay, and only
then the evidence-gated eight-label factory + training.

Most useful next uploads: `inventory.json`, actor metadata JSON, 27-trial
raw/review JSONs and the new A59/1a acceptance archive; separately rerun
nine SUMO missing control reports with fresh work/report paths. Optional
follow-up materials: CARLA custom blueprint/physics assets if Tesla model3
was modified; verified wheel coordinate conventions and tire/surface config;
real controller logs with command-vs-ack and actual issue/receipt stamps;
ROADWork camera calibration and map/georeferencing information if metric
occupancy labels are intended. No extra 1TB dataset is needed for this gate.
