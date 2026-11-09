# Phase 1A acceptance record

## Delivered
- [x] C++ interval arithmetic shared library.
- [x] Python `ctypes` wrapper.
- [x] Six-state kinematic bicycle interval vector field.
- [x] Friction-expression interval enclosure.
- [x] C++ and Python unit tests.

## Local test environment
The build was executed in the assistant's isolated Linux container (GCC 14.2, CMake 3.31.6, system Boost headers, Python 3.13.5). This is **not** the user's target host. The user stated their target Python is 3.10 and CARLA/SUMO versions are 0.9.16/1.20; those services are not used by Phase 1A.

## Test result
- CMake configure: PASS
- C++ compile/link: PASS
- CTest: 1/1 PASS
- Python pytest: 7/7 PASS (includes 250 deterministic randomized pointwise checks of the RHS and friction enclosure)

## Known limitations / gates before certification
1. The paper does not specify the continuous disturbance injection map; only the zero-disturbance nominal model is paper-determined at this point.
2. The paper does not provide calibrated `L_w`, `mu_f`, state bounds, or input bounds in the supplied model excerpt. The `2.8 m`, `0.9`, and `9.80665 m/s^2` examples are test/demo values only.
3. Boost interval arithmetic with directed rounding is a candidate backend, not yet accepted as a proof-grade backend on the user's machine. Confirm compiler flags, hardware fenv behavior, Boost version, and libm transcendental behavior on that host. For a stronger independent audit, compare against MPFR/MPFI or Arb before claiming validated integration.
4. No Picard fixed-point inclusion or time propagation is implemented in this phase.

## Failure/correction log
- Initial Boost policy composition did not expose the transcendental methods through `unprotect`; corrected by defining a combined rounding policy that retains the complete API.
- A test initially expected `cos(pi/2)` to be exactly zero at a floating-point approximation to pi/2. The test was corrected to use an interval with pi/2 strictly in its interior; this was a test-boundary issue, not a backend defect.
- Division by a denominator interval containing zero is now explicitly rejected instead of allowing an unbounded result.
