# RAMP-D Phase 3 (0.6.0)

This release preserves the Phase 1A-1D MPFR/C++ numerical core and adds the
finite belief-support abstraction and information-state invariant fixed-point
engine, then adds a public common backup-policy graph and a validated-tube
execution adapter. The Python API remains the top-level interface.

## Important assurance statement

Phase 2 computes the exact greatest fixed point of the **supplied finite
abstract information-state game**. It returns `S_in_candidate` with
`assurance_scope=FINITE_ABSTRACTION_ONLY` and `certified=false`. This is not yet
a concrete RAMP-D safety certificate. A production evidence verifier must be
integrated with protocol branches, complete ego/agent reachable tubes,
resource monitors, observation support, and the Phase 4 full-support verifier.
The synthetic demo's evidence verifier is test-only.

## Vehicle reference convention

The paper's current bicycle ODE is the rear-axle-centre kinematic bicycle
model. All `(px,py)` positions use the rear-axle midpoint; footprint geometry
is shifted by an explicit rear-axle-to-body-centre offset. The bundled
`commonroad_bmw_320i_benchmark()` profile uses a reproducible nominal profile
(4.508 m x 1.610 m, wheelbase 2.5789128 m). Its 1.4227170936 m body-centre
offset treats the CG as a proxy for the rectangle centre and must be replaced
by measured geometry before physical safety claims. Friction is intentionally
left unset because it is a scenario/tire-road parameter, not a chassis
constant. See `docs/VEHICLE_REFERENCE_CONVENTION.md` and the updated paper
Appendix `AnonymousSubmission2027_Phase2.tex`.

## Environment

The user's existing target environment is retained:

- Python 3.10.20
- GCC 9.4.0
- CMake/CTest 3.18.0
- MPFR/GMP development packages; MPFR 4.0.2 is sufficient

No C++ ABI change is introduced in Phase 2. Do not use a Phase 1A/1B/1C stale
shared library: use a clean Phase 1D/Phase 2 build directory.

## Build and test

```bash
python -m pip install -r requirements-test.txt
PYTHON_BIN="$(command -v python)" bash scripts/validate_phase2.sh
```

The script runs a clean MPFR build, mandatory CTest discovery and execution,
all Phase 1A-1D regressions, all Phase 2 tests, a finite-game demo and
certificate replay, and the scaling microbenchmark. It creates a timestamped
report under `reports/phase2_*` and packages it as
`reports/RAMP-D_Phase2_server_report.zip`.

For direct debugging:

```bash
cmake -S . -B build_phase1d -DCMAKE_BUILD_TYPE=Release -DRAMPD_BUILD_TESTS=ON
cmake --build build_phase1d --parallel 2
(cd build_phase1d && ctest -N && ctest --output-on-failure)
export PYTHONPATH="$PWD/python"
export RAMPD_INTERVAL_LIB="$PWD/build_phase1d/librampd_interval.so"
python -m pytest -q tests
python scripts/demo_phase2.py
python scripts/benchmark_phase2.py
```

## Phase 2 API

```python
from rampd_core import (
    SupportAtom, BeliefCell, SafeDomain,
    ActionWitness, AtomTransition, ObservationSuccessors, EvidenceVerdict,
    compute_information_invariant,
)
```

Every cell is one complete information-state support (union of atoms). Each
candidate action is one common `(jerk, steering_rate)` control for all atoms
in that support. For each observation, successor atoms from all compatible
source atoms are aggregated into one posterior. The posterior must be covered
by one retained belief cell. Missing source transitions, unverified evidence,
unsafe tubes, or uncovered posteriors reject the action.

`split_support_atom` refines one continuous box but keeps the same
`policy_node_id`; it never invents a new observation or allows a hidden-state
branch. Existing action evidence is invalidated after a split.

## Phase 3 API

```python
from rampd_core import (
    BackupMode, BackupControlLimits, BackupTemplate,
    synthesize_public_backup, save_backup_graph, replay_backup_graph,
)
```

`synthesize_public_backup` compiles one common action per retained complete
belief support and preserves the Phase 2 observation children. The resulting
graph exposes `control(node_id)`, `route(node_id, observation)`, and
`execute_tube(...)`. It is an executable policy graph, not a concrete safety
certificate. The first implementation is the constant-control subclass of
the paper's public feedback controller; hidden atom-specific control is never
available through the API.

## Phase order

0 -> 1A -> 1B -> 1C -> 1D -> **2** -> 3 -> 4 -> 5 -> 6.

- Phase 3: public common backup controller synthesis and executable policy graph
  (constant common-control subclass; affine public gain remains deferred).
- Phase 4: protocol automata, full-support verifier and three-valued result.
- Phase 5: concrete/spurious counterexamples and CEGAR.
- Phase 6: AV2/WOMD model training and headless SUMO 1.20 + CARLA 0.9.16
  closed-loop experiments.

Phase 2 does not require datasets, SUMO, CARLA, GPU, or any simulator process.
