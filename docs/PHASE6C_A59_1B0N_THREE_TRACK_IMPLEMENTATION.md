# Phase 6C A59/1b-0N (A68) — Three independently gated tracks

**Scope:** Incremental source release based on A59/1b-0M. No update to the manuscript's certified mathematical claims. A68 is the *entry phase* for genuine A59/1b-1 hybrid Native Post, not completion of that task. All model/empirical claims below are scoped and do not produce real-world safety labels.

## Corrected audit defect before final release

A64/A67 originally accepted a combined-control excitation only when `command_brake >= 0.20`, although the A60 CARLA capture tool permits a declared `--combined-brake-fraction` as low as 0.05. This would incorrectly reject the proposed 0.15 diagnostic. In A59/1b-0N, these auditors now compare all post-trigger brake commands against the explicit per-trial declared fraction (0.05–0.80), and detect a false/mismatched declaration. Four graded/legacy compatibility tests passed. Older raw A67 files without a declared fraction are admissible only when their full post-trigger brake command sequence is constant: the inferred profile is explicitly marked `LEGACY_CONSTANT_COMMAND_INFERRED_DESCRIPTIVELY` and remains non-certifying. An inconsistent or falsified declared fraction is rejected. **Changing the declared profile changes the experiment: a synthetic copy is not a real 0.15 trace and does not validate physical response.**

## Evidence from three new independent CARLA uploads

- CARLA 0.9.16, Town06_Opt, Tesla Model 3, actual actor IDs 121, 122, 123; 66 recorded frames per run, 26 before and 40 after trigger, 0.05 s nominal frame time.
- Raw files differ in SHA-256 and use disjoint actor IDs / world frames / world time ranges. The 0.45 combined brake + 0.03 steering pulse (0.15 s) uses a common map OpenDRIVE hash and physical configuration.
- All three normalized response traces are identical: ~26.926564657 m/s² peak negative longitudinal acceleration magnitude and ~0.0572846533 rad/s peak absolute yaw rate. This is deterministic replication, **not** a measured disturbance bound.
- A67/A68 retain `GROSS_TORQUE_ONLY_MODEL_DISCREPANCY`; four nominal 700 N·m wheels / 0.37 m radius / 1845 kg give only ~4.10 m/s² for the oversimplified torque-only comparator. These are different levels of physical description. Neither 4.10 nor 26.93 is independently a guaranteed real vehicle deceleration.

## Mathematical track, M1/M2/M5/M6/M7/M8/M10

`python/rampd_core/a68_affine_slab_replay.py`: exact fractions for a controlled *reference* x'=v, v' in [a_min,a_max], with exact endpoint and all-tube outer enclosures over each atomic clock slab. Strict world/slab inventory, no nonanticipative control mismatch within a common public-history group, next-slab start must cover all prior end possibilities. Detects invalid interval direction and missing worlds. **Does not run the six-dimensional Native MPFR bicycle or prove completeness of actor/rule/observation supports.** The constant-acceleration bound is itself a *declared assumption*.

`python/rampd_core/a68_guard_resource_monitor.py`: single **exclusive-clearance** zone, actual transition *declarations*, explicit entry/stay/exit permissions, ACK version, direction, capacity, exact clock grid. Fails closed if either actor roster or controller authority is not attested. **No continuous polygon occupancy, full physical interlock or network ACK observation is inferred.** Do not generalize this simplified zone monitor to arbitrary shared road topology.

Next A59/1b-1: native MPFR/Picard per atom/per slab; physical state and controller memory handoff; continuous swept polygon resource entry/stay/exit; lossless hidden support and public observation posterior merging; accepting-tail proof and rank descent. Independent failure-oriented tests: mid-step rule effectivity, delayed/lost ACK, entering when permission closes, hidden message leakage, unbounded waiting and false terminal stopping.

## Physical track, M3/M4/M12 plus traffic simulation

`python/rampd_core/a68_physical_campaign.py`: strict 3-run protocol check with raw JSON duplicate-key refusal, actual actor physical parameter matching after *excluding only actor-ID and metadata-capture-frame fields*, disjoint actor/frame/time traces, 26+40 sampling, simultaneous 0.45 brake and 3-frame 0.03 steer command, actual controller echo, captured lateral witness. Only diagnoses 5 m/s/0.45/0.03/0.15 s at current physics settings.

`python/rampd_core/a68_waymax_action_contract.py`: explicit nominal paper jerk and steer-rate state to Waymax's constant-acceleration/curvature action contract. For a fixed jerk, the midpoint constant-acceleration approximation has **exact nominal longitudinal position discrepancy** |jerk| * dt^3 / 12. Lateral error and frame transformation are not bounded.

Next CARLA experiment: 5 m/s controlled brake-command sweep 0.15/0.30/0.45 as *separate protocols*, one command each initially; preserve 0.05 s physics, actual wheel angle, reported velocity, command and per-wheel configuration. Then steer/speed/friction sensitivity and withheld-condition validation. Do not use repeated identical traces as a statistical uncertainty estimate. If the ~27 m/s² anomaly persists, investigate brake physics/transmission, contact physics and individual force/torque observables before fitting a physical envelope.

SUMO: rerun nine missing controller summary outputs in fresh work directories (never overwrite), reconcile signal command/request/ACK and actual physical lane/overlap geometry, test opposing flow on one physically shared conflict zone. CARLA/SUMO: independent map registration, sole tick owner, unique actor ownership, output timing and real ACK. Neither has been run live in this local A68 audit. 511NY/ROADWork: retain report/ingestion/observed time uncertainty separately from rule effectivity and metric geometry. Waymax and SUMO tasks **need not wait** for CARLA parameter closure; full physical SC needs a validated cross-simulator model.

## Evidence and supervised learning track, M9/M11/M13

`python/rampd_core/a68_supervision_release.py`: eight named source roles, SHA-256 raw content verification, duplicate JSON key refusal, explicit unknown masks. Factual/auxiliary reports may be retained as **source-only**; no offered claim is a formal label without the independently reproduced proof. No safety-training label is released in A68. `L_joint` factual logged trajectories cannot be substituted for counterfactual responses; `L_event` incident reports are not physical effectivity clocks; `L_occupancy` sampled boxes are not continuous occupancy; `L_observation` is not a benchmark history valid bit. `L_viability`, `L_margin`, `L_deadline` need proven physical continuation, tube and protocol; `L_causal` needs true paired interventions with exogenous conditions fixed. An UNKNOWN is never the number 0 / negative example.

Next: separate factual/auxiliary and formal label factories; independently replay finite policy-class infeasibility for negatives; verify posterior union, terminal accepting tail and physical margins; maintain per-claim scenario ID, data split, source SHA, time frame, bounds and reason-coded masks. No assumption that data providers supply missing physical ground truth.

## Acceptance

- A68 new standalone tests: 42 (synthetic and exact arithmetic, plus three raw CARLA fixtures and corruption tests). Full Python regression target >=875, CTest 3 on newly reconfigured server build; zero skipped/failed/errors.
- Local uploaded historical native executables can be rerun, but new server build and live simulators remain **PENDING** until actual logs are uploaded.
- CLI `scripts/a68_review_parallel_tracks.py` reports three tracks, with all eight formal masks held at 0.
- M1–M13 **none** are finally closed as joint system assurance merely by this release. Exact Q reference mathematical model is not Native proof, sampled physical repeat is not error support, SHA is not semantic validation, and certificate availability is not independent teacher correctness.
