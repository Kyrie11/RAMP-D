# Canonical phase status against the uploaded latest TeX (2026-11-17)

The latest manuscript hash is recorded in `manuscript/SOURCE_MANUSCRIPT.sha256`. The historical per-phase docs record decisions and previous results; this page is the current **non-overstating** reconciliation. This is a *code/design and uploaded-log audit*, not a fresh target-server numerical proof audit.

| Phase | Implemented calculation / interface | Status against latest definition | Still required for rigorous acceptance |
|---|---|---|---|
| 0 / 1A | 6-state rear-axle bicycle, `(j, omega_delta)` control, MPFR outward interval arithmetic and friction enclosure | Matching model and numerical intent, subject to proof environment assumptions | New server native CTest 3/3, compiler/MPFR metadata, vehicle calibration and bounded disturbance `G W` coverage |
| 1B | Picard self-inclusion for complete dynamic substep, validated endpoint, UNKNOWN budget | Algorithmically matches TeX's outer-tube principle; not yet an independent formal proof of all library rounding paths | Replay on server + independent MPFR oracle; exact rational SC-step vs dyadic binary64 step mismatch |
| 1C | Adaptive width/failure subdivision and non-certifying UNKNOWN | Consistent, but tighter boxes are not mathematically guaranteed for every split | Stress test signed-zero, near singular steering, max-depth and lossless time partitions |
| 1D | Continuous swept rectangle with rear-axle center offset and separation witness | Matching `F_i(x)` if calibrated, not automatically calibrated for AV2/WOMD actor classes | Actor-specific width/length/offset and complete polygon/resource collision checks |
| 2 | Finite joint belief-support cells and safety invariant inner fixed point | **Safety-only** under replayed finite model, not exact `S_infty` and not `W_h^SC` | Verified physical transitions and full observation/hidden-mode coverage for each cell |
| 3 | Public feedback backup graph and execution | Separate finite safety fallback. Safe stopping does not imply legal arrival | Robust invariant certificate/conformance, reconnect to task if promised |
| 4 | Protocol automaton, four-clock partial relations, full-support three-valued verifier | Correct structural separation of hidden change from public receipt/local observation; full concrete coverage is caller contract | Explicit interval event splits, true sensors, calibrated controller authority and complete support replayers |
| 5 | CEGAR structural refiner and candidate-counterexample categorization | Correct UNKNOWN vs confirmed candidate counterexample distinction, incomplete real concretization | Real tube-level concrete traces and refinement proof that no observation branch is fabricated |
| 6A | Dataset files/split/source audit | Preparatory contract checks | Actual exhaustive disjoint group splits for overlapping WOMD windows |
| 6B | WOMD Scenario and AV2-MF adapters; ID/index, focal/AV, category/valid/time masks; source+record+scenario hashes | Current WOMD sampled train+val PASS. AV2 sampled train/val SKIP; no joint dataset pass | Install `pyarrow`, inspect realistic AV2 geometry/map pairs and future masks; official metric implementation separate |
| 6C-A/A2 | Predictors and time-event/map schema, online-vs-label separation, soft RuleNet ranking | CV is a diagnostic, not a trained RuleNet or conditional causal forecasting model | Training/calibration, real event/observation clock labels, model consistency and sim bridge |
| 6C-A3/A4 | Finite goal-conditioned `W_h^SC`, rank decrease, exact rational worst-time budget, support hash and independent structural audit | Correct conditional finite algorithm in tests, **not full-support certified** | Physical/protocol replay of proof providers and verified all-history task tail; trusted callback True inadequate |
| 6C-A5/1 (this release) | Exact finite task-tail AND/OR, protocol enumerated outcome/observation gate, native physical tube replay on narrow synthetic world; robust CTest gate | Implemented and 10 dependency-free tests pass locally. MPFR integrated tests **not run here** | Server native/MPFR gate; A5/2 verified terminal physical tail and broader protocol/actor/resource coverage |
| 6C remaining | CCG/ICG/controllable scheduling, calibrated RuleNet, dynamic-causal modes, paired experiments | **Not implemented** | Build only after proof providers and label provenance are verified |

## Cross-cutting corrections

1. The manuscript's `S_infty` and `W_h^SC` differ. `W_0^SC` includes only bounded **accepted-task** tails. Rank must strictly decrease on every nonterminal observation; replans must inherit support/time and context.
2. `ICG(pi)=T_sep,+ (pi)-D_defer(pi)` is meaningful **only** if both terms use the same fixed public prefix, complete possible observations and robust times. An exact numeric value is not available in current code.
3. Binary64 `0.1` is not the exact rational `1/10`. A5/1 currently requires binary-representable fraction steps so physical replay and SC clock describe the same instant. No floating tolerance may change a certified deadline.
4. WOMD/AV2 bounding-box center states are not automatically the rear-axle states required by the ego bicycle ODE. Mixed actor geometry may not be forced into a single vehicle reference.
5. A validated outer tube proves a **superset** of reachable motion; its overlap with a bad set is UNKNOWN unless a concrete violating trajectory is separately validated. Do not use an outer tube as an inner viability set.
6. `L_viability` negative requires a complete finite policy-class oracle, not a candidate failure; proof-artifact labels and simulation-domain labels retain explicit provenance.
7. `CERTIFIED`/winning-set claims are relative to an explicitly declared uncertainty model and envelope: failing model conformance invalidates their applicability, even when arithmetic is correct.
