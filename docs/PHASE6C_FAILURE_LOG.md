# Phase 6B => Phase 6C failure, fix and remaining evidence log

| Symptom | Cause | Corrective code | Proof/test state |
|---|---|---|---|
| Original uploaded Phase6B summary SKIP | AV2 validation: `OptionalDependencyError: AV2 parquet parsing requires pyarrow or fastparquet` | `pip install pyarrow` in a compatible target-server environment; parser preserved | **NOT rerun on target server** |
| Original 6B script misleading `PHASE6B_LOCAL_PASS` | Printed pass after incomplete gate | `validate_phase6b.sh` reads JSON status and exits `2` on SKIP/error | Shell lint, local synthetic tests. Real server rerun required. |
| AV2 focal/SDC conflation | `focal_track_id` is a scenario prediction target, not sensor AV | `track_id == 'AV'` as SDC, separate category target selection | Synthetic numeric Parquet-schema fixtures PASS; real Parquet awaited |
| AV2 official category ignored | `TrackCategory.value` is numeric 0..3 | Numeric enum parser | Synthetic regressions PASS |
| Test future remains accessible despite future_available false | Metadata mask did not remove future data | Explicit future-state sanitization and job assertion | Synthetic anti-leakage tests PASS |
| Center -> rear axle conversion invalid across mixed actors | Shared offset and scene-global reference | Individual offsets, erase incompatible center velocity when yaw rate absent, and explicitly reject non-car actors | Synthetic geometry tests PASS |
| Validation-only real sample masks train split readiness | Dataset stages separate | Bound train + validation readers and sample fingerprints | Script built; actual roots unavailable locally |
| Co-sim drift, competing tick owner, missing matching town config | Need one bridge that owns both simulator ticks | Official CARLA bridge wrapper + `CoSimLedger` clock/frame guard | Synthetic ledger PASS; actual co-sim NOT RUN |
| Full Python/CTest native regression unavailable locally | Native `mpfr.h` and compiled `librampd_interval.so` not installed in this container | Target-server validator now requests full Python and CTest | Synthetic module package-loader regression 29/29 PASS; **native not tested here** |
| Revised manuscript winning-set/rank/ICG supervision not implemented | Safety invariant is not task acceptance, labels need oracle | Explicit audit + training source decision; retain UNKNOWN | **Open work**, do not treat 6C smoke as full algorithm acceptance |

## Local result

Command: `bash scripts/validate_phase6c_pure.sh` returned `29 passed` after repairs. This test harness imports the **real** 6A–6C Python modules without initializing unavailable native MPFR `.so`; it neither substitutes a fake MPFR backend nor tests C++/Picard. `python -m compileall` and `bash -n` passed. A full target acceptance gate requires the datasets, real CARLA/SUMO and MPFR development runtime. The local `validate_phase6c.sh` is expected to record `SKIP` or `ERROR` rather than declaring false success.
