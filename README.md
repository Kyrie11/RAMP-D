# RAMP-D — Phase 6C-A2 local validation snapshot (0.9.1)

This repository contains the current research implementation of RAMP-D. The mathematical specification of record is `AnonymousSubmission2027(1).tex`; implementation history and phase acceptance criteria are in `docs/`.

## Current status

- **Phase 6B:** six newly uploaded 2026-11-16 log archives do **not** include real-data acceptance reports: four failed at test collection and two ran 25 pass / 1 failing parquet mock. An earlier project note claimed WOMD 3-record PASS and AV2 SKIP, but that claim was not independently replayed here. The missing lower-case validator has been restored, now with strict status + source SHA logging; both real datasets require a fresh server PASS.
- **Phase 6C-A2:** preserves Phase 6C-A's history/future, joint-mode, soft-ranking and simulator-time contracts; adds WOMD/AV2 per-scenario map geometry, WOMD signal timestamps with strict online/label separation, common local coordinates, and versioned silence/deadline evidence. The dependency-free regression now reports **67 passed**. Real datasets/native ABI not tested locally.
- **Cross-phase audit:** change-before-receipt remains hidden; message receipt and local detection remain separate. A bare `silence_exclusion_proved=True` no longer suffices to delete a hidden mode: a versioned deadline/mode evidence object is required. Trust in the external delivery guarantee remains an explicit assumption.
- **Not complete:** native MPFR replay of this patch, user-server real-data pass, full Phase 2–5 mathematical audit, finite-horizon `W_H^SC`/rank/value/CCG, independent proof of communication guarantees, real CARLA/SUMO bridge, predictor training, and closed-loop experiments.

No current report should be interpreted as `full_support_certified=true` or as a real-road safety guarantee.

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
MAX_RECORDS=1 bash scripts/validate_phase6B.sh

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
