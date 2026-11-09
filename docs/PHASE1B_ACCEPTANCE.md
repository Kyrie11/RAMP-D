# Phase 1B acceptance record

## Scope and status

Implemented: hardened Phase 1A interval/model layer, Picard substep inclusion,
endpoint boxes, bounded retry/inflation, failure-driven time bisection, exact
binary64-duration bookkeeping, UNKNOWN semantics, JSON witnesses and replay.

Local software tests passed. **Target-server official-header build and Python
3.10 acceptance remain pending.** This is not a full-support safety certificate.

## Actual local environment

Linux x86_64; GCC 14.2.0; CMake/CTest 3.31.6; Python 3.13.5; real MPFR runtime
4.2.2. See reports/local/final/environment.json for complete recorded versions,
linked-library paths and source/library hashes.

Important limitation: official mpfr.h was unavailable in the local container.
A temporary declaration-only subset of the public MPFR API was used to link
against the actual installed runtime. It is not included in this release.
The source distribution requires the official development header on the target.
Local summary status is deliberately BOOTSTRAP_TEST_PASS_REQUIRES_OFFICIAL_HEADERS,
not LOCAL_ACCEPTANCE_PASS. Therefore these local results do not establish a
standard official-header toolchain build or Python 3.10 execution.

## Completed local checks

| Check | Actual result |
|---|---|
| Release native compilation | Passed; no warnings in final build log |
| Native CTest | 3/3 passed |
| Python pytest | 71 passed; 0 failed; 0 skipped |
| AddressSanitizer + UndefinedBehaviorSanitizer native tests | 3/3 passed |
| Independent search-path witness replay | Passed for complete demo tube |
| Seeded numerical RK4 falsification | 64 rollouts; 20,480 state-vector checks; 0 misses |
| Deliberately disabled native tests | Acceptance correctly rejected zero tests |
| Rebuilt old Phase 1A shared library loaded by new wrapper | Correctly rejected as stale ABI |
| Python source compile check | Passed |

The RK4 result is an empirical containment audit only. It is not an experiment
with AV2/WOMD/CARLA/SUMO and is not a proof. False-safe count is intentionally
null/not applicable because no safety verifier has been implemented.

## Test coverage

- Four interval operations versus exact Fraction corner values: 300 random
  interval pairs per operation.
- Decimal literals, subnormal numbers, overflow, zero divisors, invalid input.
- sin/cos critical points and large arguments; tan poles and multiple branches.
- High-precision friction checks including the previously premature mu*g product.
- Unchanged hardware rounding mode and threaded numerical determinism.
- Exact-rational straight/constant-jerk solutions at substep interior samples.
- High-precision circular motion solutions for positive and negative steering.
- Interval initial/control boxes and time-varying bounded derivative disturbances.
- Iteration, depth, minimum-step, wall-clock, attempt and accepted-step limits.
- Domain crossing, partial-prefix handling, exact time continuity and no tail gaps.
- Serialized witness corruption, endpoint linkage and unsupported safety claims.

## Target acceptance gates

1. Official MPFR/GMP development packages are used to rebuild this source.
2. Active interpreter is the intended Python 3.10 environment.
3. CTest discovers interval_cpp, picard_cpp and abi_cpp and all three pass.
4. All 71 Python tests pass without skipped tests.
5. Demo status is VALIDATED, exact horizon is 1, analytic px=8 is enclosed,
   and the saved witness replays successfully.
6. The seeded empirical audit has zero containment misses.
7. acceptance_summary.json reports LOCAL_ACCEPTANCE_PASS and
   official_mpfr_headers_used=true; save environment.json and validation.log.

The script enforces these software gates except the choice of exactly Python
3.10 (it accepts >=3.10 and records the actual interpreter). The user's intended
Python 3.10 choice must be checked in environment.json.

## Progress

Phase 1A fixes: implemented, locally tested, target regression pending.
Phase 1B: implemented, locally tested, target acceptance pending.
Phase 1C: not implemented beyond the basic failure-bisection required by 1B.
Phase 1D, belief supports, invariant synthesis, backup policies, full-support
verification and CEGAR: not implemented in this release.

## Evidence paths

- reports/local/final/validation.log
- reports/local/final/ctest_discovery.log and ctest.log
- reports/local/final/pytest.log and pytest.xml
- reports/local/final/demo_certificate.json and replay.log
- reports/local/final/empirical_audit.json
- reports/local/final/acceptance_summary.json and environment.json
- reports/local/sanitizer_tests.log
- reports/local/no_tests_guard_result.log
- reports/local/stale_library_guard.log

Do not relabel these files as results from the user's server.
