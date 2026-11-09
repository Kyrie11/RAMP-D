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
| Finite joint information-support cells and S-infinity | planned Phase 2 | Not implemented |
| Public backup policy graph | planned Phase 3 | Not implemented |
| Protocol product and full-support verifier | planned Phase 4 | Not implemented |
| CEGAR | planned Phase 5 | Not implemented |
| AV2/WOMD training and SUMO/CARLA closed-loop experiments | planned Phase 6 | Not implemented |

The paper's full planner `CERTIFIED` result is not produced by any Phase 1A-1D
module. No current result authorizes physical control execution.
