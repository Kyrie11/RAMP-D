# Numerical contract and conditional enclosure argument

## 1. Paper mapping

The source is `AnonymousSubmission2027(2).tex`, especially `eq:bicycle`,
`eq:friction`, `eq:picard-tube`, and `alg:tube`.

State order is `(px, py, psi, v, a, delta)`; input order is
`(jerk, steering_rate)`. The nominal vector field is exactly

    (v*cos(psi), v*sin(psi), v*tan(delta)/L, a, j, omega_delta).

The API additionally accepts an explicit six-component additive DERIVATIVE
box W. It defaults to zero. The paper does not determine this injection map,
its calibration or numerical bounds; this is a documented engineering extension,
not a claimed identification of the real vehicle's disturbances.

W component units are respectively m/s, m/s, rad/s, m/s^2, m/s^3, rad/s.
All parameters are exact configured binary64 point values, not uncertain
physical parameter intervals. Physical parameter uncertainty must be enclosed
explicitly in a later model extension or a justified disturbance contract.

## 2. Interval backend

Every supported arithmetic endpoint is evaluated through MPFR with explicit
RNDD (lower) / RNDU (upper) rounding, at 192-bit intermediate precision. Float
inputs are exactly representable at that precision. Conversion back to binary64
uses the same outward rounding direction. Directed rounding at two stages is
still an enclosure; mere increased precision without directed rounding would
not be sufficient.

Addition and subtraction use monotonic endpoint formulas. Multiplication and
division evaluate all four endpoint combinations with directed bounds; division
rejects a denominator containing zero. Square treats zero-crossing intervals
separately and therefore has a nonnegative lower endpoint.

For sine/cosine, the C++ implementation evaluates endpoint values with MPFR and
adds all possibly enclosed critical extrema. Candidate critical indices are
computed from an outward enclosure of x/pi (minus 1/2 for sine), using a
rigorous enclosure of pi. If an extra integer index is included, the result
can only become wider. Indices are bounded before conversion to an integer.
For absolute arguments exceeding 1e6 radians, sine/cosine deliberately return
[-1,1]; this is a sound, less precise fallback, NOT an ordinary argument reduction.
Tangent rejects intervals possibly containing a pole and uses monotonicity
between poles. Very large tangent arguments are rejected rather than guessed.

Every operation requires finite ordered endpoints. Nonfinite outputs are errors.
Binary64 underflow is enclosed using MPFR's directed conversion, not flushed to
zero silently. The C API rejects SSE FTZ/DAZ mode and a narrowed MPFR exponent
range. It does not change the caller's hardware rounding mode. Native tests
exercise upward, downward, toward-zero and nearest hardware modes.

Do not construct `Interval.point(mu * g)` as a substitute for interval
multiplication: the ordinary product may already have rounded. This was a
specific Phase 1A defect and has been corrected in the friction computation.

## 3. One-step Picard contract

Given initial box X0, a control image U, disturbance image W, and duration h,
search for a finite box Z in the smooth bicycle-model domain such that

    P = X0 + [0,h] F(Z,U,W) is strictly inside Z componentwise.

The returned endpoint is

    E = X0 + [h,h] F(Z,U,W).

The paper uses non-strict subset inclusion. This implementation requires
strict componentwise inclusion as a conservative sufficient test. It never
relaxes a failed comparison by a tolerance. The inflation pads are candidate
search parameters, NOT admissible residual errors.

Assume the true initial state lies in X0, L is the configured positive value,
and the realized input/disturbance signals are measurable and remain in U/W.
The bicycle field is locally Lipschitz in x on the checked steering domain,
with bounded inputs on the finite box. Local Caratheodory solutions exist and
are unique. Up to any proposed first exit from Z, the integral equation gives
x(t) in X0 + [0,h] F(Z,U,W), which is strictly inside Z. This contradicts first
exit. Compactness and boundedness inside the smooth domain extend the solution
to h. Consequently every intermediate state lies in Z and x(h) lies in E.
A contraction-factor test is not required by this first-exit argument; this
is not an error-estimated explicit Euler rollout.

The stored witness contains X0, h, Z, F, P, E, lower inclusion margins and
iteration count. `check_witness` recomputes the vector-field bound and inclusion
relations without running the enclosure search. This is independent of the
SEARCH path, not an independent numerical library. A common arithmetic defect
could affect both paths; rational and mpmath audits are additional falsification
checks, not replacements for the enclosure argument.

Candidate inflation is selective: only coordinates failing strict inclusion
are enlarged, then ALL coordinates are re-evaluated. An initially satisfied
coordinate may fail later as another coordinate grows; it is not exempt from
subsequent checks. Search failure does not disprove existence of a tube.

## 4. Composition, exact time and UNKNOWN

A successful substep feeds its entire endpoint box into the next substep.
Time intervals form a contiguous partition, and their union is retained as a
list of local tubes, not confused with a terminal-state box.

The input horizon is an EXACT BINARY64 VALUE. It is repeatedly halved only when
the half is exactly representable; Python Fraction tracks start/end times
without floating-point accumulation. Underflow/inexact halving is rejected.
The final time must equal Fraction.from_float(requested_horizon) exactly. There
is no `remaining < epsilon` termination rule that could leave an uncovered tail.
A float 0.1 does not mean an exact decimal rational 1/10. External protocol
timestamps require a future explicit conversion/enclosure contract; this phase
must not silently claim exact decimal-clock semantics.

Iteration, depth, minimum-step, attempt, accepted-step and wall-clock budgets
are checked. The wall-clock budget is enforced between finite native calls;
it is not a hard-real-time interrupt of MPFR. Every incomplete result is UNKNOWN,
with `endpoint=None`. A verified prefix is exposed separately and is never
relabeled as a proof over the requested complete horizon.

`replay_certificate` accepts only complete VALIDATED certificates, verifies
all substep inequalities and exact endpoint/time linkage, and rejects UNKNOWN,
empty lists and unsupported safety claims. JSON is not a cryptographic signature.
Replay establishes the claim for the encoded problem; a future planner must
bind that problem to its current query/configuration before using a certificate.

## 5. Deliberate exclusions

- No collision or swept-footprint check (Phase 1D).
- No rule, capacity, resource, observation or protocol branching check.
- No terminal invariant, backup-policy synthesis or full-support verifier.
- No automatic state/input-limit enforcement, speed clipping, stopping reset,
  actuator saturation, friction filtering or real-vehicle model calibration.
- No feedback policy synthesis; U is a supplied common control image.
- No validated other-agent response model or neural-model safety inference.
- No time-dependent vector field or hybrid jump integrator in this release.
- No claim of maximal reachable sets, optimal tightness or industrial assurance.

In particular, a high-friction-demand trajectory can have a perfectly valid
ODE enclosure. `VALIDATED` is not `CERTIFIED`. Tests explicitly enforce that
distinction. The position reference point (rear axle versus body center) is
not fixed by the supplied equation alone; a physical frame/footprint mapping
must be established before Phase 1D and simulator integration.

## 6. Trusted base and evidence

The argument is conditional on correct MPFR/GMP behavior, the C++ interval
formulas, the model/domain assumptions, correct ABI linkage and supported
floating-point environment. No proof-assistant verification of the implementation
has been performed. Unit tests, exact analytic cases and Monte Carlo-style
checks can find bugs; they cannot prove that no software or modeling bug remains.
All subsequent phases must preserve these tests as regressions.

Primary references checked during this development:
- The uploaded paper's labels listed in section 1.
- GNU MPFR manual: rounding modes, correct rounding, `mpfr_get_d`, `mpfr_const_pi`.
- CMake CTest manual: `--test-dir` introduced in version 3.20.
- Boost.Interval rounding-policy documentation: required rounding assumptions
  for arithmetic/transcendental operations in the previous backend.
