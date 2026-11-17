# RAMP-D Phase6C-A5/1 — native replay and finite task/protocol evidence gate

**Source of mathematical semantics:** `manuscript/AnonymousSubmission2027.tex` (identical SHA-256 to the uploaded 2026-11-17 TeX). This is a **partial A5 increment**, not acceptance of complete Phase 6C or RAMP-D.

## 1. Goal and proof obligations

Retain the phase sequence and A4 SC/rank contracts. Do NOT replace `compute_sc_inner`, `audit_sc_proof`, the full-support verifier, Picard MPFR arithmetic or the existing dataset loaders. The incremental gates are:

- **A5/1-D**: Verify a finite task tail as a nonanticipative information-state policy under every declared observation, with exact `Fraction` worst-case duration. Waiting that never reaches task acceptance is excluded. `FiniteTaskModel` is a *declared finite model*, not a statement about full traffic behavior.
- **A5/1-P**: Audit all enabled, point-time protocol transitions for each source atom against the independently supplied successor boxes, including same-observation merging, action identity, protocol digest and observation/clock digest. Unknown guard/uncertain public-time/hidden events are unresolved. No behavior-model probability can delete a branch.
- **A5/1-X**: Replay every included native MPFR Picard step; require an exact dyadic public step compatible with Phase1B's authoritative binary64 time axis, a constant common control, complete continuous safe-domain inclusion, explicit full actor/resource model assumptions, pairwise continuous swept-body separation and static resource constraints. Both world geometry and the tube artifact are SHA-256 context-bound. Incomplete evidence -> False/UNKNOWN.
- **A5/1-N**: Repair native CTest discovery by executing from the build directory (works with older CTest), requiring an ON cache, three exact named tests and 100% success. A5 uses its own build folder and does not remove earlier build output.

The mathematical interpretation is:

\[
\text{replay}(E_{x,u},\mathcal P,\mathcal M)=\text{true}
\quad\Longrightarrow\quad
\bigcup_t\operatorname{Reach}^{\rm model}_t(x,u)\subseteq\mathcal X_{\rm declared-safe}
\]

**only** when the declared disturbance, actor-enumeration, geometry, resource-state, observation and protocol models actually cover the intended scenario. The finite tail audit adds acceptance for the *declared task transition graph* but not physical or protocol replay of each tail step. These premises must not be silently promoted to a full-support real-world safety or task-success certificate.

### Exact time limitation, deliberately fail closed

Phase1B's `integrate` currently tracks exact binary64 step durations with `Fraction.from_float(h)`; the published SC contract uses exact rationals (e.g. `1/10`). An exact `1/10`-second SC step cannot be equated with binary64 `0.1` without a new certified resampling/contraction rule. A5/1 accepts representable dyadic steps such as `1/8`, and rejects this mismatch instead of inserting an unsound tolerance. A5/2 must implement provably covering time-axis conversion or a rational native step backend before a 10 Hz SC certificate.

### Conservative restrictions

- Constant common action only; feedback-controller digests remain unsupported at this gate.
- Model-declared world completeness required, with exact context hash. A Boolean `complete_actors_assumed` records the *assumption* and does not prove that a real-world detector found all actors.
- One fixed resource state throughout each toy prefix. Other actors plus resource polygons are unresolved until the mixed-actor resource occupancy monitor is implemented. Unknown separation is not a collision counterexample.
- Protocol transitions must have a proved guard and one exact public observation instant at the end of the step. Message issue/receipt and local detection must not be silently conflated.
- The task acceptance checker does not include native swept-body or protocol checks for its tail, so its output cannot be directly used as `terminal_replayer=True` in a full-support SC claim.

## 2. Files changed/added

- `python/rampd_core/a5_finite_contract.py`: finite task policy AND/OR replay and exact worst time.
- `python/rampd_core/a5_replay_bridge.py`: model-/clock-/tube-bound physical and protocol gates.
- `tests/test_phase6c_a5_finite.py`: finite task acceptance, wait-loop, hidden observation, numeric precision and mutation tests.
- `tests/test_phase6c_a5_bridge.py`: MPFR-based prefix replay and protocol omission/clock/geometry/resource tests (run on target server).
- `tests/test_a5_native_discovery.py`: native discovery on a minimal, independent CMake fixture.
- `scripts/check_native_ctest.py`: use `cwd=build_dir`, check CMakeCache and nonzero mandatory tests, preventing root-directory zero-test false PASS.
- `scripts/validate_phase6c_a5.sh`: separate mandatory acceptance gate; final PASS explicitly scoped.
- `PROGRESS.json`, `README.md`, `MANIFEST.sha256`: versioned source synchronization.

## 3. Local verification / failure analysis

Available local: Python and CMake/CTest. Not available in this container: native MPFR **development headers**, full `/data0` real scenes and CARLA/SUMO server. Thus native bridge tests are **not** legitimately executable here.

- `python -m pytest -q tests/test_a5_native_discovery.py tests/test_phase6c_a5_finite.py`: **10 PASS** after fixing one test's assertion: when `RAMPD_BUILD_TESTS=OFF`, CMake may omit `CTestTestfile.cmake` entirely instead of producing an empty list. Both failure modes now correctly count as NOT RUN. This was a test-expectation issue, not a relaxation of the gate.
- `python -m compileall -q python tests scripts`: pass.
- `bash -n scripts/validate_phase6c_a5.sh`: pass.
- Native MPFR `test_phase6c_a5_bridge.py`, existing Phase0–6C suite: **PENDING SERVER**.
- Real-data full coverage and paired interventions: **NOT RUN**; the uploaded Phase6C report remains the latest evidence.

**Do not label this release `CERTIFIED` or set `SCResult.certified_full_support=True`.** A4 still checks finite structure and callback acceptance conditionally. A5/1 provides narrower executable proof adapters, but neither establishes the terminal tail's physical realization across all histories nor completes the real scenario's support coverage.

## 4. Server execution in a NEW checkout

```bash
conda activate mfrp
mkdir -p /home/senzeyu2/code/RAMP-D-A5
unzip -q RAMP-D_Phase6C_A5_1.zip -d /home/senzeyu2/code/RAMP-D-A5
cd /home/senzeyu2/code/RAMP-D-A5
python -m pip install -r requirements-test.txt
python scripts/verify_release.py
bash scripts/validate_phase6c_a5.sh
```

Expected from A5 script: release-integrity PASS, 10/10 dependency-free targeted tests, CMake configure/build against MPFR+GMP, at least 3 named CTest tests and 100% pass, then physical/SC/Phase4/Picard regressions and full suite PASS. `reports/phase6c_a5_*/` contains the logs and scoped summary. **Any failure is a failing gate**, not a success with missing tests.

Separate 6B / 6C real-data verification (requires active-env `pyarrow`, native library):

```bash
python -m pip install -r requirements-data.txt
python -c 'import pyarrow, pandas; print(pyarrow.__version__, pandas.__version__)'
MAX_RECORDS=5 bash scripts/validate_phase6b.sh
MAX_RECORDS=5 bash scripts/validate_phase6c.sh
```

Do not launch CARLA/SUMO for A5/1. The official co-simulation bridge and realistic paired interventions are later, after model-conformance and task-terminal integration; no current `SUMO_CONFIG` or `CARLA_COSIM_DIR` was supplied, so the previous co-sim SKIP was correct.

## 5. Next iteration A5/2, then 6C-B

1. Build a *physical and protocol verified* finite task-acceptance terminal tail; integrate A5 proof providers with `compute_sc_inner`, `audit_sc_proof` and Phase4, testing same-observation merging, all hidden histories, task acceptance and inherited rank/time. No shortcut via `lambda *args: True`.
2. Add event-split time-interval handling, controller-law replay, variable permissions and mixed-actor resource occupancy. Resolve 0.1-second rational/native time by proved conservative conversion. New status `UNKNOWN` for unsupported semantics.
3. Complete WOMD/AV2 dual real-data gates; add causal paired-run identity/seeds/protocol clock evidence and real-train factual loss, then CCG/ICG and dynamic controllability before closed-loop ICAPS E1–E5 tables.
