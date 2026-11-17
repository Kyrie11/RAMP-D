## Phase6C-A4 mathematical proof gate (2026-11-17)

Start with [README_A4.md](README_A4.md). This release repairs SC support/time-budget binding, adds an independent structural proof audit and exact finite-game cross-check, and hardens native CTest discovery. Real physical/protocol proof providers remain pending.

## Phase6C integrated repair (0.9.3-p1, 2026-11-16)

This release **combines Phase6C-A3 SC/rank + A2 map/protocol with the earlier Phase6C offline CV/simulation diagnostics**. DO NOT overlay it on an older checkout: extract into a fresh directory and run `python scripts/verify_release.py`. Fixes, evidence scope and commands: [Phase6C integration repair](docs/PHASE6C_INTEGRATION_REPAIR_20261116.md). Supervision policy: [eight losses](docs/SUPERVISION_SOURCE_POLICY_20261116.md). Locally 84 synthetic data/protocol tests and 13 synthetic finite SC/rank tests pass; native/data/simulator gates are pending target server.


**Filename and release-integrity hotfix (0.9.3-p1):** Phase6B is exclusively `scripts/validate_phase6b.sh` (lowercase `b`). The obsolete uppercase wrapper has been removed and the SHA-256 release manifest regenerated. `verify_release.py` now prints individual missing/changed/untracked paths with recovery guidance. For a working checkout, do not delete `python/`, `tests/`, or `scripts/`; install this patch in a new directory instead of overlaying an old checkout.

---

# RAMP-D — Phase 6C-A3 finite SC/rank patch (0.9.2)

This repository contains the current research implementation of RAMP-D. The mathematical specification of record is `AnonymousSubmission2027(1).tex`; implementation history and phase acceptance criteria are in `docs/`.

## Current status

- **Current patch 6C-A3:** restores the broken Phase 4/5 `build_coverage_ledger` export; adds exact finite abstract reach--avoid / terminal-task inner family, non-resettable completion ranks, exact rational completion budgets and optional *conditionally verified* physical margin lower bounds. 13 synthetic mathematical tests pass in an isolated value-carrier environment; real native Phase 4/5 regression is pending the user MPFR build. See `docs/PHASE6C_A3_*.md`.
- **Server Phase 6B report received:** WOMD one real validation record PASS (139 map primitives, no signal entries); AV2 SKIP due missing `pyarrow`. Both datasets have not yet passed together.

- **Phase 6B:** the six earlier 2026-11-16 logs had four test-collection failures and two 25-pass/1-fail parquet-mock runs. The newly uploaded server report has **one WOMD real validation record PASS** and **AV2 SKIP** because the active Python environment lacks `pyarrow`. The missing lower-case validator has been restored, now with strict status + source SHA logging; both real datasets require a fresh server PASS.
- **Phase 6C-A2:** preserves Phase 6C-A's history/future, joint-mode, soft-ranking and simulator-time contracts; adds WOMD/AV2 per-scenario map geometry, WOMD signal timestamps with strict online/label separation, common local coordinates, and versioned silence/deadline evidence. The dependency-free regression now reports **67 passed**. Real datasets/native ABI not tested locally.
- **Cross-phase audit:** change-before-receipt remains hidden; message receipt and local detection remain separate. A bare `silence_exclusion_proved=True` no longer suffices to delete a hidden mode: a versioned deadline/mode evidence object is required. Trust in the external delivery guarantee remains an explicit assumption.
- **Not complete:** native MPFR replay of this patch, user-server real-data dual pass, complete Phase 2–5 formal proof audit, full-horizon optimal `V_H^SC`/CCG, independent proof of communication guarantees, real CARLA/SUMO bridge, predictor training, and closed-loop experiments.

No current report should be interpreted as `full_support_certified=true` or as a real-road safety guarantee.

## Phase 6C-A3 acceptance (requires official MPFR development files)

```bash
PYTHON_BIN=python bash scripts/validate_phase6c_a3_sc.sh
# Creates reports/RAMP-D_Phase6C_A3_server_report.zip; three native CTests
# and Phase 4/5/SC Python regressions are mandatory.
```

## Validation

From the project root, in the server environment:

```bash
# Install the optional parquet readers used by AV2 Motion
pip install -e ".[datasets]"

# Pure contracts (67 tests) + source/geometry/semantic guards.
bash scripts/validate_phase6c_a2.sh

# Real WOMD/AV2 validation: 0 PASS / 3 SKIP / 4 ERROR.
export WOMD_ROOT=/data0/senzeyu2/dataset/waymo_open_dataset_motion_v_1_3_1/uncompressed/scenario
export AV2_ROOT=/data0/senzeyu2/dataset/Argoverse2/motion
MAX_RECORDS=1 bash scripts/validate_phase6b.sh

# Optional legacy Phase 6C-A smoke.
scripts/validate_phase6c_a.sh
```

The Phase 6B script returns exit code `0` for PASS, `3` for SKIP, and `4` for ERROR. A SKIP is not a pass. Dataset roots default to the paths supplied in the project configuration and can be overridden with the environment variables documented in `docs/PHASE6B_ACCEPTANCE.md`.

## Important implementation documents

- `docs/PHASE6B_SIX_LOGS_REVIEW.md` — per-archive diagnosis of six 2026-11-16 Phase 6B runs.
- `docs/PHASE6B_AUDIT_AND_FIXES.md` — data schema, masks, timestamps, and digest contracts.
- `docs/PHASE6C_A_PLAN.md` — Phase 6C-A contracts and RuleNet ordering math.
- `docs/PHASE6C_A2_PLAN.md`, `docs/PHASE6C_A2_IMPLEMENTATION_REPORT.md` — new map/signal, silence-evidence work and acceptance gates.
- `docs/PHASE6C_A_IMPLEMENTATION_REPORT.md` — code changes, tests, and explicit limitations.
- `docs/MATHEMATICAL_AUDIT_PHASE1_5.md` — current cross-phase math audit and unresolved gaps.
- `docs/DATASETS_AND_SIMULATORS.md` — WOMD, AV2, CARLA 0.9.16, and SUMO 1.20 data/integration policy.
- `PROGRESS.json` — machine-readable development status.

## Dataset and simulator policy

Use WOMD `scenario` protobufs as the canonical source for track identity, SDC identity, vector-map and dynamic-map semantics. In AV2 Motion, the official API convention `track_id == "AV"` identifies the ego vehicle; `focal_track_id` remains a separate prediction-target identity. The separate AV2 Map Change dataset is reserved for map-change robustness work.

CARLA/SUMO have not been started by this repository snapshot. Phase 6C-B will require a single orchestrator tick owner, matched fixed time steps, one traffic-light authority, and separate sensor production/delivery timestamps. See the simulator policy before launching experiments.
