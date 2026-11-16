# Phase6C-A3 + offline prediction gate: integrated release 0.9.3

**Scope:** engineering consistency repair and bounded dataset diagnostics. The paper revision is identical (SHA256 `0d9b8e50fd8c0f8aaa89f9979b33c6905211b9f16ed5caa6e388be1d3ca76621`) across the supplied `(1).tex`, `(2).tex`, and the original 6C manuscript snapshot. Do not infer new mathematical commitments from filename suffixes.

## 1. Goal, implementation, tests, failure analysis, acceptance

**Goal:** repair the Phase4/6B/6C server collection failure caused by a hybrid of old 6C baseline and A2/A3 tests; fix WOMD time-axis scoring, close the AV2 numeric-category regression, keep the A3 finite SC/rank implementation, and report truthful native/data/simulator gates.

**Integrated code:** newest A3 tree is the base. Older 6C files are preserved as an `offline-only` candidate: `phase6c_cv.py`, `clock_ledger.py`, `evaluate_phase6c.py`, and optional `smoke_phase6c_cosim.py`. The A3 public APIs remain authoritative (`protocol`, `map_context`, `safe_continuation`, advanced RuleNet interfaces). Newly added `iter_womd_split` and `iter_av2_split` read train and validation with the split properly forwarded into manifests. `supervision_inventory` identifies legal label sources and missing oracle/protocol labels.

**Server evidence reviewed:**

- Phase3 report: original native CTest 3/3 passed, then Python collection stopped on three missing symbols (`MapVertex`, `public_observation_window`, `SilenceExclusionEvidence`). Thus Phase4 was NOT accepted.
- Phase6B report: WOMD validation sampled 3 real scenes, PASS for the reader; AV2 SKIP because its parquet engine was absent. Overall SKIP.
- Phase6C report: 29 synthetic tests passed; full pytest had the same 3 import errors. WOMD train/val both ERROR (`prediction and truth time axes differ`); AV2 train/val SKIP (missing parquet engine); co-sim SKIP. Native CTest said `No tests were found!!!` but returned 0; this is **not** a native pass. Overall ERROR.

**Corrections:**

1. **Reproducible unified source.** A3 module exports and tests are shipped together with the offline baseline, not overlaid onto an older tree. A SHA256 manifest and `verify_release.py` reject files missing/changed and extra source files from an accidental overlay. Phase4/6C validator invokes this gate.
2. **AV2 numeric categories.** Official Parquet encodes category as the integer 0..3. Map `2 => SCORED_TRACK`, `3 => FOCAL_TRACK`; keep `focal_track_id` conceptually separate from `AV` ego identity. Missing benchmark targets now cannot falsely produce an empty-score diagnostic.
3. **Offline temporal scoring.** The original function permitted ~1% jitter in input sampling but required `<=1e-5` seconds exact equality at every target index. The corrected evaluator uses the *label* timestamp to interpolate the predicted trajectory on its own time axis, enforcing slot-offset strictly less than `0.45*dt`. When necessary it uses bounded endpoint velocity extrapolation; invalid prediction/GT masks remain invalid. It records maximum offset and number of resampled steps. This is **only for logged-action offline ADE/FDE**, not reachability verification, MPC safety, or the official challenge metric.
4. **Per-scene errors.** The data gate now retains the successful scenario rows and explicitly reports `failure_cases`; one later error cannot erase previously inspected evidence or make a partial split PASS.
5. **CTest discoverability.** Native regression requires `interval_cpp`, `picard_cpp`, `abi_cpp`, at least 3 discovered tests, 100% success with 0 failures. `ctest` returning 0 with no tests is rejected.
6. **Loss source audit.** The dataset `observed` bit is NOT an observation/awareness label. Logged traffic light states are auxiliary signal-state supervision, NOT certified rule activation/effectivity or message delivery. Formal viability, margins and deadlines are masked until evidence generation.

## 2. Actually measured in this environment

| Gate | Result | Meaning |
|---|---|---|
| A2/A3 data/protocol/map + CV + release/supervision tests | **84 passed** | Python 3.13 synthetic fixtures only; independent of MPFR |
| A3 finite SC discrete/rank tests via synthetic value carrier | **13 passed** | Exercises finite combinatorial SC/rank code, **not** MPFR or physical proof |
| Python compileall and validator bash syntax | **PASS** | Static validation only |
| Full native MPFR, full Phase0–5 pytest | **UNAVAILABLE** | Official MPFR header and user compiled library absent here |
| Real WOMD / AV2 readers and predictor ADE/FDE | **NOT RUN** | `/data0/...` datasets not mounted in this environment |
| CARLA/SUMO closed-loop smoke | **NOT RUN** | User's server simulators unavailable here |

No server real-data fix has been confirmed by these local tests. A result is not certified task reachability, RuleNet training, or a complete Phase6C implementation.

## 3. Correct server sequence

**Extract into a brand-new empty directory. Do not unzip over `/home/senzeyu2/code/RAMP-D`** (it already had A2/A3 tests beside an older 6C implementation). From the extracted root:

```bash
conda activate mfrp
python -m pip install -r requirements-test.txt
python -m pip install -r requirements-data.txt
python scripts/verify_release.py
bash scripts/validate_phase6c_pure.sh
# Compiles native library (if needed) and runs the full historical regression:
bash scripts/validate_phase4.sh
# The case-sensitive basename is deliberately lowercase:
MAX_RECORDS=3 bash scripts/validate_phase6b.sh
MAX_RECORDS=3 bash scripts/validate_phase6c.sh
```

If `validate_phase6c.sh` ends in `SKIP` because no CARLA/SUMO config is set, **the dataset gate and full Python/CTest results are still valuable**. Do not turn off the full regression just to obtain PASS. For co-sim, launch headless CARLA 0.9.16 on 2000 and explicitly configure a matching `SUMO_CONFIG`, `CARLA_COSIM_DIR`, `SUMO_HOME`; run only one tick owner. The sync smoke is clock/alignment only, not scene-planning verification.

The principal upload for the next iteration is `reports/RAMP-D_Phase6C_server_report.zip`; also upload `reports/RAMP-D_Phase6B_server_report.zip` if the AV2 reader fails after installing pyarrow. Include the Phase4 report folder if it fails before data checks.

## 4. Maths audit / unsolved modules

The paper's `S_infty` (can remain safe) and `W_H^SC` (has a task-completing safe continuation) are not equivalent. A3's finite SC/rank uses exact rational time/rank arithmetic and admits cells only given **externally replayed** full-tube/branch-cover/terminal-tail obligations. Synthetic callback `True` is not a physical certificate. `SCResult.certified_full_support` deliberately remains false. Any failed local search is `UNKNOWN`, not a negative viability label.

Deadline calculation requires a common candidate ego control prefix for both `T_sep,+` and `D_defer`. Neither quantity may be constructed from average latency, nominal predicted trajectories, or the backup stopping time alone. Formal CCG resource/product graphs and controllable policy-tree scheduling still need implementation.

**Next phase:** once Phase4/6B/6C bounded data gates run cleanly, connect replayable Phase4 full-support tube and protocol/observation evidence to the A3 SC kernel; implement verified terminal tail and inherited rank budget across real replanning. Only then implement coarse/refined CCG, interval ICG and dynamic scheduling. Learned conditional joint prediction and RuleNet should use established supervised provenance and remain search-order heuristics, never hard-support truncation. A CARLA/SUMO closed-loop planning benchmark follows after this evidence integration, not as a substitute.
