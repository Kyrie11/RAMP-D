# Historical mathematical and semantic audit (pre-A3 snapshot) — latest manuscript vs Phase 0–6C

> **Historical audit, not the current implementation status.** This document was written before Phase6C-A3/A4 added `safe_continuation.py` and `sc_proof_audit.py`. Its entries saying `W_h^SC`/rank are entirely MISSING have been superseded for the **finite conditional abstraction only**. Current status: `docs/PHASE6C_A4_MATH_GATE_20261117.md` and `docs/PHASE6C_A5_1_DESIGN_AND_ACCEPTANCE.md`. Physical all-history terminal-tail replay, genuine full-support proof and ICG remain missing.


## Method and epistemic boundary

Source of truth: uploaded latest `AnonymousSubmission2027.tex` (snapshot `manuscript/AnonymousSubmission2027.tex`, hash in `manuscript/SOURCE_MANUSCRIPT.sha256`) (`Problem Formulation`, `Planning Method`, physical/protocol/network/verification appendices). Implementation locations refer to modules in this archive. Historical server reports are evidence only for their declared tests; this review is a **contract inspection and scoped regression**, not a fresh native numerical verification for every module. No new hard mathematical assertion is added to the verifier from a learned score.

| Formula / obligation in latest TeX | Code and audit | Status and immediate implication |
|---|---|---|
| Physical model `(p_x,p_y,psi,v,a,delta)` with control `(j,omega_delta)` and `dot psi = v tan(delta)/L_w` | `model.py`, C++ `interval_bicycle.cpp`, `reachability.py`; historical MPFR directed rounding/Picard certificates preserved without modification in this patch | **Earlier scoped tests only**. Fresh complete native MPFR CTest and numerical witness regression mandatory on target server. Dataset box-center is not ego state rear axle. |
| Physical footprint `F_i(x)` and resource occupancy `1[F_i(x) intersection P_r != empty]` | `footprint.py`, `resources.py`, `record_adapters.py` | Existing synthetic swept footprint support, **no real maps/calibrated mixed-actor shapes certified**. Ego rear offset must be measured. Unknown heading prevents rear conversion. |
| Correlated joint support `B`, posterior union of indistinguishable observations, public common control | `belief.py`, `invariant.py`, `observations.py`, `full_verifier.py` | Finite explicit-support skeleton only. Synthetic correctness does not imply a complete external-world transition/observation relation. Do not split policy by hidden rule activation. |
| Rule event sources `Q^ext`, `Q^act`, `Y^int`; issue/effective/receipt/local clocks and causal order | `protocol.py`, `record_adapters.FourClockInjection` | General contract skeleton. The two public datasets **do not** provide all four clocks. Simulator event instrumentation not yet built. No real protocol full support. |
| Entry `alpha`, continued occupancy/clearance `beta`, directions/capacity/controller `R_r` | `resources.py`, `protocol.py` | Synthetic resource monitor, not a complete legal rule precedence engine or calibrated controller. No inference of formal authority solely from traffic-light states. |
| Safety invariant `S_infinity` = greatest fixed point | `invariant.py`, `backup_graph.py`, `backup.py` | Scoped finite-inner safety domain only; prior brake/hold fixture not general robust indefinite stop. Valid safety-only fallback is **not** navigation completion. |
| Goal-conditioned terminal `K_term^SC` requires finite certified task acceptance tail | **No corresponding end-to-end module** | **MISSING**. Waiting/refuge is not terminal unless onward task route and bound are certified. |
| Winning inner family `W_h^SC` and rank `d(C)` with strict decrease for every observation on replan | **No task-ranked winning-set implementation** | **MISSING**; do not call current safety-invariant memberships viable for goal completion. Store tail and rank with protocol, clock, model and task automaton context. |
| Physical minimum margin `g_tube` and conditional `V_H^SC` on rank-feasible controls | `footprint.py` provides some separation bounds; `forecast.py` proposals | **MISSING** goal-conditioned `V` and terminal tail margin. A proposed/learned margin is a search score, not verified reserve. |
| SCO options including start/occupancy windows, observation guards, resource path, completion tail | `control.py` recovery templates and `backup_graph.py` | Templates are NOT paper-certified SCO: no task acceptance tail, inherited rank, dynamic scheduling or full graph. |
| `ICG(pi) = T_sep,+ (pi) - D_defer(pi)` on **same common prefix** | No sound ICG estimator/certifier | **MISSING**. Positive is warning, nonpositive not sufficient by itself: shared prefix still safe and rank-decreasing. Latest-start != decision-deferral deadline. |
| CCG coarse/refined resource graph preserving correlated hypotheses | Phase 4 `resources.py`, no full CCG builder | **MISSING** graph derivation from real lane polygons and conditional resource classes. Prediction cannot narrow verification support. |
| Causal joint factorization `Q_ext`, `Q_act`, motion, observation; actions only affect external events via permitted causal paths | `forecast.py`, `phase6c.py` baseline only | No trained intervention-aware model. CV baseline uses logged historical velocities. Rule soft scores preserve all proposals and do not change proof domain. |
| Conditional temporal controllability and public policy-tree multiple shooting | `full_verifier.py` finite branch skeleton | **MISSING** dynamic controllability and nonlinear optimization; discrete timing feasibility alone would not prove physical safety. |
| `CERTIFIED / COUNTEREXAMPLE / UNKNOWN`, CEGAR | `full_verifier.py`, `cegar.py` | Three-valued scoped synthetic contract; candidate counterexample is NOT a proof of initial task infeasibility. All concrete real traffic requires calibrated full support. |
| Dataset/simulator supervisory labels | `record_adapters.py`, `phase6c.py`, `clock_ledger.py` | Motion ADE/FDE and parser/clock checks implemented; other six losses' labels require separate sources/oracles below. |

## Eight supervision channels from the *revised* paper, not invented labels

| TeX loss | Allowed source | Constructed ground truth / prohibition |
|---|---|---|
| `L_event` | Explicit SUMO/CARLA protocol controller logs; real authoritative records when available | Event class, scope, formal resolution, activation/effectivity, issue/receipt intervals; use interval censoring and provenance. Dataset dynamic map snapshots are **not** sufficient for issue/receipt. |
| `L_joint` | WOMD Scenario and AV2-MF motion under actual logged ego actions; additionally seeded paired simulator interventions | Joint observed motion (masked) under **logged action only** for public data. No causal response to arbitrary ego prefix from the replay alone. |
| `L_occupancy` | Vehicle/actor footprint + actual lane/conflict polygon intersection; simulator geometry | Derive entry, stay, clearance, resource conflict and capacity masks. Missing geometry = UNKNOWN, not zero or no-conflict. |
| `L_observation` | CARLA sensor production/delivery, occlusion/visibility, SUMO message publish/receipt logs | Separate possible detection from guaranteed public receipt. Censored silence only when protocol specifies delivery guarantees. |
| `L_viability` | Certified task-winning inner witness; negative ONLY from complete finite-game oracle for declared finite model | `positive/negative/unknown`; leave incomplete solver output and losing single-candidate attempts UNKNOWN and mask. |
| `L_margin` | Outward reachable tubes plus hard feasible candidate solver | Conservative continuous margins with explicit units/normalization. A time-discrete nearest-center gap or predicted TTC is not a verified lower bound. |
| `L_deadline` | Declared protocol clocks + resource windows + interval reachability + exact small scheduler | Option latest-start, guaranteed observation separation bound and decision deferral **on same prefix**; unresolved = interval/UNKNOWN, not mean latency. |
| `L_causal` | Paired simulator interventions sharing exogenous seed, initial state and protocol realization | External events invariant to ego prefix; actuated rules may change only through flow/controller evolution. No such paired labels in AV2/WOMD alone. |

## Additional discovered source-semantic defects fixed

1. Official AV2 Parquet writes `TrackCategory.value` 0/1/2/3. The legacy string-only categorizer silently lost `FOCAL_TRACK` and `SCORED_TRACK` for real records. `record_adapters.py` parses the official numeric enum; AV2's `focal_track_id` is separate from the collection vehicle with ID `AV`.
2. WOMD `tracks_to_predict.track_index` is a **tracks array index**; scenario `Track.id` is the stable object ID. The mapping is preserved; `objects_of_interest` are object IDs. Protobuf missing scalar presence must not become a physically meaningful zero.
3. Test split `future_available=False` previously only metadata-masked; now invalidated future coordinates, headings and velocities in the scene. Offline metrics refuse unavailable labels.
4. A global offset for all other actors gives physically incorrect rear-axle coordinates. Multi-car conversions require actor-specific offsets. Missing yaw rate with a nonzero body offset erases the incompatible center velocity instead of silently reusing it for a rear-axle coordinate. Mixed pedestrian/cyclist scenes keep source box centers; ego-specific geometry belongs in the ego dynamic-state adapter.
5. File-shard SHA-256 is not per-record evidence identity; both hashes are now available when protobuf serialisation is supported.
6. AV2 Phase6A audit previously demanded the optional `av2` package even though the actual reader depends on pandas + a Parquet engine; its dependency gate has been corrected.
7. Original Phase6B validation script printed `LOCAL_PASS` after SKIP. The repaired script returns nonzero on incomplete real-data validation.

## Mathematical non-claims

- Dataset sample rate `10 Hz` and CARLA/SUMO fixed step `0.05 s` do NOT bound all intersample disturbances or certify collision-free swept trajectories.
- The soft RuleNet hook is not a trained classifier, is not resource-legal proof and never prunes an environment branch.
- Synthetic solver `CERTIFIED` cannot be upgraded to real-traffic `CERTIFIED` without the exhaustive, calibrated protocol/observation/agent/geometry contract.
- No claim of globally sound or numerically exact *entire* new manuscript implementation should be made pending native tests and the missing task-winning, ICG and temporal solver components.

## Research provenance

- WOMD `scenario.proto`: https://github.com/waymo-research/waymo-open-dataset/blob/master/src/waymo_open_dataset/protos/scenario.proto
- AV2 official schema: https://github.com/argoverse/av2-api/blob/main/src/av2/datasets/motion_forecasting/data_schema.py
- AV2 Parquet serialisation: https://github.com/argoverse/av2-api/blob/main/src/av2/datasets/motion_forecasting/scenario_serialization.py
- AV2 user guide: https://argoverse.github.io/user-guide/tasks/motion_forecasting.html
- CARLA 0.9.16 co-sim documentation: https://carla.readthedocs.io/en/0.9.16/tuto_G_retrieve_data/
