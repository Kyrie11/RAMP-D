# Paper-to-code implementation map

| Paper concept | Code location | Current status / boundary |
|---|---|---|
| Six-state kinematic bicycle dynamics, Appendix Physical Recoverability | `python/rampd_core/model.py`, `cpp/src/interval_bicycle.cpp` | Implemented with explicit additive derivative-disturbance box interface; calibration envelope still required |
| Outward-rounded interval extension | `cpp/src/interval.cpp` | MPFR directed rounding, 192-bit internal precision, binary64 outward endpoints |
| Picard inclusion and endpoint enclosure, Eq. (picard-tube) | `cpp/src/picard.cpp`, `python/rampd_core/reachability.py` | Implemented; `VALIDATED` is a dynamics enclosure only |
| Failure-driven bisection and UNKNOWN | `python/rampd_core/reachability.py` | Implemented in Phase 1B |
| Adaptive local tube width control | `python/rampd_core/reachability.py` | Phase 1C; exact rational coordinate widths, per-axis SI caps, width-triggered bisection and independent split budget |
| Tube witness and replay | `python/rampd_core/certificate.py` | Schema v2 exact width metadata; schema v1 backward replay; same arithmetic backend used by replay |
| Fixed/adaptive resolution benchmark | `scripts/benchmark_phase1c.py` | Synthetic numerical benchmark only; not AV2/WOMD/SUMO/CARLA experiment |
| Continuous swept vehicle footprint | planned Phase 1D | Not implemented |
| Finite joint information-support cells and S-infinity | planned Phase 2 | Not implemented |
| Public backup policy graph | planned Phase 3 | Not implemented |
| Protocol product and full-support verifier | planned Phase 4 | Not implemented |
| CEGAR | planned Phase 5 | Not implemented |
| AV2/WOMD training and SUMO/CARLA closed-loop experiments | planned Phase 6 | Not implemented |

The paper's `CERTIFIED` verifier result is not produced by any Phase 1A-1C
module. No current result authorizes physical control execution.
