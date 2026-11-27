# RAMP-D — 1.0.0.dev0

Phase7A factual-learning pilot on the same maintenance baseline derived from A75. This implements a minimal trainable joint-motion model and data contract, not the full paper architecture, a Phase6C exit certificate, a trained production model, or a real-vehicle safety approval.

## Start here

- [Current Phase7A pilot implementation and acceptance](docs/PHASE7A_PILOT.md)
- [Phase7A server commands](docs/PHASE7A_SERVER_RUNBOOK.md)

- [Cleanup and A75 evidence review](docs/CLEAN_RELEASE_REPORT.md)
- [Current Phase6C / Phase7–10 implementation roadmap](docs/PHASE7_TO_10_ROADMAP.md)
- [Module catalog (including scope and historical roles)](docs/MODULE_CATALOG.tsv)
- [Exact migration table](docs/CLEANUP_MIGRATION.json)
- [Head-specific supervision contract](docs/A75_SUPERVISION_CONTRACT.md)
- [Original paper](manuscript/AnonymousSubmission2027.tex), unchanged
- [Historical A75 README](docs/history/README_A75.md), original bytes; historical commands may refer to tools in the separate archive. Other historical docs and gates remain at their existing paths.

## Installation / regression

Unpack this release into a **new empty directory**. Do not overlay it on A75.

```bash
python scripts/verify_release.py
bash scripts/validate_cleanup_regression.sh
# Native gate on a server with MPFR and GMP development headers:
cmake -S . -B build_clean -DCMAKE_BUILD_TYPE=Release
cmake --build build_clean -j 4
export A5_NATIVE_BUILD_DIR="$PWD/build_clean"
export RAMPD_INTERVAL_LIB="$PWD/build_clean/librampd_interval.so"
bash scripts/validate_native_regression.sh
```

The second command is the isolated pure regression, not the Native gate. The last command delegates to the existing A75 conditional gate and preserves its expectations; even a PASS does not establish complete SC. The public package imports lazily: data and learning modules do not require Native. Native numerical operations and certificates still require the actual backend. No numerical fallback is added. The previous proof formats and schema versions are retained.

## Phase7A commands

```bash
bash scripts/validate_learning_pilot.sh
python scripts/prepare_factual_dataset.py --help
python scripts/train_factual.py --help
python scripts/check_rule_overlay.py --help
python scripts/check_cosim_map.py --help
```

## Stable command-line names

| Purpose | CLI (arguments unchanged) |
|---|---|
| Raw WOMD record format | `python scripts/womd_format_probe.py --help` |
| Small WOMD inventory | `python scripts/womd_scenario_inventory.py --help` |
| Factual scoped export | `python scripts/export_factual_labels.py --help` |
| Waymax IDM paired diagnostic | `python scripts/waymax_idm_pairs.py --help` |
| CARLA actor trials | `python scripts/carla_actor_trials.py --help` |
| CARLA repetition audit | `python scripts/carla_campaign.py --help` |
| SUMO logical corridor | `python scripts/sumo_corridor_probe.py --help` |
| SUMO sampled audit/export | `python scripts/sumo_sampled_replay.py --help`, `python scripts/export_sumo_sampled_labels.py --help` |
| ROADWork strict site / visual binding | `python scripts/roadwork_site_split.py --help`, `python scripts/roadwork_bind_split.py --help` |
| ROADWork visual extraction / 511NY normalization | `python scripts/roadwork_visual_pipeline.py --help`, `python scripts/normalize_511ny.py --help` |
| Native multi-actor local proof gate | `python scripts/native_multi_actor_microcase.py --help` (requires Native library) |

Stable name does not mean production-ready. For example `native_multi_actor_screen` is a necessary, conditional screen, `affine_resource_monitor` is scoped to translating rectangles, and `finite_wait_reference` is a finite model oracle. Keep these boundaries in all downstream code.

Legacy `aXX_...` imports for migrated core modules resolve to the same module object through compatibility aliases. Old CLI names delegate to the semantic commands; argument and artifact formats stay the same. Some legacy implementations retain their filenames because historical tests load them directly or they are reference-only. For new code use the names in the module catalog. Restore archived diagnostic scripts only in the original A75 checkout. Do not merge the history ZIP into this release.

## Active engineering boundary

The final planner, complete Native multi-actor SafeTube/Succ/SC integration, synchronized shared-resource incident runs, full split registry, all eight label adapters and learned model remain to be completed. Use log/vector-token inputs for the main planning model. Rendered images are for the observation adapter/robustness evaluation, not a prerequisite for training all eight heads.

## Phase7A follow-up
See [follow-up scope](docs/PHASE7A_FOLLOWUP.md). Fixed query-grid factual features, CV initialization and epoch-zero selection, future-only incident schedule replay, isolated event-clock likelihood. No simulator response or SC authorization.

## Phase7A / 7B response checkpoint
See `docs/PHASE7A_FOLLOWUP.md`. Optional `--objective radial_laplace`, `--selection ade`, fixed-validation training extension, projected longitudinal rule-response diagnostic (`scripts/run_rule_response.py`). No full-scene CF/physical/SC authorization. Same development version; earlier scripts remain compatible.

## Current Phase7AB motion / rule checkpoint

- [Acceptance and actual evidence](docs/PHASE7AB_MOTION_RULE_ACCEPTANCE.md)
- [Server runbook](docs/PHASE7AB_MOTION_RULE_RUNBOOK.md)
- [Optional manuscript evaluation-metric clarifications](docs/metrics_proposed.diff)

Motion-context, residual-gate and query-mode flags are isolated. Formal SC and physical resource labels remain unauthorized.

## Current Phase7AB motion / response checkpoint

- [Acceptance and actual evidence](docs/PHASE7AB_MOTION_RESPONSE_ACCEPTANCE.md)
- [Server runbook](docs/PHASE7AB_MOTION_RESPONSE_RUNBOOK.md)

Optional actor-local history, CV anchor and shared per-mode scorer; independent weak motion and damped CA diagnostics, fresh official development manifest, projected rule sensor/response clocks and 2D sampled ribbon diagnostics. No formal SC or real counterfactual authorization.

## Current Phase7AB factual freeze / shared resource checkpoint

See `docs/PHASE7AB_FACTUAL_FREEZE_ACCEPTANCE.md` and `docs/PHASE7AB_FACTUAL_FREEZE_RUNBOOK.md`.
Factual architecture candidate: motion-context + actor-local history + CV residual + radial Laplace; preserve older flags/checkpoints. New optional scene-level mode-quality auxiliary (default off), extended factual audit, route geometry ledger, versioned report/declared device cohort, projected evidence v2. Executable declared affine 2D shared corridor and separate model-domain Event/Occupancy/Observation head pilot; no real simulator or Native SC claim.
