# Phase 1B failure and correction record

## F01 - CTest discovered zero tests on the user's server

Observed: compilation succeeded, but `ctest --test-dir build` printed the
project ROOT as its search directory and reported no tests. Uploaded CMakeLists
already contains enable_testing/add_test. Most likely cause: CTest older than
3.20 ignoring the unsupported flag, or an equivalent command/path mismatch.
The exact server version has not been supplied, so this remains a diagnosis,
not a confirmed version number.

Fix: execute CTest from inside the build tree and explicitly verify the
registered test count/names. A negative test built with tests OFF reported
Total Tests: 0; the acceptance script exited with code 1 as intended.
Evidence: reports/local/no_tests_guard_result.log.

## F02 - Phase 1A rounded mu*g before interval construction

Observed in source: `const Interval scale(mu*g)` loses the arithmetic error
of that product before the interval exists. Fix: `I(mu)*I(g)` and use interval
operations throughout the expression. Added high-precision point evaluations
and retained zero-crossing square tests.

## F03 - Transcendental backend was not suitable as an unchecked proof premise

Phase 1A relied on a Boost policy wrapping ordinary math-library functions.
Numerical sample coverage did not establish the needed directed transcendental
bounds. This release uses MPFR explicit rounding for every arithmetic endpoint,
plus a conservative critical-point enclosure for interval sin/cos/tan. No
silent fallback to the old backend is allowed. ABI version 2 rejects the
actual rebuilt Phase 1A shared library; see stale_library_guard.log.

## F04 - Uniform inflation stalled a straight-motion inclusion test

Initial implementation enlarged all dimensions on every failed retry. In a
straight-motion case with h*v=1, heading and lateral padding grew together and
the lateral component kept failing strict inclusion. The first native suite
reported 2/3 tests passed.

Fix: enlarge only failed coordinates, recomputing every field and every
inclusion relation after each update. The strict inclusion predicate and
expected analytic displacement were NOT weakened. The native regression now
passes and also checks an explicitly unresolved one-iteration call.

## F05 - A test assumed two retries were enough for a jerk propagation chain

The first Python suite reported 69 passed and 1 failed: a test incorrectly
expected a two-iteration search to become successful after bisection. The
acceleration -> velocity -> position dependency can require more search
iterations even for a very small step.

Correction: the success-after-bisection fixture now uses three iterations,
first asserts the coarse step is UNKNOWN, then verifies that refinement succeeds.
A separate regression preserves the two-iteration case as EXPECTED UNKNOWN.
This is not a relaxation of enclosure acceptance or the analytic tests.

## F06 - Local build dependency limitation, NOT silently resolved

The local container has MPFR 4.2.2 runtime and GMP headers but lacks official
MPFR development headers, and dependency download/install attempts were not
available. Local native tests used a minimal declaration-only header matching
the public MPFR APIs called by this project. No arithmetic was mocked: the
actual system libmpfr.so.6 was linked and executed.

That temporary header is outside the project and is NOT shipped. The release
CMake build requires official mpfr.h and libraries. Local build_info explicitly
marks bootstrap_public_API_declarations and the acceptance summary says
BOOTSTRAP_TEST_PASS_REQUIRES_OFFICIAL_HEADERS. The user's official-header build
is an outstanding acceptance gate; no target-server result is fabricated.

## Current unresolved engineering boundaries

Model calibration, nonzero disturbance interpretation, vehicle pose reference
and simulator/model mismatch are not supplied by the paper's equations alone.
They do not block the nominal mathematical tests, but must be resolved before
claiming physical safety. See NUMERICS_AND_SCOPE.md.
