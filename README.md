# Latest increment: Phase 6C-A5/3b-4 (0.9.9)

See `docs/PHASE6C_A5_3B4_ACCEPTANCE.md` and `docs/PHASE6C_A5_3B4_SUPERVISION.md`. Run `bash scripts/validate_phase6c_a5_3b4.sh` in a fresh checkout. Previous 3b-3 server report failed before tests; no native success implied.

# RAMP-D 0.9.8 · Phase 6C-A5/3b-3

A5/3b-2 已通过服务器限定验收（566 Python / 3 native）；WOMD+AV2 四个有界 split 全部通过。A5/3b-3 实现受限连续 incumbent/no-entry 证明、单次不确定事件时钟、声明有限消息分组、施工报告绑定、连续 clearance reference controller、MUTCD table guidance 和独立 ROADWork / Waymax audit。154 isolated、29 finite、13 SC 本地通过。新原生证明与真实 ROADWork/Waymax 待服务器。完整真实场景、消息协议、形式化 Teacher、模拟标签和训练尚未完成。

```bash
python -m pip install -r requirements-test.txt
python scripts/verify_release.py
bash scripts/validate_phase6c_a5_3b3.sh
```

见 `docs/PHASE6C_A5_3B3_ACCEPTANCE.md`（数学、失败分析、命令）和 `docs/PHASE6C_A5_3B3_SUPERVISION.md`（数据/时钟/后续方案）。在新目录解压。当前不要求 CARLA/SUMO 运行。

---
历史版本说明（以下 PASS 仅对应当时发布）：

# RAMP-D 0.9.7 · Phase 6C-A5/3b-2

基于用户已验收的 A5/3b 第一增量（550 Python + 3 native）。本轮新增 AV2 binary64 endpoint 兼容性审计、声明移动 actor 连续传播、计划施工 clearance 身份绑定、Incident/TIM 参考契约、WZDx CSV inventory。论文未修改。141 独立数据/协议测试、29 finite、13 SC 本地通过，原生新增测试与真实 AV2 仍须服务器验证。不要把本轮当作真实世界完备证书或训练标签生产完成。

```bash
python scripts/verify_release.py
bash scripts/validate_phase6c_a5_3b2.sh
```

在同一 mfrp 环境运行真实数据 gate（先选单个真实 AV2 Parquet）：

```bash
AV2_ROOT=/data0/senzeyu2/dataset/Argoverse2/motion
AV2_FILE="$(find "$AV2_ROOT" -type f -name 'scenario_*.parquet' -print -quit)"
python scripts/validate_av2_arrow_timestamp.py --parquet "$AV2_FILE" --output reports/a5_3b2_av2_timestamp.json
python scripts/validate_a5_logged_labels.py --womd-root /data0/senzeyu2/dataset/waymo_open_dataset_motion_v_1_3_1/uncompressed/scenario --av2-root "$AV2_ROOT" --max-records 60 --max-files 6 --prefix-steps 10 --output reports/a5_3b2_logged_labels.json
```

WZDx `scripts/audit_wzdx_inputs.py --registry FILE --event-csv FILE --schema SOURCE_ZIP_OR_REPO_ROOT --output reports/a5_3b2_wzdx.json`；真实 CSV 已本地验收，不生成精确事件标签。详见 `docs/PHASE6C_A5_3B2_ACCEPTANCE.md` 和 `docs/PHASE6C_A5_3B2_SUPERVISION.md`。

---

历史说明如下（其阶段范围与当前版本不同）：

# A5/3b first increment (current release)

Run `bash scripts/validate_phase6c_a5_3b.sh`. See `docs/PHASE6C_A5_3B_ACCEPTANCE.md` and `docs/PHASE6C_A5_3B_SUPERVISION.md`. Scoped declared ego-only proof; original full-support and real-policy guarantees are not completed. A5/3a server passed 528 Python and 3 native tests. This increment local 128 dependency-free, 29 finite, 13 SC; native and actual data server gates pending.

# Phase 6C-A5/2 (current release)

**Scoped only; native server validation pending.** A5/1 Hotfix1 server baseline 470 Python tests and 3 CTest tests passed. New rational-time endpoint and composed static finite-tail proof, resource direction and label provenance. See [A5/2 acceptance](docs/PHASE6C_A5_2_ACCEPTANCE.md) and [eight-loss plan](docs/PHASE6C_A5_2_SUPERVISION_PLAN.md). Extract to a fresh directory, `python -m pip install -r requirements-test.txt`, `python scripts/verify_release.py`, `bash scripts/validate_phase6c_a5_2.sh`. No simulator or real dataset needed for the math gate. Optional real-data smoke is separate.

---

## CURRENT RELEASE: Phase 6C-A5/1 — model-relative evidence gate

**Not a full-support certificate.** See `docs/PHASE6C_A5_1_DESIGN_AND_ACCEPTANCE.md` for the scoped implementation, native test gate and server commands. The sections below document previous releases and are retained for history.

---

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

## Phase 6C-A5/1 incremental proof gates (current release)

The latest TeX is already bundled verbatim under `manuscript/`.
A5/1 adds **model-relative** finite task-tail AND/OR auditing, bounded
synthetic physical/protocol replay adapters and a repaired native CTest gate.
It does NOT complete A5 terminal-tail proof integration or enable real-world
full-support certification. Read `docs/PHASE6C_A5_1_DESIGN_AND_ACCEPTANCE.md`
and `docs/PHASE6C_A5_SUPERVISION_AND_SIM_RESEARCH.md`.

On the target server, extract into an **empty** directory, install dependencies,
run `python scripts/verify_release.py`, then
`bash scripts/validate_phase6c_a5.sh`. The script builds a dedicated fresh native
MPFR core and runs mandatory tests. If AV2 Parquet remains SKIP, install
`requirements-data.txt` into the active environment, then run the existing
Phase6B/6C sample data gates separately.

### A5/1 hotfix 1

See [hotfix acceptance](docs/PHASE6C_A5_1_HOTFIX_ACCEPTANCE.md). This is an A5 release, not A6. A5World v2 requires explicitly declared ego parameters, derivative disturbance, control bounds and friction-enabled safe domain; regenerate model/evidence digests. Run `bash scripts/validate_phase6c_a5.sh` in a fresh directory.


## Phase 6C-A5/3a (scoped release)

See `docs/PHASE6C_A5_3_ACCEPTANCE.md` and `docs/PHASE6C_A5_3_SUPERVISION_PLAN.md`.
Run `python scripts/verify_release.py` then `bash scripts/validate_phase6c_a5_3.sh`. The full gate requires native MPFR/GMP; no real-world full-support claim.

`python scripts/validate_a5_logged_labels.py --womd-root /data0/senzeyu2/dataset/waymo_open_dataset_motion_v_1_3_1/uncompressed/scenario --av2-root /data0/senzeyu2/dataset/Argoverse2/motion --max-records 60 --max-files 6 --prefix-steps 10 --output reports/a5_3_logged_labels.json`

Optional Waymax in compatible environment: `python scripts/probe_waymax.py --tf-example-file /data0/senzeyu2/dataset/waymo_open_dataset_motion_v_1_3_1/uncompressed/tf_example/validation/validation_tfexample.tfrecord-00000-of-00150 --output reports/waymax_probe.json --plot reports/waymax_logged.png`. Supply an actual local WOMD 1.3.1 TFExample shard; no counterfactual or safety certificate is generated.
