# Paper-to-code mapping

| Paper object | Implementation | Status |
|---|---|---|
| eq:bicycle, six-state vector field | cpp/src/interval.cpp: rhs | Implemented |
| eq:friction | cpp/src/interval.cpp: friction | Implemented as a separate predicate |
| eq:picard-tube, interval extension | MPFR interval operations | Implemented |
| alg:tube candidate enclosure / inclusion / endpoint | cpp/src/picard.cpp | Implemented, strict subset sufficient test |
| alg:tube retry and half-step composition | reachability.py | Implemented with finite budgets |
| alg:tube inclusion witness | certificate.py | Implemented and replayed |
| alg:tube swept-footprint map | None | Deferred to Phase 1D |
| State/input calibration and actual W | Explicit interface only | Not supplied/identified |
| Other-agent reachable models | None | Deferred |
| Protocol event-time branching | None | Deferred |
| S_in / S_infinity and backup graph | None | Deferred |
| Full-support CERTIFIED / COUNTEREXAMPLE / UNKNOWN | None | Deferred; do not confuse with tube status |
| Empirical tube coverage audit | scripts/audit_phase1b.py | Synthetic numerical audit only |
| Paper closed-loop experiment tables | None | Not filled by these tests |

This is a partial implementation of Algorithm 3 by design: its geometric
footprint operation belongs to a later agreed phase. No source-paper claim has
been silently replaced by sample-based validation or by optimizer feasibility.
