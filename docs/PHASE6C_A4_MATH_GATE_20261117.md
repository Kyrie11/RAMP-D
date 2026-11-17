# Phase6C-A4: mathematical correctness gate, not an end-to-end safety certificate

**Source**: `AnonymousSubmission2027(3).tex` (uploaded in the same review).  The new SC/Rank semantics are those in Sect. *Safe-continuation feasibility and commitment timing* and Appendix *Set-Valued Viability, Optimization, and Verification Details*.  No change to the manuscript's definition is asserted.

## Server evidence reviewed

`RAMP-D_Phase6C_server_report(1).zip`: 428 full Python tests pass; 43 specialized tests pass. WOMD training/validation bounded real-record diagnostics pass (only small selected files). AV2 training and validation SKIP due to missing pyarrow. Native CTest detects 0 mandatory tests; CARLA/SUMO SKIP. Overall status ERROR. These results do not independently verify the full mathematical model.

## Confirmed implementation bug fixed

Before A4, `replan_sc_execution` compared the SC contract hash and `cell_id` but **not the support carried by that ID**. The same label could silently be reused with different intervals/modes/other-agent bounds, potentially inheriting the wrong rank. A4 stores `support_digest_pairs` per certificate and a support digest in `SCExecutionBudget`, verifies it at `start`, `advance`, and `replan`, and fails closed on mismatch. The digest is over exact binary64 bound encodings and all mode/other-state dimensions. It is an identity binding, not proof of full concrete support.

Before A4, a valid rank-preserving replan could also replace a short terminal policy with a far longer one without preserving an inherited **worst-case completion bound**. A4 retains `remaining_completion_s` using exact `Fraction`s; advancing decreases the available time by the verified step, and replanning must not increase the bound. Exact floating values are forbidden for time/margin *proof claims*; use Fraction or decimal strings (the binary64 input to the physical backend has a different, explicit meaning).

## Newly implemented, independently checked finite abstraction

- `sc_proof_audit.py`: standalone finite-structure audit; it does not call `compute_sc_inner` nor `_evaluate_action`. Checks source-atom coverage, observation union and single public child, strict rank decrease, selected public action, exact step+worst-child time, claimed margin recursion, terminal evidence and context/support binding.
- `finite_game_oracle.py`: dependency-free game solver by set-iteration; separately implemented recursive AND/OR winning check. They agree over 300 fixed-seed random tiny games in local tests, including adversarial cycles, unsafe supports and nondeterministic observations.
- `tests/test_sc_a4_proof_audit.py`: seven new targeted proof checks, including mutation attacks on certificate ranks/times/labels/support and two real rank-replanning bugs. Local 7/7 **with a mathematical value-carrier stub only**; server real-MPFR run pending.
- `scripts/validate_phase4.sh`: calls mandatory native test discovery/execution and no longer judges CTest via a permissive textual pattern.
- `scripts/validate_phase6c_a4.sh`: explicit full proof-gate script. Missing CMake build / native tests remains a hard error, not PASS.

## Mathematical scope and independent proof obligations

| Layer | What can be checked | What remains unproved in this release |
|---|---|---|
| Phase1A | C++ MPFR outward interval arithmetic with direct rounding | Fresh native machine build and independent MPFR/property oracle for every arithmetic path; CTest currently 0 in last report |
| Phase1B/1C | Picard strict inclusion and exact dyadic substeps, bounded UNKNOWN | Fresh replay of native samples, per-step physical modeling assumptions, differential inclusion outside supported domain |
| Phase1D | swept rectangular footprint separation for declared geometry | Calibration, mixed actor geometry, complete resource polygons, time-continuous shape correctness |
| Phase2/3 | finite info-support game, public backup law, selected witness replay | full scene support/observability and a general infinite safety invariant; safety fallback != finite task completion |
| Phase4/5 | three-valued verifier and CEGAR under caller-supplied protocol/physical checkers | end-to-end, complete full-support protocol relation, independent resource/controller and observation replay |
| Phase6C-A3 | finite SC inner recursion, certified-tail *interface*, strict rank, conditional margin bounds | actual task-accepting tails and full physical/branch proof callback implementations |
| Phase6C-A4 | independent finite certificate structural audit + inherited support/time identities | does not turn callbacks into proofs; no real-scenario `full_support_certified` claim |

The induction for the finite abstract SC family is sound **conditionally on** (P0) safe continuous tubes, (P1) complete public observation partition/merging, (P2) all-history finite tail reaching task acceptance, (P3) consistent version/binding. A4 verifies the claimed *finite structure* and requires replay callbacks, but cannot independently prove those callbacks are sound. A single counterexample to a candidate does not establish nonviability.

## Dataset semantics and metrics

WOMD `tracks_to_predict` indexes track arrays; `Track.id` is the actor identifier. The report correctly uses target masks, valid future frames and source hashes. `alignment_method=bounded_piecewise_linear_prediction_resample` means the CV-baseline ADE/FDE are custom full-rate debug metrics: NOT the official WOMD 2Hz challenge aggregate (minADE/minFDE/miss-rate/mAP) and NOT a safety bound. Record-level ADE averaging is not a dataset-wide agent/step-weighted benchmark. This is acceptable for plumbing diagnostics only.

AV2 Parquet `object_category` numeric 2/3 means scored/focal targets; `track_id == 'AV'` is the AV identity, distinct from focal. The current report is SKIP, not a demonstration of real AV2 decoding. Install `pyarrow` in the active environment, check `scenario_*.parquet`/`log_map_archive_<scenario_id>.json` pairing, split, nanosecond axis/110 steps, observed history, heading/velocity, and scored/focal coverage on real samples. AV2 MF does not provide per-track authoritative physical footprint length/width; do not silently treat shape priors as certification evidence.

## Nine losses? Manuscript actually contains eight

The current TeX table and equation explicitly list **eight**: `event`, `joint`, `occupancy`, `observation`, `viability`, `margin`, `deadline`, `causal`. If a ninth supervision target was intended, specify its exact equation/name before adding training code. Do not invent an extra label to force a count of nine.

## Next coding gate (A5): real physical+protocol proof replay integration

1. Define a frozen support/action/clock/observation/task proof bundle, with typed version-bound hashes and an explicit admissible uncertainty model.
2. Replay Phase1B/1D native tube witnesses for every public-action source atom, exact occupancy and resource permission, then replay Phase4 protocol and observation branch **coverage** independently of the candidate graph. Unaccounted alternatives -> UNKNOWN.
3. Build a task automaton and terminal-tail verifier for a small *complete* synthetic road-resource scene. Require finite task acceptance under every admissible observation, record exact tail bound and precondition. A safe stop is not an accepted terminal.
4. Only then connect these typed proof providers into `compute_sc_inner` and `audit_sc_proof`, run mutation/adversarial tests, and extend to CARLA/SUMO. Finite/toy evidence can establish semantics but not full real traffic certification.

## Server commands

```bash
python -m pip install -r requirements-data.txt
python -c 'import pyarrow, pandas; print("AV2 parquet environment OK", pyarrow.__version__)'

# Run in a newly unpacked release tree; not the mixed previous checkout:
python scripts/verify_release.py
bash scripts/validate_phase4.sh
bash scripts/validate_phase6c_a4.sh
MAX_RECORDS=5 bash scripts/validate_phase6b.sh
MAX_RECORDS=5 bash scripts/validate_phase6c.sh
```

If CTest again reports `Total Tests: 0`, inspect `$PWD/build_phase3/CTestTestfile.cmake` and `$PWD/build_phase3/CMakeCache.txt`; rebuild cleanly **only the generated build folder** (e.g. `mv build_phase3 build_phase3_old_$(date +%s)`), with `cmake -S . -B build_phase3 -DRAMPD_BUILD_TESTS=ON -DCMAKE_BUILD_TYPE=Release`, `cmake --build build_phase3 -j 4`. Do not remove user source code or modify `MANIFEST.sha256`.
