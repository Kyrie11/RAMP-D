# RAMP-D development roadmap (preserved sequence)

This project follows the agreed dependency order; later modules must not be
implemented as substitutes for unaccepted earlier numerical modules.

| Order | Phase | Scope | Acceptance artifact |
|---:|---|---|---|
| 0 | Engineering foundation | Project skeleton, model/state contracts, build/test infrastructure | Reproducible environment report |
| 1 | Phase 1A | MPFR-backed interval arithmetic and six-state bicycle vector field | Arithmetic/model unit tests |
| 2 | Phase 1B | Picard validated continuous-time integration and endpoint enclosure | Complete-horizon inclusion witnesses and replay |
| 3 | Phase 1C | Width-driven adaptive subdivision, budgets, fail-closed UNKNOWN | Fixed/coarse/fine/adaptive benchmark and replay |
| 4 | Phase 1D | Swept oriented footprint outer enclosure and conservative continuous pairwise separation | Geometric containment audit and separation witnesses |
| 5 | Phase 2 | Finite joint belief-support cells and certified inner approximation of S_infinity | Fixed-point/information-support tests |
| 6 | Phase 3 | Public backup-controller synthesis and executable policy graph | Common-control and backup-transition tests |
| 7 | Phase 4 | Protocol product and full-support verifier | CERTIFIED / COUNTEREXAMPLE / UNKNOWN tests |
| 8 | Phase 5 | Concrete/spurious counterexample handling and CEGAR | Refinement correctness and termination tests |
| 9 | Phase 6 | AV2/WOMD training, SUMO/CARLA controlled closed-loop experiments | Reproducible experimental tables and audits |

Phase 1A-1D are mathematical/physical infrastructure. Phase 2 must consume
sound state/footprint enclosures; Phase 3 must consume validated tubes and
information-state semantics; Phase 4 must be independent of learned likelihoods;
Phase 5 must refine only validated concrete/spurious cases; Phase 6 evaluates
the completed system. No dataset or simulator is required before Phase 6,
although synthetic geometry tests are used in Phase 1D.

For Phase 2, the uploaded paper already cites Brown et al. (2023) and Schäfer
et al. (2023). Uploading those two full papers before implementing the fixed
point would help cross-check the invariant-set numerical assumptions. They are
not required for Phase 1D.
