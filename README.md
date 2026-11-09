# RAMP-D Phase 1C — Adaptive Subdivision

This release includes the accepted Phase 1A/1B numerical core and adds an
adaptive *local tube-width policy* on top of validated Picard integration.
Python 3.10+ orchestrates the integrator; the C++17/MPFR backend performs the
outward-rounded interval arithmetic. No dataset, GPU, SUMO process or CARLA
process is required in this phase.

**Semantics:** `VALIDATED` means the complete requested time horizon is covered
by replayable Picard inclusion witnesses and, when enabled, every accepted
local tube box obeys the configured coordinate-width limits. It does not mean
collision-free, rule-compliant, friction-feasible, recursively safe, or
executable. Width limits are numerical/abstraction resolution budgets, not
physical safety constraints. Failure to meet them returns `UNKNOWN`.

## Phase 1C additions

- Exact rational diameters for binary64 interval endpoints. Width comparison
  is exact against the configured binary64 cap; no epsilon is added.
- Six independent local width caps in SI units, in state order
  `(px [m], py [m], psi [rad], v [m/s], a [m/s^2], delta [rad])`.
- Width-triggered time bisection even when the coarse Picard inclusion itself
  succeeded. Both children are recomputed and independently validated.
- Separate `max_width_subdivisions` budget, in addition to the existing step,
  attempt, depth, minimum-step and wall-clock budgets.
- Explicit `INITIAL_WIDTH_LIMIT`, `WIDTH_SPLIT_BUDGET`, and width-related
  depth/min-step `UNKNOWN` reasons. No incomplete horizon receives an endpoint.
- Per-segment exact width metadata in certificate schema v2. Replay recomputes
  widths and enforces the recorded width policy. Schema v1 Phase 1B certificates
  remain readable.
- Fixed-coarse, fixed-fine and adaptive-width synthetic benchmark with JSON/CSV
  output. Runtime measurements are descriptive, not pass/fail performance
  claims.

A coordinate's local tube width includes both true support spread and the
coordinate range traversed during that time substep, as well as interval
wrapping/inflation. Subdivision reduces the local time span; it cannot remove
real initial uncertainty or uncertainty that genuinely accumulates. If the
initial support already exceeds a cap, integration returns `UNKNOWN` without
attempting to split time.

## Dependencies

Linux, GCC/Clang, CMake >= 3.16, Python >= 3.10, official MPFR/GMP development
headers and libraries. On Ubuntu/Debian:

```bash
sudo apt-get update
sudo apt-get install -y build-essential cmake libmpfr-dev libgmp-dev
python -m pip install -r requirements-test.txt
```

Use the intended active Python 3.10 environment. CARLA 0.9.16 and SUMO 1.20
are not imported, started or tested. The simulation mode may remain headless;
no simulator is needed for Phase 1C.

## One-command target acceptance

From `/home/senzeyu2/code/RAMP-D`:

```bash
PYTHON_BIN="$(command -v python)" bash scripts/validate_phase1c.sh
python scripts/package_report.py
```

The acceptance script creates a clean `build_phase1c/` tree, requires discovery
of all three native tests, runs the full Python regression suite, the Phase 1B
Picard demo and witness replay, the seeded RK4 falsification audit, and the
Phase 1C benchmark. It rejects zero native tests, skipped/failed Python tests,
benchmark runs without width-triggered splits, invalid benchmark witnesses,
and accepted segments exceeding their width caps.

The report is written under `reports/phase1c_<UTC timestamp>/`. The packaged
server report is `reports/RAMP-D_Phase1C_server_report.zip`.

## Manual build and tests

```bash
cmake -S . -B build_phase1c -DCMAKE_BUILD_TYPE=Release -DRAMPD_BUILD_TESTS=ON
cmake --build build_phase1c --parallel 2
(cd build_phase1c && ctest -N && ctest --output-on-failure)
export PYTHONPATH="$PWD/python${PYTHONPATH:+:$PYTHONPATH}"
export RAMPD_INTERVAL_LIB="$PWD/build_phase1c/librampd_interval.so"
python -m pytest -q tests
python scripts/benchmark_phase1c.py --output reports/phase1c_benchmark.json --repeats 5
```

## Typical API

```python
from rampd_core import PicardOptions, integrate

opts = PicardOptions(
    max_step_s=0.4,
    max_tube_widths=(2.2, 0.8, 0.1, 0.3, 0.1, 0.01),
    max_width_subdivisions=10000,
    max_steps=10000,
    max_attempts=20000,
    max_depth=20,
)
result = integrate(initial, control, vehicle, horizon_s=0.8, options=opts)
```

The numerical values above are a synthetic benchmark configuration, not
recommended universal vehicle thresholds. Select width caps from the downstream
collision/resource geometry resolution and uncertainty budget. Do not copy them
as physical safety limits.
