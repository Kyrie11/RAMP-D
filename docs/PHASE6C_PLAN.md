# Phase 6C — contract-first execution plan (manuscript revision aligned)

Canonical specification: the user-uploaded **latest** `AnonymousSubmission2027.tex`, not the older Phase 6B freeze. The pre-existing `docs/PHASE6_PLAN.md` calls for train ingestion, prediction proposals, RuleNet soft ranking, and SUMO/CARLA clock smoke in that order. This implementation is the **first bounded, testable Phase 6C candidate**, not completion of the paper's full planner.

## 1. Target and acceptance definition

1. Re-open and correct Phase 6B dataset semantics before adding training or simulation: WOMD `Track.id` vs `tracks_to_predict.track_index`, AV2 `FOCAL_TRACK` vs collection vehicle `AV`, AV2 category encoding and test future masking.
2. Parse train and validation independently (never use validation to train), preserve scene/source/record/map SHA-256, test overlap on the **sampled** scene IDs. Record the precise sampling limits.
3. Offer only an online-prefix `ForecastJob`; connect an explicitly untrained constant-velocity diagnostic baseline to `PredictionProposal/ProposalSet`. Evaluate full logged future with masked ADE/FDE. No fictitious causal intervention labels or prediction-based hard support.
4. Add a RuleNet-style score-combination hook. It MUST preserve every input proposal mode, not assert that RuleNet is trained or change resource permissions/viability.
5. Add a **single-owner** SUMO 1.20/CARLA 0.9.16 bridge smoke based on CARLA's official `run_synchronization.py`; record frame/time increments and unmapped/mapped vehicle counts (observed counts, not actor-identity/geometry verification). Stop and report errors for mismatched or competing clocks. Simulator event issue/receipt and sensor production/delivery are explicitly NOT YET RECORDED.
6. Run focused tests, the historical full Python suite and native CTest, real bounded dataset gates and simulator smoke. All PASS is a *scoped contract smoke success*, not task-winning or continuous-time formal certification.

## 2. Mandatory ordering

Goal and audited semantics -> code -> synthetic tests -> real train+validation sampling -> independent failed-case analysis -> co-sim smoke -> report -> next iteration. Data/simulator missing means **SKIP**, schema/clock contract violated means **ERROR**, never fabricated PASS.

## 3. Implementation slices

| Slice | Implemented | Still required to satisfy revised paper |
|---|---|---|
| 6B repair | AV2 official enum, focal/AV separation, explicit future scrubbing, per-track geometry, record hash | Verify against target server's AV2 Parquet + map JSON; repeat 6B gate |
| 6C-I real data/forecast | independent bounded train/val readers, leakage-free CV, ADE/FDE, source provenance | Exhaustive split overlap audit, training batches/normalizers learned on train only, reliable map geometry, calibrated joint decoder |
| 6C-II RuleNet | ranking-only score API with required source | Trained rule features + causal graph + option-aware joint behavior model; full protocol branch support remains separate |
| 6C-III co-sim | official bridge smoke, frame/time ledger, explicit TLS owner | Actual paired interventions, sensor production/delivery, protocol event clocks, matched CARLA/SUMO actor-map/footprint calibration |
| Revised task-winning core | Explicitly NOT implemented here | Terminal tail certificate, joint-support rank, task-conditioned SCO, CCG/ICG, dynamic temporal controllability and verifier links |

## 4. Hard guardrails

- Input prediction is `UnifiedScene.online_view()`. All future ground truth remains in a separate evaluation scene; public metadata must not disclose hidden dynamic map state transitions or target future states.
- WOMD/AV2 logged motion only identifies `P(X_future | observed history, executed action)`; do NOT call it a ground-truth response to arbitrary counterfactual ego candidates.
- Geometric occupancy is derived from footprints and map polygons; segment centerlines and geometric boundary samples are not equivalent.
- AV2 does not supply the prediction ego by `focal_track_id`, and both datasets represent objects by bounding-box centers. The ego kinematic model is rear-axle-centered; a physically calibrated, *ego-specific* transform is necessary before physical control. A global scene-wide rear-axle transform must not process pedestrians/cyclists.
- A failed candidate or numerical UNKNOWN is not a negative task viability label. Similarly sampled-time collision checks are not continuous-time proofs.
- Co-sim time ledger is neither the paper's four-clock protocol ledger nor proof of online nonanticipativity.

## 5. Target-server prerequisites

- Native `rampd_interval` built against **official** MPFR/GMP development headers and native CTest manifest.
- WOMD Scenario `waymo_open_dataset.protos.scenario_pb2` and TensorFlow TFRecord support (the existing server WOMD 6B result demonstrates these were present).
- AV2: `pandas` **plus** `pyarrow` or `fastparquet`. Installing `av2` itself is optional for this reader. Compatible map JSON alongside each `scenario_*.parquet`.
- CARLA Python API 0.9.16, CARLA 0.9.16 headless server and matching CARLA `Co-Simulation/Sumo` bridge, SUMO 1.20 binary/tools and SUMO_HOME, a matching Town04 `.sumocfg` and no competing synchronous tick client.
- `scripts/validate_phase6c.sh` writes the status JSON and zip even on incomplete gates; `exit 2` means no full scoped smoke acceptance. `RUN_FULL_REGRESSION=0` is diagnostic only and cannot produce PASS.
