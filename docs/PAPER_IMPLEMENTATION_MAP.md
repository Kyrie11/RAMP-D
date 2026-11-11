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
| Public backup policy graph and constant common controller | `python/rampd_core/controller.py`, `scripts/demo_phase3.py` | Phase 3; compiles retained Phase 2 witnesses, routes only by realized observations, `PUBLIC_CONTROLLER_SYNTHESIS_ONLY`, `certified=false`; affine `K_B` extension deferred until interval image/tube verification |
| Protocol product and full-support verifier | planned Phase 4 | Not implemented |
| CEGAR | planned Phase 5 | Not implemented |
| AV2/WOMD training and SUMO/CARLA closed-loop experiments | planned Phase 6 | Not implemented |

The paper's full planner `CERTIFIED` result is not produced by any Phase 1A-1D
module. No current result authorizes physical control execution.
