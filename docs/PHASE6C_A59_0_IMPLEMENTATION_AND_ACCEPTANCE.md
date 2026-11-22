# RAMP-D Phase 6C-A59/0 — Evidential repair and conditional Native Post → SC boundary

2026-11-22. This document is an **acceptance of independent local checks**, not an unrestricted SC proof or completed CARLA/SUMO physical simulation.

## 1. Objective, immutable algorithm definition

Paper's one-step task predecessor is `SafeTube(B,u)` AND `Succ_P(B,u) ⊆ K`, with same public observation histories merged and retained rank strictly decreasing. `SafeTube` must cover **all possible** dynamics, legal resource entry/stay/exit and all declared agents. `K_term^SC` requires a goal-accepting finite policy tail, not a stopped safe ego. Distinguish verified per-slab ego avoidance, complete guarded physical Post, model-relative SC rank and full-protocol physical task certificate. **Never generate training positives from local conditions only.**

## 2. What failed in uploaded A58 outputs

Server acceptance archive reports `679/679` full pytest, `3/3` native CTest, A58 pure `19/19`, A58 native `6/6`, and a conditional status; not proof of full SC or actual co-simulation. The 12 SUMO JSONs include only 3 `SUMO_LOGICAL_CORRIDOR_PASS` (slow_reaction/41, lower_friction_proxy/23 and /41). **Nine were overwritten with** `ValueError: fresh empty work directory required`, despite original `vehicle_trace.jsonl`, `roster_trace.jsonl`, network XML and simulator log surviving. The `carla_vehicle_params_raw.json` says `REVIEW_NO_VEHICLE_ACTOR`, `vehicle_count=0`. No live ego metadata or controls were measured.

## 3. Code repair and new scope

- `a59_sumo_forensics.py` + `audit_a59_uploaded_a58.py`: independently stream per-run raw vehicle/roster traces from ZIP (no full unzip), reconstruct frame grid, departed/arrived IDs, route-coordinate monotonicity, swept logical corridor occupancy, sample-to-sample deceleration and simulator warnings. Reconcile all counts for the 3 still-valid summary files. The other 9 remain REVIEW due to missing signal/control summaries. This audit **cannot** reconstruct per-tick TLS actual display, command ACK, 3D geometry or continuous-time dynamics from raw positional snapshots.
- `probe_sumo_alternating.py`: when the result JSON exists, stop without clobbering the previous output. Fresh report and fresh work directories are both required. Existing error-only output from an earlier run is not proof of failed traffic motion; preserve it for debugging.
- `a58_sumo_audit.py`: status allowlist, missing-field failure, profile checks, model-relative only; no implicit PASS for a `REVIEW_REQUIRED` or missing comfort/violation field. Baseline with sigma=speedDev=0 is marked deterministic replay, not independent behavioral coverage. Optional strict guard provenance check.
- `a59_sc_predecessor.py`: typed boundary for **already audited** native Post, requiring complete source atom match, every same-label successor merged, full posterior target-cell inclusion, sealed rank/step/support digests and strictly falling finite SC rank. Signal controller phase, version and clock are copied into **hidden** support coordinates; never exposed as an observation. Does **not** create new certified SC ranks, a general resource permission proof, branch completeness proof or valid task tail. `native_sc_predecessor` actually calls the MPFR native post and per-slab A58 safety audit; its return is at most `CONDITIONAL_PHYSICAL_RANK_PREDECESSOR_CANDIDATE`.
- `dump_a58_carla_vehicle_params.py`: read-only capture now explicitly includes wheel `max_brake_torque`, `max_handbrake_torque` and available speed steering curve. Raw units and calibration remain unverified; wheel brake torque does NOT establish guaranteed stopping deceleration.

## 4. Actually executed (this workspace)

- A58 existing pure tests: **19/19 PASS**.
- A59 new pure forensic tests: **11/11 PASS**.
- A59 Python syntax compilation: **PASS**.
- Full uploaded A58 ZIP independent raw trace scan: **12/12 traces read**, 108000 roster frames, 867 unique departures and 867 unique arrivals, no sample-to-sample deceleration >4.01 m/s², no mixed-direction logical swept occupant step and no SUMO warning/error line in the supplied logs. Exactly 3/12 have matching successful controller summary; 9/12 remain REVIEW with reason `MISSING_VALID_CONTROLS_SUMMARY`.
- **Not executed here:** any C++ MPFR CTest, full repo pytest requiring native backend, A59 native 5 tests, live Waymax/SUMO/CARLA, real brake/steer/latency experiments. No MPFR development headers, TraCI or simulators installed in this isolated environment. The uploaded server's 679 tests are historical, not a newly executed A59 acceptance.

## 5. Failure taxonomy and next substage

Observed: reused work directory and report clobber; no CARLA actor. Repaired report protection and summary fail-closed checking. Historical 12 raw traces have no counterexample for the **limited** tested monitors, but they cannot establish controller ACK or physically shared single lane. The logical SUMO model is two separate directed edges, not an actual one-lane physical resource. `lower_friction_proxy` changes SUMO configured decel and flow parameters, not measured tire-road coefficient. Waymax IDM curve-leader search and real driver response envelope remain unvalidated; 511NY event report times are not hidden physical onset/receipt; ROADWork visual boxes are not metric roadway occupancy.

Next **A59/1**: independent complete physical Post across general resource enter/stay/exit; bound physical state and phase to the same task/protocol observation relation, prove no branches dropped, check terminal accepting tail and inherited rank with independently enumerated tiny oracle. Only after this gate may the finite conditional task teacher become usable; any UNKNOWN must remain masked. **A5/3c-1** follows: CARLA/SUMO live sync, map coordinate registration, ego single owner, signal states/ACK and vehicle/obstacle registry and dynamics tests. These two workstreams should not be claimed complete on A59/0.

## 6. M1–M13 acceptance matrix (scope matters)

| Gate | 2026-11-22 judgement | Outstanding physical/mathematical closure |
|---|---|---|
| M1 MPFR/Picard | Historical server **pass**, no A59 native execution here | Re-run A59 native, certify configured uncertainty classes |
| M2 Exact clock | Partial | Real issue/receipt, observation and simulator sync provenance |
| M3 Ego physical model | Partial, nominal six-state model | Real rear reference, jerk actuator identification, speed/friction-dependent limits, error envelope |
| M4 Reactive agents | Declared envelope only | Driver model diversity, leader geometry and empirical coverage/calibration |
| M5 Continuous geometry | Interval SAT/rectangles present; conditional | Arbitrary resource enter/stay/exit & exit capacity/topology |
| M6 Resource rule/capacity | Guard hypotheses present | Formal legality and incumbent/clearance joint Post proof |
| M7 Traffic management | Simulated interlock/guard | Actor barrier deployment, monitor authority, fault ACK |
| M8 Hidden protocol | Finite declared branching present | Actual complete message/public observation relation |
| M9 Public sensing | Not complete | Camera/LiDAR/occlusion/actual delivery-latency logs |
| M10 SC / tail | **A59/0 local rank candidate only** | Independent verified complete SC predecessor and terminal acceptance |
| M11 Independent teacher | Not complete | Model-relative positive/negative/unknown proof with exact oracle |
| M12 Simulator fidelity | **12 trace checks, 3 complete summary matches** | Nine control summaries, physical co-sim, measured dynamics and Waymax curve geometry |
| M13 Eight-source production | Inventory/schema only | Evidence-gated label factory, source masks, train/holdout and real validation |

## 7. Eight losses and strict evidence source roles

`L_event`: actual simulator controller + protocol issue/receipt; 511NY reports only statistical event prior; `L_joint`: WOMD/AV2 factual ego-conditioned log, paired interventions later (not real counterfactual); `L_occupancy`: trustworthy box and map polygon matches and simulator sampled footprints, with unknown dimensions masked; `L_observation`: CARLA sensor/occlusion and actual message timestamps, ROADWork only visible-cue auxiliary; `L_viability`: independently verified complete finite contingent goal-winning policy for positives / exact finite-class impossibility for negatives; `L_margin`: proved lower bound of a **certified candidate** not the true maximized value; `L_deadline`: matched protocol/physical observation/candidate time intervals (not 511NY TIM duration); `L_causal`: fixed-exogenous A/A and A/B interventions with reactive agents, not log replay. Current A59/0 **produces none of these eight labels as fully certified supervised targets**.

## 8. Vehicle evidence sufficiency

Uploaded `车辆参数.md` is a **literature/measurement plan, not a measured CARLA actor calibration**. Tesla manual geometry 2.875m/4.695m/1.850m is a nominal physical vehicle, CommonRoad BMW 320i 2.579m wheelbase is another model, and ScenarioRunner's generic model3 XML 3.1m wheelbase is a simulation-scenario descriptor. Never combine these three as if from the same real CARLA blueprint. The attached CARLA JSON contains no car actors. Minimum additional data: one isolated `vehicle.tesla.model3` actor's `get_physics_control` and bbox metadata in CARLA 0.9.16; separately measured 5/10/15m/s brake and steering step response by speed + surface/friction setting, sample time, model and controller version, tire/wheel angular conditions, actual issued control and resulting pose/velocity/yaw rate. Fit conservative **bounds** and independent held-out errors; only then set `E_cert`, lower guaranteed braking and actuator delay bounds. No extra external full dataset required now.
