# Paper-to-code implementation map

| Paper concept | Code location | Current status / boundary |
|---|---|---|
| Six-state kinematic bicycle dynamics, Appendix Physical Recoverability | `python/rampd_core/model.py`, `cpp/src/interval_bicycle.cpp` | Implemented with explicit additive derivative-disturbance box interface; calibration envelope still required |
| Outward-rounded interval extension | `cpp/src/interval.cpp` | MPFR directed rounding, 192-bit internal precision, binary64 outward endpoints; ABI 3 adds interval sqrt |
| Picard inclusion and endpoint enclosure, Eq. (picard-tube) | `cpp/src/picard.cpp`, `python/rampd_core/reachability.py` | Implemented; `VALIDATED` is a dynamics enclosure only |
| Failure-driven bisection and UNKNOWN | `python/rampd_core/reachability.py` | Implemented in Phase 1B |
| Adaptive local tube width control | `python/rampd_core/reachability.py` | Phase 1C; exact rational coordinate widths, per-axis SI caps, width-triggered bisection |
| Tube witness and replay | `python/rampd_core/certificate.py` | Dynamics schema v2 exact width metadata; schema v1 backward replay |
| Swept oriented rectangular footprint | `python/rampd_core/footprint.py` | Phase 1D; outer support-projection enclosure of each complete state tube; explicit body-center offset |
| Continuous pairwise separation | `python/rampd_core/footprint.py` | Phase 1D; sufficient fixed-axis projection gap, metric lower bound, replay; unresolved is UNKNOWN |
| Different adaptive segment schedules | `python/rampd_core/footprint.py` | Exact common temporal refinement; reuse full source-segment tubes on overlap subintervals |
| Fixed/adaptive resolution benchmark | `scripts/benchmark_phase1c.py` | Synthetic numerical benchmark only |
| Swept-footprint axis benchmark and high-precision audit | `scripts/benchmark_phase1d.py`, `scripts/audit_phase1d.py` | Synthetic geometry microbenchmark and falsification audit only |
| Rear-axle reference convention and explicit body-centre offset | `python/rampd_core/vehicle.py`, `python/rampd_core/footprint.py`, `AnonymousSubmission2027_Phase2.tex` | Rear-axle convention selected; CommonRoad BMW 320i nominal profile; CG-as-box-centre is explicitly a proxy requiring calibration |
| Finite joint information-support cells | `python/rampd_core/belief.py` | Phase 2; union of continuous boxes and discrete protocol/resource/agent modes; one cell is one complete information support |
| Robust information-state predecessor and finite fixed point | `python/rampd_core/invariant.py` | Phase 2; common control per belief cell, posterior aggregation by observation, conservative cell coverage, fail-closed evidence callback |
| Support-box refinement preserving observation equivalence | `python/rampd_core/refinement.py` | Phase 2; split does not create a new policy node and invalidates stale action evidence |
| Finite invariant candidate certificate and replay | `python/rampd_core/invariant.py`, `scripts/replay_invariant_certificate.py` | Phase 2; explicitly `S_in_candidate`, `FINITE_ABSTRACTION_ONLY`, `certified=false` |
| Public sampled feedback and finite bias/gain synthesis | `control.py`, `backup.py` | Phase 3; finite search, MPFR input images, local static-scene hard checks; not global optimization |
| Analytic integrator-chain tightening | `analytic_bounds.py` | Sound intersection with Picard; exact quadratic velocity extrema, no speed clipping |
| Context-bound transition evidence | `invariant.py`, `backup.py` | Full support/action/law/contract/transition binding and independent numerical replay |
| Executable closed public backup graph | `backup_graph.py` | Phase 3; observation-only children, fixed-point closure, contract and execution guards |
| Protocol product and full-support verifier | `protocol.py`, `resources.py`, `agents.py`, `observations.py`, `full_verifier.py` | Phase 4 first explicit finite-support implementation; synthetic contracts only, real-scene integration pending |
| CEGAR | `python/rampd_core/cegar.py`, `scripts/validate_phase5.sh` | Phase 5 orchestration implemented locally; target-server gate pending; real-scene integration remains Phase 6 |
| WOMD Scenario / AV2 Motion train+validation adapters | `record_adapters.py`, `evaluate_phase6c.py` | Phase 6B repairs and bounded Phase6C gate; original WOMD real validation PASS (3), AV2 real validation SKIP, train unverified |
| Forecast online prefix + baseline ADE/FDE | `scene_schema.py`, `phase6c.py` | Phase 6C untrained constant-velocity diagnostic; no learned joint conditional decoder |
| RuleNet soft ranking | `phase6c.py` | Score-combination API only; NOT trained RuleNet, no support narrowing |
| SUMO/CARLA sync smoke | `clock_ledger.py`, `smoke_phase6c_cosim.py` | Synthetic ledger tests pass; target simulator required; protocol four clocks not observed |
| Terminal task-winning certificate and persistent rank | latest TeX Appendix Verification | MISSING: safety invariant and backup graph are not task-reaching terminals |
| ICG same-prefix guaranteed observation separation vs decision-deferral | latest TeX CCG appendix | MISSING: cannot infer from mean delay |
| Task-conditioned SCO / CCG / dynamic scheduling and continuous policy optimization | latest TeX Planning Method | MISSING: recovery candidates are not task-certified SCOs |
| Eight supervised losses | latest TeX Appendix Network | Only logged-action motion baseline evaluated; see PHASE6C_MATHEMATICAL_AUDIT.md for sources/masks |

The paper's full planner `CERTIFIED` result is not produced by any Phase 1A-1D
module. No current result authorizes physical control execution.

Phase 3 exported graphs retain `full_support_certified=false`; Phase 4 synthetic verifier results retain the same real-traffic boundary. Physical execution in a real traffic scene still requires complete protocol/observation contracts and calibration. Current per-template fixtures are local one-step recovery objectives; only the nominal brake/hold fixture is a complete closed invariant graph.
