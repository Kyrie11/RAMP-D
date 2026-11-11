# RAMP-D development roadmap

| Phase | Deliverable | Status |
|---|---|---|
| 0 | Project skeleton, contracts, build/test harness | complete |
| 1A | MPFR interval arithmetic and six-state bicycle interval RHS | server accepted |
| 1B | Picard validated integration and replayable inclusion witness | server accepted |
| 1C | Width metrics, adaptive subdivision, budgeted UNKNOWN | server accepted |
| 1D | Swept rectangular footprint and fixed-axis strict separation | server accepted |
| 2 | Finite joint belief-support cells and robust information-state fixed point | implemented; target-server acceptance pending |
| 3 | Public common backup controller synthesis and executable policy graph | next |
| 4 | Protocol automata, full-support tube/resource verifier, CERTIFIED/COUNTEREXAMPLE/UNKNOWN | pending |
| 5 | Concrete/spurious counterexample handling and CEGAR | pending |
| 6 | AV2/WOMD learning, SUMO/CARLA headless co-simulation, closed-loop experiments | pending |

Phase 2 does not require datasets or simulators. Phase 3 will initially use
synthetic bounded dynamics and validated tubes. Phase 4 will need the protocol
specification and complete resource/agent transition contracts. Phase 6 is the
first phase that requires AV2/WOMD and the SUMO/CARLA headless co-simulation
bridge.
