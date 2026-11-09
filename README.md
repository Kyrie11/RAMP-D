# RAMP-D — Phase 1A

This is the initial, self-contained project skeleton for **Interval Arithmetic + the paper's Kinematic Bicycle Model**. It is not yet a validated reachable-tube integrator and does not issue safety certificates.

## Scope

Implemented:
- C++17 interval backend using Boost.Numeric.Interval with directed rounding control and transcendental interval extensions.
- Python 3.10+ API via `ctypes`.
- The six-state ODE exactly as written in `AnonymousSubmission2027.tex`, Appendix `Physical Recoverability and Continuous Constraints`:
  `x=(px, py, psi, v, a, delta)`, `u=(jerk, steering_rate)`.
- Interval extension of the ODE, including interval `sin`, `cos`, and `tan`.
- Interval enclosure of the paper's friction expression.
- C++ and Python unit tests.

Not implemented in Phase 1A:
- Picard iteration, validated time integration, adaptive subdivision, reachable tubes, swept footprints, other-agent dynamics, protocol events, or `S_infinity`.
- Vehicle parameter calibration and state/control limits. The paper says these are bounded/calibrated but does not give numerical values in the provided equations.
- A physical disturbance injection matrix. The paper uses `W` but does not specify the continuous-time injection map. The API therefore permits an explicitly supplied additive derivative box for plumbing/tests; the default is exactly zero and no nonzero physical disturbance is asserted.

## Numerical backend notes

The C++ target uses Boost.Numeric.Interval, `rounded_transc_std` and the platform C99 floating-point environment rounding control. Compilation explicitly disables fast-math and enables rounding-math. Do not build this target with `-ffast-math`, `-Ofast`, unsafe reassociation, or LTO settings that invalidate dynamic rounding assumptions. The transcendental enclosure relies on the Boost interval implementation and the platform C math library honoring the selected rounding mode; this must be re-audited on the target server/compiler before treating the backend as a formal proof component. This Phase 1A test suite is an implementation check, not a complete proof of compiler/libm conformance.

The API rejects division intervals containing zero and rejects non-finite output intervals. A tangent interval crossing a pole is consequently not accepted as a finite enclosure.

## Build and test (Linux)

Requirements: C++17 compiler, CMake >= 3.18, Boost headers, Python >= 3.10, pytest.

```bash
cmake -S . -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build -j2
ctest --test-dir build --output-on-failure
PYTHONPATH=python python3 -m pytest -q
```

No pip installation is required for this phase. The Python wrapper locates `build/librampd_interval.so`. If needed, set `RAMPD_INTERVAL_LIB` to the full library path.

## Python example

```python
from rampd_core import Interval, BicycleParameters, StateBounds, ControlBounds, rhs

p = BicycleParameters(wheelbase_m=2.8, friction_coefficient=0.9)
x = StateBounds(
    px=Interval(0, 0), py=Interval(0, 0), psi=Interval(0.1, 0.2),
    v=Interval(8, 9), a=Interval(-0.2, 0.1), delta=Interval(-0.05, 0.05),
)
u = ControlBounds(jerk=Interval(-1, 1), steering_rate=Interval(-0.1, 0.1))
xdot = rhs(x, u, p)
print(xdot)
```

The values above are illustrative only, not calibrated vehicle parameters.
