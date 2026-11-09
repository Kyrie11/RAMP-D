# RAMP-D Phase 1D — Swept Footprint and Conservative Separation

This release preserves the accepted Phase 1A-1C numerical core and adds an
outer enclosure for oriented rectangular vehicle footprints, plus a sufficient
fixed-axis test for separating two complete swept spatial sets.

Python 3.10+ is the top-level API. C++17/MPFR provides directed-rounded
interval arithmetic. The native ABI is now **3** because an MPFR-directed
interval square-root operation was added for normalized geometric clearance.
An ABI-2 library from Phase 1C must not be reused; the validation script builds
a clean `build_phase1d/` directory and the Python loader rejects stale ABIs.

## Meaning of the results

- `VALIDATED` (from the dynamics integrator): the complete requested horizon
  is covered by replayable Picard state-tube witnesses.
- `SEPARATED` (from the footprint module): two swept spatial outer enclosures
  have a strictly positive outward-proved projection gap on a fixed axis.
- `UNKNOWN`: the supplied axes did not prove strict separation, a numerical
  enclosure could not be formed, or a required input/time alignment is invalid.

**There is deliberately no `COLLISION` status.** Overlapping outer enclosures
or failure to find a separating axis are not proof of a real collision. They
must be refined or concretized by a later verifier. Neither `VALIDATED` nor
`SEPARATED` is the full-support planner's `CERTIFIED` result and neither
authorizes control execution.

## Geometry contract

A vehicle rectangle has fixed configured length and width. The model state
`(px, py)` is a reference point, not automatically the body center. The
`VehicleGeometry.center_offset_x_m/y_m` values locate the rectangle's
geometric center relative to that state reference in body coordinates. Zero
is valid only if `(px,py)` is the geometric center. The supplied paper does not
specify whether its bicycle-model reference is rear-axle center or body center;
real vehicle dimensions and this offset must be calibrated before applying the
module to AV2/WOMD/CARLA data.

The state box supplied to `SweptFootprint` must enclose the vehicle state for
the **entire** exact time interval. Use `SweptFootprint.from_segment` with a
Phase 1B/1C `TubeSegment`, or the high-level `separate_tube_results` function.
The latter rejects incomplete/UNKNOWN `TubeResult` objects and replays both parent dynamics certificates before geometry is evaluated. If two adaptive
integrators have different step boundaries, `separate_tube_results` forms a
common temporal refinement and reuses each source segment's whole-step tube on
the contained overlap interval; this is sound but may be conservative.

## Mathematical method

For a fixed axis `n`, a rectangle centered at `c` with orientation `psi` has
support radius

    r(n,psi) = (L/2) |n dot (cos(psi), sin(psi))|
             + (W/2) |n dot (-sin(psi), cos(psi))|.

The center includes the configured body-frame reference offset. Interval
arithmetic bounds the center projection and the two absolute dot products
for every state in the input tube. This gives an outward projection interval
for the union of all footprints over the substep. AABB axes and fixed axes
selected from the midpoint headings of both vehicles are tested. Axis
selection uses ordinary `math.sin/cos` only to choose candidate binary64
vectors; once selected, those vectors are treated as exact binary64 constants
and all proof arithmetic is performed by MPFR-directed interval operations.

If the two outer projection intervals are strictly disjoint, their complete
swept spatial sets are disjoint. The reported metric clearance is a lower
bound obtained by dividing the positive projection-gap lower bound by an
MPFR upper bound on the exact axis norm. If no tested axis separates, return
`UNKNOWN`. The candidate-axis family is sufficient but not complete for
uncertain swept sets.

This test is intentionally stronger than time-synchronized collision
avoidance: it proves the two vehicles' **spatial swept unions** are disjoint.
If their spatial paths cross at different times, it may return `UNKNOWN` even
when no simultaneous collision occurs. Temporal subdivision can reduce this
conservatism in later work.

## Dependencies

Linux, GCC/Clang with C++17, CMake >= 3.16, Python >= 3.10, and official MPFR/GMP
development headers/libraries. On Ubuntu/Debian:

```bash
sudo apt-get update
sudo apt-get install -y build-essential cmake libmpfr-dev libgmp-dev
python -m pip install -r requirements-test.txt
```

The target server previously reported GCC 9.4, CMake/CTest 3.18, MPFR 4.0.2,
Python 3.10.20. These versions are sufficient; no upgrade is required if the
same official MPFR development package remains installed. The ABI bump means
a clean rebuild is mandatory.

No AV2/WOMD dataset, GPU, SUMO 1.20 process, or CARLA 0.9.16 process is needed
for Phase 1D. Headless simulator configuration is not involved yet.

## One-command target acceptance

From `/home/senzeyu2/code/RAMP-D`:

```bash
PYTHON_BIN="$(command -v python)" bash scripts/validate_phase1d.sh
python scripts/package_report.py
```

The script creates `build_phase1d/`, requires discovery of all three native
tests, runs the full Python regression suite, replays the Phase 1B dynamics
certificate, reruns the Phase 1C width benchmark, runs the Phase 1D geometry
benchmark, and performs a high-precision corner-projection falsification audit.

Expected minimum results:

```text
100% tests passed, 0 tests failed out of 3
109 passed
```

The Phase 1D synthetic benchmark must report AABB-only `UNKNOWN`, oriented
candidate-axis `SEPARATED`, and successful replay of all separation witnesses.
The high-precision projection audit must report zero misses. These are
acceptance checks, not a formal proof that the implementation contains no bug.

## Manual build and test commands

```bash
cmake -S . -B build_phase1d -DCMAKE_BUILD_TYPE=Release -DRAMPD_BUILD_TESTS=ON
cmake --build build_phase1d --parallel 2
(cd build_phase1d && ctest -N && ctest --output-on-failure)
export PYTHONPATH="$PWD/python${PYTHONPATH:+:$PYTHONPATH}"
export RAMPD_INTERVAL_LIB="$PWD/build_phase1d/librampd_interval.so"
python -m pytest -q tests
python scripts/benchmark_phase1d.py --output reports/phase1d_benchmark.json --repeats 5 --iterations 100
python scripts/audit_phase1d.py --output reports/footprint_audit.json --samples 2000
```

## Main Python API

```python
from rampd_core import (
    VehicleGeometry, separate_tube_results,
)

# These dimensions/offsets are illustrative only; calibrate before use.
geometry = VehicleGeometry(
    length_m=4.5,
    width_m=1.9,
    center_offset_x_m=0.0,  # only if (px,py) is body center
    center_offset_y_m=0.0,
)
result = separate_tube_results(
    ego_tube_result, geometry,
    agent_tube_result, geometry,
)
print(result.status, result.reason)
```

Use `save_separation_certificate` on a per-overlap `SweptFootprint` pair to
write a fixed-axis separation witness, and `replay_separation_certificate`
to recompute its projections and positive gap. The separation witness assumes
the encoded input state boxes came from sound, complete dynamics tubes; it does
not itself replay the parent Picard certificates.
