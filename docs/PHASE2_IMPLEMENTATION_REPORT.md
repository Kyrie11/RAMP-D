# Phase 2 implementation report

## Delivered

Phase 2 adds the finite information-state abstraction and fixed-point engine
while preserving the Phase 1A-1D MPFR/C++ backend and all previous tests.
The implementation is deliberately separated from the Phase 3 controller
synthesis and Phase 4 full-support verifier.

## Mathematical semantics

For each belief cell `B`, the engine searches a finite list of candidate
common controls. A candidate is admissible only if it has one transition for
every source atom, the external evidence verifier replays every source-atom
transition, and all observation-conditioned posterior supports are contained
in one cell of the current candidate invariant family. The predecessor
iteration removes all failing cells simultaneously until a no-removal round.

This is the finite game semantics of the paper's `Pre_info` iteration. The
algorithm terminates because the retained family is finite and monotonically
decreasing. It is not the continuous maximal-invariant theorem of either
reference paper.

## Why the two uploaded references are not copied verbatim

- Brown et al. (CDC 2023) address discrete-time control-affine systems and
  interval/polytope inclusion. Their Lipschitz and discrete-time assumptions
  are not a direct proof for the continuous-time hybrid belief-space RAMP-D
  problem.
- Schäfer et al. (IEEE TAC 2024) address perturbed nonlinear sampled-data
  systems with zonotopes and a separate verification step. Their synthesis
  algorithm is not a ready-made partially observed information-state solver.

Their reusable ideas are set-valued overapproximation, conservative
predecessor iteration, subdivision of unresolved sets, and strict separation
between candidate synthesis and verification. Detailed mapping is in
`PHASE2_REFERENCE_ANALYSIS.md`.

## Vehicle convention added to the paper

The ODE's position is fixed at the rear-axle centre. Footprint geometry is
translated by the rear-axle-to-body-centre offset. The nominal CommonRoad BMW
320i profile uses length 4.508 m, width 1.610 m, wheelbase 2.5789128 m, and a
nominal 1.4227170936 m rear-axle-to-body-centre offset by treating the CG as a
proxy for the rectangle centre. This last assumption must be replaced by
measured CARLA bounding-box geometry before any physical safety claim.
Friction is a scenario parameter and is not embedded in the chassis profile.

Updated paper and bibliography copies:
- `AnonymousSubmission2027_Phase2.tex`
- `aaai2027_Phase2.bib`

## Local verification

- 3/3 C++ CTest tests passed.
- 129/129 Python tests passed, no skips.
- 3/3 AddressSanitizer + UBSan native tests passed.
- Phase 1B dynamics certificate replay passed.
- Phase 1C width regression: all three strategies validated and replayed.
- Phase 1D geometry regression: AABB overlap remains UNKNOWN; oriented axes
  prove separation; all witnesses replay; 40,000 high-precision projection
  audit checks with zero sampled misses.
- Phase 2 finite demo retains `A` and `L`; candidate certificate replay passes.
- Phase 2 finite game microbenchmark: 50, 100, 250, 500, 1,000, and 2,000
  cells all converge on the deterministic self-invariant fixtures.

The local environment lacks the official MPFR development header, so this
remains a bootstrap test build with a temporary declaration-only header and
the real MPFR runtime. It is not server acceptance. The target server must
rebuild with its official MPFR 4.0.2 development package.

## Explicit non-claims

The Phase 2 result is not yet the paper's concrete `S_in` certificate. The
current demo evidence verifier is synthetic. Full concrete evidence replay,
protocol coverage, continuous agent/ego tubes, resource monitor transitions,
and all possible observation branches must be supplied by Phase 4. Phase 3
must synthesize the actual public backup feedback law.
