# Phase 1D acceptance record

## Status

Implemented in source. Local bootstrap acceptance passed. Target-server
acceptance on the user's official MPFR 4.0.2 / GCC 9.4 / Python 3.10
installation is pending a clean ABI-3 rebuild and report.

## Implemented

- ABI-3 MPFR-directed interval square root for a certified axis norm.
- Fixed-geometry oriented rectangle with explicit state-reference-to-body-center
  offset.
- MPFR interval support-projection enclosure for an entire state tube.
- AABB bounds from world x/y support directions.
- Fixed-axis strict projection-gap test with positive metric clearance lower
  bound; no `COLLISION` status is exposed.
- Candidate axes from world axes and midpoint headings of both vehicles.
- Exact rational time interval checks and common temporal refinement for
  different adaptive segment partitions.
- High-level API rejects incomplete/UNKNOWN dynamics tube results, checks exact
  horizon/endpoint linkage, and replays both source Picard witnesses.
- Versioned fixed-axis separation witness and replay.
- Synthetic AABB/oriented-axis benchmark and 100-digit corner-projection
  falsification audit.

## Local environment limitation

The local execution container has MPFR runtime 4.2.2 but no official MPFR
header/development symlink. Local bootstrap compilation used the existing
external temporary public-API declaration header and linked the real runtime
library explicitly. This header is not included in the delivered source.
Consequently local results are marked
`BOOTSTRAP_TEST_PASS_REQUIRES_OFFICIAL_HEADERS`; the user's server must build
with its official `libmpfr-dev` 4.0.2 header. MPFR 4.0.2 provides `mpfr_sqrt`;
no version upgrade is expected to be necessary.

## Local results

| Check | Result |
|---|---:|
| Release C++ compile | passed |
| CTest | 3/3 passed |
| Python suite | 109 passed, 0 failed, 0 skipped |
| ASan + UBSan native tests | 3/3 passed |
| Phase 1B dynamics demo/replay | passed; 32 segments |
| Phase 1C width benchmark regression | 3/3 methods VALIDATED and replayed; 3 width splits |
| Phase 1D geometry benchmark | AABB-only UNKNOWN; oriented and dense axes SEPARATED; both witnesses replayed |
| Phase 1D high-precision audit | 2,000 sampled poses x 4 corners x 5 axes = 40,000 projections; 0 misses |
| ABI guard | ABI-2 library rejected by ABI-3 Python loader |
| ZIP package | source package prepared without build artifacts |

The 40,000 checks are falsification evidence only, not a proof. The proof
argument is the interval support enclosure plus strict projection separation,
conditional on correct MPFR behavior, sound source state tubes, and calibrated
geometry.

## Synthetic benchmark

The test uses two 4.0 m x 0.2 m rectangles at 45 degrees, with center offset
1.5 m along their common lateral axis. Their AABBs overlap, but a fixed oriented
axis has a positive projection gap.

| Method | Axes | Result | Median local time | Metric lower clearance |
|---|---:|---|---:|---:|
| AABB only | 2 | UNKNOWN | 0.527 ms | n/a |
| Oriented candidate axes | 4 | SEPARATED | 1.161 ms | 1.30 m |
| Dense 16 + oriented | 20 | SEPARATED | 1.891 ms | 1.30 m |

These are local microbenchmark measurements, not vehicle experiments or
server performance claims. The AABB-only `UNKNOWN` is expected and important:
AABB overlap is not a collision finding.

## Failure cases and guards

- Exact touching: UNKNOWN, because strict positive gap is required.
- Overlapping outer projections: UNKNOWN, never COLLISION.
- Uncertain heading: may widen the footprint and lead to UNKNOWN.
- Mismatched exact time intervals: rejected; sequence API builds a common
  refinement and checks all subintervals.
- Incomplete/UNKNOWN dynamics result: rejected by high-level API.
- Numerically unrepresentable axis/projection: fail-closed UNKNOWN.
- Tampered projection, gap, clearance, or full-safety claim: replay rejects.
- Old ABI-2 dynamic library: explicitly rejected; clean ABI-3 rebuild required.

## Target server acceptance gates

1. Python 3.10 selected; GCC 9.4/CMake 3.18 accepted.
2. Official MPFR/GMP development headers used; MPFR 4.0.2 is sufficient.
3. ABI-3 library built in a fresh `build_phase1d/` directory.
4. CTest discovers and passes `interval_cpp`, `picard_cpp`, `abi_cpp`.
5. At least 109 Python tests pass with zero skips/errors/failures.
6. Phase 1B certificate replays; Phase 1C width benchmark still passes.
7. Phase 1D benchmark returns AABB-only UNKNOWN and oriented SEPARATED,
   with replayed witnesses.
8. Footprint projection audit reports zero misses.
9. Summary says `LOCAL_ACCEPTANCE_PASS` and
   `official_mpfr_headers_used=true`.

## Scope boundary

No AV2/WOMD parsing, resource polygon occupancy, road-rule checking, agent
response model, full-support collision verifier, invariant set, backup
controller, CEGAR, SUMO or CARLA integration is implemented in Phase 1D.
The body reference-point convention and real vehicle dimensions remain
calibration inputs, not inferred values.
