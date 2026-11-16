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
| 6B | Validation record parsers, center/reference conversion, four-clock injection | parser audit/fixes local; WOMD server sample PASS, AV2 SKIP pending pyarrow |
| 6C-A | History/future data split, joint-mode/observation proposals, RuleNet soft ranking, non-pruning branch order, simulator sync contracts | 47 dependency-free tests passed locally; no real data/simulator/native certification |
| 6C-A2 | WOMD/AV2 unified vector-map geometry and dynamic-signal timeline | completed local data contracts; server WOMD 1 record PASS, AV2 SKIP |
| 6C-A3 (math gate) | Phase 4/5 public API fix + finite task-winning inner family, completion rank, conditional margin lower bounds; server native gate pending | local finite Python proof-kernel tests; native pending |
| 6C-B | CARLA/SUMO bridge, single tick owner, actor/TLS mapping, sensor and four-clock alignment | pending Phase 6B full PASS and mathematical verifier gate; requires user-started simulators |
| 6C-C | Train/evaluate joint prediction and planning-guided model; closed-loop experiments | pending |

Phase 2 does not require datasets or simulators. Phase 3 uses
synthetic bounded dynamics and validated tubes. Phase 4 provides versioned
protocol/resource/agent/observation contracts and a conservative verifier.
Phase 5 adds a version-bound CEGAR refinement layer over finite synthetic
fixtures. The current audit has found finite-horizon value/CCG and silence
deadline-evidence gaps that must be closed before formal end-to-end claims.
Phase 6A reads directory metadata; 6B has bounded real-record readers and
synthetic regression, but the server AV2 gate is still SKIP until pyarrow is
installed and the samples pass.
6C-B requires the SUMO/CARLA headless co-simulation bridge. Phase 6C-A is a
pure-Python contract layer and does not start either simulator. Complete the
6C-A2 map/signal adapters and the Phase 2–5 mathematical gaps before running
closed-loop simulation.
