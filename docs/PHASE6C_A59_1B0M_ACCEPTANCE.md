# Phase 6C A59/1b-0M (A67) — actual combined-control diagnosis and byte-authenticated evidence gate

**Scope:** make the user's CARLA 0.9.16 5 m/s combined-control evidence independently reproducible; distinguish diagnostic repeat eligibility from actuator calibration; close a false-confidence gap in previous A66 cross-artifact comparison. **NOT** a completed hybrid native Post, a CARLA physical error enclosure, or an ICAPS-safe-continuation certificate.

## User-uploaded facts (do not upgrade)
- `town06_5ms_combined_raw.json`: one Town06_Opt `vehicle.tesla.model3`, 66 frames at dt≈0.05s (26 through trigger, 40 after). Brake=0.45; normalized steer=0.03 for three frames (0.15s). Actual wheel steer≈1.9°, measurable yaw≈0.0573 rad/s. All logged instantaneous rectangle/lane checks positive.
- CARLA reports longitudinal deceleration peak around 26.9266 m/s², agreeing with the finite speed difference to the precision of current data; this is far from the **noncertifying comparison model** Σwheel_torque/radius/mass≈4.10 m/s². At 0.45 brake command the **linear brake-scaled comparison** ≈1.85 m/s² is even further away. It is not legitimate to conclude the vehicle deceleration capability is guaranteed or that CARLA itself is physically wrong.
- `town06_5ms_combined_a64.json`: captured-only status. `town06_5ms_combined_a66.json`: positive sampled/interpolated-pose lane witness; NOT a verified reachable sweep or physical calibration. Minimum source sampled margin ~0.534 m; independent-axis sampled/interpolated model margin ~0.505 m.
- Raw sample is a **single trial**. Neither stochastic uncertainty support nor a robust dynamics envelope can be inferred. The measured positive margin is not \\(\\mathcal L_{margin}\\) evidence.

## Implemented
1. `a67_carla_combined_diagnostics.py` and `a67_review_carla_combined.py`: real simultaneous brake+steer+wheel+yaw witness, actual byte/raw inputs, velocity vs acceleration moving-pair crosscheck, gross torque-only model REVIEW, no safety labels.
2. `a67_repeat_campaign.py` and `a67_review_combined_repeats.py`: inspect independent run file SHA-256, identical-protocol strata (map hash, physics, time-step, maneuver, weather, control strength), distinguish physically identical responses from uncertainty coverage. Even a complete 3-run diagnostic campaign does not yield a guarantee bound.
3. `a67_artifact_bytes_binding.py`: A66 `WorldSlabBinding` compared declared SHA hex strings but not referenced bytes. A67 requires actual raw bytes, verifies SHA-256 and typed world, exact rational slab times, public-control identity, role and protocol file. This is **content integrity only**; replays of Picard, Guard, resource polygons, public observation, liveness rank and terminal accepting policy are still TODO.
4. `a60_carla_actor_trials.py`: adds `--combined-brake-fraction` (0.05–0.8, default 0.45), recorded with trial protocol. Enables graded 0.15/0.30/0.45 trials without quietly mixing them into a single distribution.
5. 18 mutation and adversarial tests for false combined evidence, physical parameter corruption, missing bytes, replaying digest declarations, missing repeat runs, repeated duplicate records and changes in run protocol.

## Actual local acceptance
- Complete Python regression: **833/833 PASS**, JUnit `/mnt/data/a67_artifacts/full_pytest.xml`, with `RAMPD_INTERVAL_LIB=/mnt/data/a66_native/librampd_interval.so`. Test includes all earlier math/protocol tests in this repository. This does **not** prove their mathematical assumptions or all mathematical logic correct.
- A67 new pure/integrated: **18/18 PASS**.
- Historical C++ executable tests: 3/3 direct execution PASS using uploaded native runtime. Not a new CMake build or actual new native mathematical post.
- Latest A67 combined diagnostic: `DIAGNOSTIC_REPEAT_ELIGIBLE_MODEL_REVIEW_NOT_CALIBRATED`; gross torque-model discrepancy remains open.
- Repeat campaign: only 1 run provided; `REVIEW / INSUFFICIENT_VALID_REPEAT_ATTEMPTS`.
- CARLA server, SUMO runtime, Waymax live and CARLA–SUMO twin simulator were NOT invoked locally.

## M1–M13 — claim boundaries
| Gate | What is actually checked | Still missing |
|---|---|---|
| M1 MPFR/Picard | Existing native + Python regression, slab interval continuity | True native per-slab proof replay and complete physical model |
| M2 exact Traffic event clocks | Rational time partition, public history grouping | Actual issue/effective/receive/ACK trace and runtime slab execution |
| M3 ego model | Real actor metadata and combined-control capture | Validated physical delay, friction model, 5/10/15m/s + perturbations, certified residual envelope |
| M4 reactive other vehicles | Existing declared IDM/Waymax checks | Complete realistic counterfactual response support |
| M5 continuous footprint | Conditional rectangle/interpolation, declared swept checks | Actual reachable continuous polygons, topology and numerical enclosure |
| M6 rules/capacity | Declared dynamic Guard and conflict checks | Complete authority, entry/stay/exit, verified capacity and version semantics |
| M7 interlock/ACK | Declared version/owner checks | Physically observed signal and actuator acknowledgment |
| M8 hidden protocols | Finite declared worlds, no-early-control tests | Full hidden-world support and adversarial observation outcomes |
| M9 public observation | Public history grouping and token checks | Real sensor occlusion/message latency uncertainty |
| M10 SC terminal and rank | Finite rank gates and handoff checks | Real task accepting tail and complete goal-directed policy replay |
| M11 teacher | Conditional finite oracle structure | Complete policy-class positive and negative witness with independent validator |
| M12 sim fidelity | CARLA data present, old SUMO roster/audit | SUMO missing 9 reports, matched actual physical resource, real cosim |
| M13 eight labels | Separate source inventory and non-certified masks | Independently replayed full provenance per loss; NO certified labels yet |

## Math integrity caveat and next step
The paper's observation-aware predecessor requires a common *public* action, continuous `SafeTube` for **every** hidden possibility, all observationally merged posterior supports in the certified predecessor family, and inherited finite rank to verified task acceptance. A verified SHA-256 of an alleged tube is not evidence that it actually encloses the system; and a CARLA observed lane trace is not a continuous reachable tube. The immediate math milestone A59/1b-1 is to invoke the **actual** MPFR/Picard solver for every event atom and jointly replay Guard/resource/observation and accepting task tail using verified content. Tests must inject: in-slab rule change, missing ACK, changed hidden-world support, nonanticipativity breach, interval underapproximation, boundary crossing and rejected goal tail. Fail closed to `UNKNOWN`, never turn UNKNOWN into a negative training label.

## Independent CARLA experiment design
1. Current combined 5 m/s 0.03 × 0.15s, brake 0.45: repeat **three distinct fresh runs** (unique filenames) for repeatability diagnostics. Do not infer confidence bounds from deterministic repeats.
2. In an isolated simulator, grade `--combined-brake-fraction` 0.15 then 0.30 then 0.45 (one smoke each). Distinct protocol groups, never pool them without explicit domain stratification. Inspect gross stopping behavior and the 0.1–0.2s apparent transition; do not identify actuator delay solely from a sign change in net acceleration.
3. Only if all first-stage simulations remain in the declared lane and capture traces are complete, expand to 10 m/s and 15 m/s with an independently checked safe road/area, then repeat with friction/surface/physics perturbations. Collect actual applied wheel angles, engine and brake response telemetry if version permits, and record simulator build and world configuration.
4. For the **actual** `safe` envelope, identify model vs CARLA residuals with train/held-out config splits and independently justified physical disturbance limits; CARLA 0.9.16 simulated behavior by itself does not yield real-world guaranteed μ or closed-loop delay.

## Parallel engineering, independent of CARLA completion
- Traffic clocks + Guard: real event/command/ACK trace schema, sourced authority and version chain, integrate into event-split Native Post.
- Shared resources + SUMO: complete real road polygon and opposing-lane topology, reproduce all 12 original runs with fresh work directories, independently cross-check controller summaries (old 9 were missing due directory reuse).
- Waymax: reference-point/handedness alignment, discrete acceleration-curvature to jerk-steering-rate interface, record actor-response sets; not full adversarial support.
- CARLA/SUMO bridge: choose matched Town04/Town05 rather than assuming Town06 geometry matches SUMO, unique tick ownership, map registration, signal ACK trace.
- 511NY/ROADWork: report/physical effective/received time and metric resource uncertainties remain distinct; images alone do not supply verified spatial occupancy.
- M10/M11/M13: terminal acceptance + independent teacher first, then eight per-loss labels with explicit UNKNOWN masks and proof references.
