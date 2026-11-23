# Phase 6C-A59/1b-0L: CARLA lateral witness + hybrid/co-sim identity contracts

## Evidence status (2026-11-23)

* Input: `town06_steer_raw(1).json` SHA256 `4c8593905121a677df58ea8ecbc71ba2071493a9b5a061790c6c913ab9cbf6c3`; fixture in `tests/fixtures/a66_town06_steer_raw.json` is byte-identical.
* CARLA 0.9.16, `Town06_Opt`, Model 3, road 48/section 0/lane -6; one `steer` control smoke, 5 m/s, 0.03 steer fraction for 0.15 s. One valid single-control run; 26 pretrigger and 40 posttrigger frames.
* Measured actual front wheel steering ~1.91 deg, peak |yaw rate| 0.120149 rad/s. Source sampled lane clearance ~0.451570 m.
* A66 independently recomputes **only declared straight-lane, sample and interpolated-pose geometry** from world XY/yaw and actor bounding box: interpolated minimum lower clearance ~0.422498 m across 65 intervals. **The true between-tick CARLA trajectory is not known to be an interpolation**. This is NOT a swept-physical safety certificate.
* `combined` raw JSON is **not present**. The provided chart depicts the same `steer` run, not a combined or independent verification. `brake` earlier has captured dynamics but gross torque-only-model discrepancy; not a validated guaranteed stop bound.

## New A66 software, scope and falsification

* `a66_carla_lateral_witness`: all frame/clock data, commanded and actual front wheel angles, yaw response, heading finite difference cross-check, independent straight-lane footprint projection, and conservative over-interpolated-pose extrema. Rejects missing trigger, missing wheel angle, bad yaw dynamics, negative lane margin. Returns `DESCRIPTIVE_...NOT_CERTIFIED` only.
* `a66_cosim_clock_contract`: checks declared rational CARLA/SUMO clock and exactly one asserted tick owner, traffic control owner, ACK version, permission, resource clearance; rejects skips, rollback (also across missing ACK), missing registration and time skew. This function does **not** contact a simulator or independently authenticate actual ACK or map registration.
* `a66_hybrid_contract_binding`: checks consistency among exact clock partition, declared per-hidden-world evidence ledger, rational interval handoff and SHA declarations. **Does not hash artifact bytes** or invoke Picard. Same-public-history controls must match.
* `a66_evidence_inventory`: visibly marks `brake/steer/combined` separately, never substitutes one for another, never generates training labels.
* Provenance digests alone are not physical proofs. Tests for missing/forged inputs have explicit UNKNOWN/REVIEW behavior. M1–M13 and all eight label gates remain subject to independent replay and cross-system validation.

## Next scientific acceptance criteria

### P0: CARLA combined and actuator response

In exclusive CARLA Town06 instance, repeat 5 m/s small pulse with `--smoke-maneuver combined --steer-fraction 0.03 --steer-pulse-s 0.15`, preserving a new raw path, and run both `a64_review_carla_smoke.py` and `a66_review_carla_lateral.py`. Require genuine nonzero **simultaneous** brake/steer command, actual front wheel angles, measurable yaw, correct time and lane status, no aborted approach; each condition is necessary, not sufficient for a physical certificate. Run 3 repeats and expand to 10/15 m/s only after range check; do not change steering protocol and pool results without provenance.

### P1: M1–M2–M5–M6–M8–M10 real mixed Native Post

Take exact `a61` atomic slabs, apply the same public control to every hidden state with the same observation history, perform *fresh MPFR Picard* inclusion on each slab, propagate end outer set to next slab, check actual world/region swept occupancy and resource entry/stay/exit plus permissions/versions, merge posteriors by observed public history, and close a finite accepting terminal tail. All physical and support claims must be **independently replayed from actual bytes**, not a consistent digest table. Require adversarial tests: rule inside a step, late/missing ACK, resource capacity conflict, hidden states indistinguishable before receipt, rank not decreasing. An unresolved sub-obligation means UNKNOWN, not policy certification.

### P2: Independent parallel simulation and source chains

* Waymax: preserve dataset-native motion and actor identity; align acceleration/steering discrete model to the paper's jerk/steer-rate and rear-axle convention with explicit integration and residual tests. IDM is an example response, never exhaustive behavior support.
* Traffic/Guard: produce authoritative sourced issue/effective/receipt/ACK intervals, controller phase memory, direction and capacity; never equate message absence with clearing. Gate source versions through an actual visible physical signal feedback.
* SUMO: re-run nine A58 `ERROR` scenarios into fresh output dirs, not overwriting reports, and convert logical alternating corridor into an actual registered shared resource and real road footprint.
* CARLA/SUMO: choose map with a verified common network (CARLA official Town01/04/05 examples), a single step owner, a single signal authority and a single physical ego owner; log both snapshots, versioned ACK and exact coordinate transformation; tests first use synthetic traces then actual dual-engine replay.
* 511NY/ROADWork: keep published/reported/effective/observed times separate, spatial extent uncertainty, source and licensing; absence of observation is censored, image boxes aren't metric closure truth.
* Four truth levels: producer report -> independent descriptive replay -> validated simulation model-relative enclosure -> complete observation-aware SC certificate. None may be silently promoted.

## Long-term M1–M13

| Gate | Status and independent missing evidence |
|---|---|
| M1 | Partial native MPFR; *per-slab verified Picard with calibrated disturbance* open |
| M2 | Exact partition + declarative cosim ledger; *live multi-clock receipt/effective timeline* open |
| M3 | Real actor geometry/one brake/one steer; *joint controls and bounded execution residuals* open |
| M4 | Waymax/IDM synthetic; *actor response support under ego interventions* open |
| M5 | Static samples & limited swept resource contract; *general polygon continuous occupancy* open |
| M6 | Declared Guard states; *physical rule version/capacity/direction authority* open |
| M7 | Declared version ACK; *physical controller feedback and vehicle command delay* open |
| M8 | Exact hidden worlds in small supports; *complete reachable protocol support* open |
| M9 | Public history syntax; *sensor visibility, occlusion, message receipt semantics* open |
| M10 | Conditional SC rank; *complete accepting terminal policy and all posteriority branches* open |
| M11 | Candidate/small oracle infrastructure; *complete finite class infeasibility proof for negatives* open |
| M12 | Standalone simulator experiments; *real mapped CARLA/SUMO synchronous co-run* open |
| M13 | Head schema/source planning; *independently proven and masked labels* open |

Eight labels: `event`/`joint` only with provenance and observational scope; `occupancy`/`observation` with geometric/sensor receipt evidence; `viability` positives require complete policy certificate and negatives exhaustive finite-class impossibility; `margin` validated conservative bound; `deadline` same candidate prefix with timed-game proof; `causal` exogenous matched paired intervention. None can be inferred from one CARLA trace.
