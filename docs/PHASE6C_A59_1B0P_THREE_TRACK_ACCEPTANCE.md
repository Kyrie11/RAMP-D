# RAMP-D Phase 6C A59/1b-0P (A70): independent three-track acceptance

## Scope and scientific conclusion

This release is the **next conditional step**, not Phase A59/1b-1 complete. It is based on the uploaded A59/1b-0O full source archive and the three **real** CARLA Town06 `combined_b{0.15,0.30,0.45}.json` traces. The manuscript is not modified. Paper's formal task-success condition remains

\[
 W^{SC}_0=K^{SC}_{term},\quad W^{SC}_{h+1}=W^{SC}_{h}\cup(B_{safe}\cap Pre_{obs}(W^{SC}_{h})),
\]

with a *single public nonanticipative action*, validated continuous `SafeTube`, full posterior support under every public observation, rank decrease and an independently replayed finite accepting tail. An action being continuously safe without a verified onward task route is **not** a completed SC certificate.

## Track 1: mathematical (M1, M2, M5, M6, M8, M10)

**Actually newly executed:** `a70_native_segmented.py` invokes the existing C/MPFR Picard integrator and full `replay_certificate` on **four distinct 6D native ego slabs**: two initially observation-indistinguishable worlds, an exact rule-effective boundary at `1/20 s`, two substeps per world. The source supplies explicit world/start/end/control/initial box/disturbance, and a new independent partition is reconstructed from the events. The test checks the physical *value* of public controls (not merely the control string), missing hidden worlds, clock integrity, complete tube witnesses and the sound direction of endpoint-to-next-start inclusion. Exact physical event time is not silently rounded to a binary64 sample: a local outward binary64 horizon encloses the exact fraction, and `exact_step_endpoint` retrieves the exact-time enclosure.

**New A70 necessary conditions:** `a70_hybrid_guard_preflight.py` independently reads the Native certificate data and SHA, replays the certificate, projects the complete Picard tube onto a simple one-dimensional resource, and rejects possible intra-slab resource intersection even when both endpoint snapshots appear empty. Permissions are explicitly **start-of-slab** rather than using a future endpoint state. ACK events arriving at the next boundary cannot retroactively authorize entry. Capacity and opposite directions are checked in the starting roster. The terminal rank screen rejects a nondecreasing rank or rank-zero without a declared accepting tail. These are **fail-closed screens**, not complete polygon collision/SC proof.

**What remains unproved:** actual complete road/resource polygons, continuous enter/stay/exit automaton for all actors, authority and acknowledgment sourced from running traffic infrastructure, physical observation kernel, complete hidden-world enumeration, complete actor disturbances/real-vehicle mismatch, independent terminal policy and full finite SC strategy. None of these can be completed by a simple witness hash or assumed completeness flag. The A70 executable is an actual native dynamics demonstration but is a synthetic, straight, constant-velocity microcase only.

Seven adversarial cases: (1) indistinguishable hidden worlds need the same numerical controls; (2) rule changes at the right-continuous internal boundary; (3) late/missing ACK cannot justify the previous slab; (4) false initial occupancy or missing support is rejected by A69 and A70; (5) initial overcapacity and opposing direction rejected; (6) possible between-frame resource entry forces UNKNOWN; (7) rank non-decrease and unverified tail force UNKNOWN. **These do not constitute a single certified, general-road end-to-end example**.

## Track 2: physical (M3, M4, M7, M12)

Uploaded independent raw CARLA measurements: 5 m/s, Tesla Model 3, Town06_Opt, brake fractions **0.15/0.30/0.45** each with steering command 0.03 for 0.15 s and a 0.05 s simulation step, one repeat per brake arm. Trigger speed approximately 4.892842 m/s for each arm. `a69_physical_factors` confirms comparable declared configs and three unique source files.

| Brake input | Max recorded decel (m/s²) | Peak frame after trigger | Speed at peak (m/s) | First measured rest (s after trigger) | Observed post-trigger planar path (m) |
|---:|---:|---:|---:|---:|---:|
| 0.15 | 23.407819 | 39 | 0.530744 | 2.00 | approx 6.570 |
| 0.30 | 26.927363 | 4 | 2.838201 | 0.35 | approx 1.042 |
| 0.45 | 26.926565 | 4 | 2.824778 | 0.35 | approx 1.039 |

**New distinction:** A peak at `0.53 m/s` in the **near-stop** region is not comparable to a peak at `2.8 m/s` in active travel. The `0.30`/`0.45` traces indicate a plateau in the measured peak under these conditions, not a general identified saturation law. 1 repeat per intervention cannot estimate stochastic disturbance support. Even 3 identical repeats at 0.45 would not supply a worst-case bound. Reported and velocity-differenced acceleration share CARLA's own physics solver, not an independent physical ground truth.

**Corrected trial design:** Original `a60_carla_actor_trials.py --smoke-maneuver brake` used hard-coded `0.70` and could not isolate braking from steering. A70 adds explicit `--brake-only-fraction` default 0.70, separate from `--combined-brake-fraction` default 0.45, and updates A64 so legitimate 0.15 brake-only commands pass descriptive auditing, while non-zero steering in a brake-only trial is rejected. A proper small factorial design holds speed/map/tire/weather/clock constant, changes brake fraction among 0.15,0.30,0.45 and steering between 0 and 0.03, and runs at least 3 repeats/arm as a diagnosis (not a worst-case guarantee).

Still missing: repeat per arm; independent brake-only comparison; 10/15 m/s; separate tire friction, actuator lag, lateral dynamics and steering response; physics substep audit; real road-relevant error enclosure; Waymax counterfactual support and reference-frame conversion; 9 missing SUMO controller summaries; actual CARLA/SUMO one-owner tick, map registration, true signal ACK and control arbitration. **Not all simulator pre-work requires CARLA to finish**, but joint physical SC does.

## Track 3: evidence / supervision (M9, M11, M13)

A69 split checks use declared `scenario_id`, which can be renamed for another annotation of the same recording. A70 adds declared immutable-root grouping (`dataset_id`, `root_scenario_id`, `recording_family_id`) for all derivative files and interventions, rejecting same-root train/validation/test leakage even when different `scenario_id` values are supplied. It also rejects missing root provenance. **Root identity is still a producer declaration** until externally reconciled with actual dataset recording IDs. The gate **never releases certified safety labels**.

Recommended staged rollout of *domain-limited auxiliary* sources, preserving scope and masks:

1. `L_event`: simulated effective/publish/receive/ACK with causal clocks; 511NY time is report evidence, not onset truth.
2. `L_joint`: factual AV2/WOMD agent trajectories, Waymax/IDM *modeled* counterfactuals tagged separately, validate support coverage.
3. `L_occupancy`: source-registered geometry + sampled footprint as auxiliary, then independently verified continuous envelopes.
4. `L_observation`: actual sensor visibility, occlusions, receipt and censored silence, not global hidden-state truth.
5. `L_causal`: simulator paired interventions sharing external seed, time, actor initial state and an explicit causal DAG; no actual driver truth required if clearly labeled synthetic.
6. `L_viability`: independent complete conditional policy/tail proof for positive; full finite-policy-class exhaustion for negative, UNKNOWN otherwise.
7. `L_margin`: validated physical/actor tubes and robust lower clearance bound, with correct normalization.
8. `L_deadline`: information-separation bounds + commitment deadlines conditioned on the same SC feasible policy and event authority.

Do not create a single eight-head `CERTIFIED` sample until its own per-head conditions pass. A learning model's predictions cannot be used to certify its teacher.

## M1–M13 acceptance ledger

| Gate | Actual completed level | Open, next source of independent acceptance |
|---|---|---|
| M1 Native MPFR/Picard | A70 4 6D model-conditional slabs, replayed | General motion/resource joint Post, model error support |
| M2 Exact clock | Model-right-continuous split exercised | Real event source/effectivity/ACK sensor timeline |
| M3 Ego physics | Actor metadata, readiness, 3 brake interventions | Brake-only factorial, repeats, friction/speed/delay and justified enclosure |
| M4 Agent responses | Existing IDM/Waymax experiments, nominal jerk adapter | Empirically grounded adversarial reaction support and correlations |
| M5 Continuous geometry | Simple Native 1D projection negative screen, existing rectangles | General polygons and enter/stay/exit with all full swept bodies |
| M6 Authority / capacity Guard | Start-slab capacity/entry/direction negative checks | Effective authority/jurisdiction versions, real occupancy protocol |
| M7 Actuation / interlock | Declared receipt/ACK and CARLA controls | Physical signal ACK and response latency |
| M8 Hidden protocol | Two-world nonanticipativity with explicit support | Completeness of all hidden rule, delay, observation branches |
| M9 Observation | Public-token model | CARLA sensor visibility and real receipt timeline |
| M10 SC and task completion | Rank necessary screen and earlier conditional adapters | Accepting finite tail, full safe Post, rank inherited |
| M11 Independent Teacher | Finite submodel oracles | Complete policy-class positive and negative witnesses |
| M12 Simulator fidelity | Real CARLA measured, historical SUMO source reports | 9 SUMO missing control summaries and physical CARLA/SUMO sync |
| M13 Eight losses | Source-family firewall / UNKNOWN masks | Individual proof-role replay and formal training label factory |

**Final state: all M1–M13 gates are NOT globally closed; no formal training labels issued.**

## Local tests and limitations

A70 new regressions include 31 adversarial tests (26 native/clock/guard/physics/family, 4 brake-only control-compatibility tests and 1 clock-source-digest tampering test). The entire 77-file repository was independently executed in four non-overlapping pytest processes: **940 passed / 0 skipped / 0 failures**, with JUnit XML for every shard. A monolithic invocation in this local container did not return a JUnit summary before the execution budget; it is not counted as monolithic PASS. Three historical native C++ executables are available for direct replay, but **no fresh CMake build was performed** in this environment. Only the user server can attest the new clean build and live CARLA/SUMO runs.
