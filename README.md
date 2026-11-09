# RAMP-D Phase 1B - validated Picard integration

This is the complete source release replacing Phase 1A. It contains the Phase
1A regression suite and a C++17 / MPFR numerical core called from Python 3.10+.
No dataset, GPU, SUMO process or CARLA process is needed in this phase.

**A `VALIDATED` result proves a dynamics enclosure under the declared model and
inputs. It is not the full-support verifier's `CERTIFIED`, not a collision
certificate, and not authorization to execute vehicle controls.**

## What changed

- Replaced the Boost/libm numerical backend with explicit MPFR directed
  rounding at 192 bits, followed by directed binary64 endpoint conversion.
- Corrected the Phase 1A friction scale: `I(mu) * I(g)`, never `I(mu*g)`.
- Added interval subtraction, square, exact-decimal enclosures and pi bounds.
- Added C++ Picard self-inclusion, selective enclosure inflation and endpoint
  bounds. Every accepted step has strict componentwise inclusion.
- Added Python failure-driven bisection, exact rational bookkeeping of dyadic
  times, resource budgets, UNKNOWN propagation and replayable JSON witnesses.
- Added stale-native-library rejection and a mandatory zero-tests guard.
- Preserved the previous Python model/RHS/friction call signatures.

## Dependencies

Supported target: Linux, GCC or Clang, CMake >= 3.16, Python >= 3.10.
The user reports Python 3.10, CARLA API 0.9.16, SUMO 1.20; the simulators are
not imported, started or tested by this release.

Ubuntu/Debian development packages:

```bash
sudo apt-get update
sudo apt-get install -y build-essential cmake libmpfr-dev libgmp-dev
python -m pip install -r requirements-test.txt
```

Use the active Python environment. No runtime Python dependency beyond the
standard library is needed; pytest and mpmath are used by the test suite.
MPFR/GMP development headers and libraries are required for the C++ build.
Boost is no longer required. A user-installed prefix is supported through
`CMAKE_PREFIX_PATH` or explicit CMake `MPFR_INCLUDE_DIR`, `MPFR_LIBRARY`,
`GMP_LIBRARY` arguments. Do not mix the old `.so` with the new Python code.

## One-command acceptance

From `/home/senzeyu2/code/RAMP-D`:

```bash
PYTHON_BIN="$(command -v python)" bash scripts/validate_phase1b.sh
python scripts/package_report.py
```

The script configures a new `build_phase1b/` tree, discovers all 3 C++ tests,
runs them, runs the Python suite, replays a demo witness, runs a numerical
falsification audit, and records environment/source/library hashes. It refuses
zero native tests even when the installed CTest itself exits successfully.

Pass additional arguments to CMake after the script name if necessary:

```bash
PYTHON_BIN=python bash scripts/validate_phase1b.sh -DCMAKE_PREFIX_PATH="$CONDA_PREFIX"
```

This requires MPFR/GMP development files actually to be installed in that
prefix; setting a prefix alone does not install them.

## Manual build / tests

```bash
cmake -S . -B build_phase1b -DCMAKE_BUILD_TYPE=Release -DRAMPD_BUILD_TESTS=ON
cmake --build build_phase1b --parallel 2
(cd build_phase1b && ctest -N && ctest --output-on-failure)
export PYTHONPATH="$PWD/python${PYTHONPATH:+:$PYTHONPATH}"
export RAMPD_INTERVAL_LIB="$PWD/build_phase1b/librampd_interval.so"
python -m pytest -q tests
python scripts/demo_phase1b.py --output reports/demo_certificate.json
python scripts/replay_certificate.py reports/demo_certificate.json
python scripts/audit_phase1b.py --output reports/empirical_audit.json
```

`ctest --test-dir` was added in CMake 3.20. Entering the build directory works
with the older supported versions too. The uploaded Phase 1A already had
`enable_testing()` and `add_test()`; its reported root-directory search is most
consistent with an unsupported flag/CTest version, not a missing test target.
The target's actual CTest version is recorded by the acceptance script.

## Python API

```python
from rampd_core import (
    BicycleParameters, StateBounds, ControlBounds, PicardOptions,
    TubeStatus, integrate, replay_certificate,
)

params = BicycleParameters(wheelbase_m=2.8, friction_coefficient=0.9)
initial = StateBounds.point([0, 0, 0, 8, 0, 0])
control = ControlBounds.point(jerk=0, steering_rate=0)
result = integrate(initial, control, params, horizon_s=1.0,
                   options=PicardOptions(max_step_s=0.05))
print(result.status.value, result.reason)
if result.status is TubeStatus.VALIDATED:
    print(result.endpoint)
    result.save("reports/example.json")
    assert replay_certificate("reports/example.json").ok
else:
    assert result.endpoint is None
    print("verified prefix ends at", result.validated_until)
```

`max_step_s` is a cap, not a fixed step: a 1 s horizon with a 0.05 s cap is
bisected to 32 substeps of 0.03125 s before any failure-driven refinement.
No unvalidated point integrator is used as the enclosure generator.

## Package guide

- `cpp/src/interval.cpp`: directed interval operations and bicycle vector field.
- `cpp/src/picard.cpp`: one-step candidate search and inclusion witness.
- `python/rampd_core/reachability.py`: orchestration and exact-time schedule.
- `python/rampd_core/certificate.py`: serialization and search-independent replay.
- `tests/`: retained Phase 1A regressions, rational/high-precision audits,
  analytic-flow tests, failure handling and witness tampering tests.
- `docs/NUMERICS_AND_SCOPE.md`: mathematical contract, proof argument and limits.
- `docs/PHASE1B_ACCEPTANCE.md`: actual local test results and target acceptance gate.
- `docs/FAILURE_LOG.md`: detected failures, fixes and unresolved boundaries.
- `reports/local/`: local evidence, not target-server results.

The local container lacked official MPFR development headers. Its native
functional tests used an explicitly recorded minimal public-API declaration
header against the real MPFR 4.2.2 runtime. That header and all binaries/build
trees are **excluded** from this source release. The target must rebuild using
the official development headers. This limitation is visible in local report
status `BOOTSTRAP_TEST_PASS_REQUIRES_OFFICIAL_HEADERS`; it is not target acceptance.
