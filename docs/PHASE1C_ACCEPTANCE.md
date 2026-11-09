# Phase 1C acceptance record

## Status

Implemented in source; local bootstrap tests and benchmark passed. Target-server
acceptance on the user's Python 3.10 / GCC 9.4 / MPFR 4.0.2 environment is
pending. Phase 1B target-server acceptance is recorded separately and passed.

## Phase 1C implementation

- Exact rational widths of binary64 interval endpoints.
- Six SI-coordinate local tube-width caps.
- Width-triggered bisection after successful Picard inclusion.
- Separate width split budget and fail-closed UNKNOWN reasons.
- Per-segment exact width metadata and replay-enforced cap policy.
- Backward replay support for Phase 1B schema v1 certificates.
- Fixed coarse / fixed fine / adaptive width benchmark.

## Local test environment and limitation

The available local container has Python 3.13.5 and MPFR runtime 4.2.2 but no
official MPFR development header. For local bootstrap verification only, the
unchanged native core was linked against the real MPFR runtime using a temporary
public-API declaration header outside this source release. This is not an
official-header build and is not represented as target acceptance. The user's
server has already demonstrated an official-header MPFR 4.0.2 build in Phase
1B; Phase 1C must be rebuilt there from this release.

## Local results

| Check | Result |
|---|---:|
| Python regression suite | 81 passed, 0 failed, 0 skipped |
| Native CTest | 3/3 passed in bootstrap build |
| Phase 1B demo witness replay | passed |
| Phase 1B empirical RK4 audit | 64 rollouts / 20,480 state vectors / 0 misses |
| Phase 1C benchmark methods | 3/3 VALIDATED and replayed |
| Width-triggered subdivisions in benchmark | 3 |
| Adaptive accepted maximum width ratio | 0.9886314837 |

## Synthetic benchmark snapshot

One synthetic case, 0.8 s horizon, initial heading `[-0.03,0.03]` rad and
speed `[7.9,8.1]` m/s, zero control and zero derivative disturbance:

| Method | Accepted steps | Width splits | Max local x span (m) | Median time (ms, local) |
|---|---:|---:|---:|---:|
| Fixed coarse, 0.4 s | 2 | 0 | 4.206239 | 0.444 |
| Fixed fine, 0.025 s | 32 | 0 | 0.532401 | 8.203 |
| Adaptive cap, max initial step 0.4 s | 5 | 3 | 2.174989 | 1.708 |

The adaptive case reduces the maximum local x span by about 48.3% relative to
the coarse schedule, while using 5 rather than 32 accepted segments. The fixed
fine schedule gives a narrower x span; adaptive is an explicit middle point in
the resolution/cost tradeoff. These timing numbers are from the local container
and are not target-server performance claims.

## Failure cases covered

- Initial support wider than a cap: immediate UNKNOWN, zero Picard attempts.
- Width split budget exhausted: UNKNOWN, no terminal endpoint.
- Certificate width metadata altered: replay rejects.
- Width policy metadata forged to a cap smaller than the witnessed tube: replay
  recomputes and rejects.
- No width policy configured: Phase 1B segment schedule behavior is preserved.
- A validated-but-too-wide candidate is not silently appended; its children
  must be recomputed and validated.

## Target server acceptance gates

1. Official MPFR/GMP headers used; Python 3.10 environment selected.
2. CTest discovers and passes `interval_cpp`, `picard_cpp`, `abi_cpp`.
3. At least 81 Python tests pass, with no skips/errors/failures.
4. Phase 1B demonstration status is VALIDATED; full horizon and replay pass.
5. Empirical RK4 audit reports zero misses (falsification only).
6. Benchmark has all three methods VALIDATED, all witnesses replayed, and
   adaptive width-triggered subdivision count greater than zero.
7. Adaptive accepted width ratio is at most 1.0.
8. `acceptance_summary.json` says `LOCAL_ACCEPTANCE_PASS` and
   `official_mpfr_headers_used=true`.

## Scope boundary

No AV2/WOMD data, SUMO, CARLA, GPU, vehicle controller, swept footprint,
collision verifier, belief-support abstraction, invariant set or safety
certificate is implemented in Phase 1C.
