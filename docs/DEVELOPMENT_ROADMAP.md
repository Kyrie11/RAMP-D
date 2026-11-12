# RAMP-D development roadmap

| Phase | Deliverable | Status |
|---|---|---|
| 0 | Project skeleton, contracts, build/test harness | complete |
| 1A | MPFR interval arithmetic and six-state bicycle interval RHS | server accepted |
| 1B | Picard validated integration and replayable inclusion witness | server accepted |
| 1C | Width metrics, adaptive subdivision, budgeted UNKNOWN | server accepted |
| 1D | Swept rectangular footprint and fixed-axis strict separation | server accepted |
| 2 | Finite joint belief-support cells and robust information-state fixed point | uploaded server baseline accepted; evidence binding repaired |
| 3 | Public common backup controller synthesis and executable policy graph | implemented and regression-tested in local physical scope; target server report available |
| 4 | Protocol automata, full-support tube/resource verifier, CERTIFIED/COUNTEREXAMPLE/UNKNOWN | implemented first explicit synthetic-support verifier; real scene integration pending |
| 5 | Concrete/spurious counterexample handling and CEGAR | server Python regression passed; native CTest gate hardened |
| 6A | Read-only AV2/WOMD manifest audit, unified scene contract, future-leakage guard | implemented and locally tested |
| 6B | Validation record parsers, center/reference conversion, four-clock injection | implemented locally; server sample gate pending |
| 6C | Prediction proposals, RuleNet soft ranking, SUMO/CARLA headless closed loop | pending |

Phase 2 does not require datasets or simulators. Phase 3 uses
synthetic bounded dynamics and validated tubes. Phase 4 now provides versioned protocol/resource/agent/observation contracts and a conservative verifier. Phase 5 adds a version-bound CEGAR refinement layer over those finite synthetic fixtures; complete real-scene contracts are still required before dataset integration. Phase 6 is the
Phase 6A reads only directory metadata and requires no simulator. 6B now has
dependency-free synthetic regression plus bounded real-record readers; the
server sample gate is still required before claiming `real_scene_verified`.
6C requires the
SUMO/CARLA headless co-simulation bridge.
