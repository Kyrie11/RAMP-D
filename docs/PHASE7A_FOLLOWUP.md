# Phase7A / Phase7B projected response checkpoint (same 1.0.0.dev0)

Scope: factual training and declared projected longitudinal response. Not a full dynamic WOMD world, physical resource, full REA, or SC proof. No new authorized event/causal/CF labels.

## Fact learning
- Preserve CV initialization and old checkpoint compatibility. Gaussian shared-scene mixture remains baseline; optional proper radial Laplace density and independent NLL/ADE model selection. Report Gaussian likelihood even with radial training, and radial likelihood separately.
- Strict baseline recomputation, logit/mask shape checks, unknown-only rows excluded; event loss checks only active rows. Module gradient norms, scene mode spread/posterior diagnostics. `prediction_beats_cv_ADE` now requires strict improvement; equality reported separately.
- `prepare_factual_dataset.py --base-manifest ...` extends train roster while preserving exact validation and original train IDs. No global geographic/log-family guarantee. Revalidate raw bytes on prepare. Existing cache 50/10 is usable; raw future sample alignment remains approximate.
- Do not turn a factual candidate query into a do-intervention. No new active loss other than joint.

## Incident contract
1. Real history cutoff; source family, split, record hash and current frame. No retroactive rule injection without regenerated history.
2. Condition event type on geometry/traffic, use 511NY/ROADWork/WZDx for weak source priors only. Distinguish actual legal scope and proposed geometry.
3. Plan rule interval, actual effectivity, issue/publication, recipient-specific receipt and detection, physical activation/clearance, cancellation/version, authority. The current scheduled proposal assumes planned=actual, newly declared projected Closure explicitly separates them. No physical ACK inferred; no detection implemented.
4. All currently valid recipients explicitly represented in proposal; None means no scheduled receipt in declared world, not proof of unawareness. Only own receipt available to behavior at next fixed control tick. Hidden actual clock used only in entry audit. No update at a hidden clock that changes the numerical response policy.
5. New longitudinal corridor `datasets/incident_response.py`: restrictive 1.25m projection, heading dot>=.9, >=25m route, >=2 aligned vehicles, 8m closure region ahead, existing footprint occupants allowed to leave, no instantaneous stop. Nominal/cautious headway variants; A/AA/B ego pair, NO_EVENT separate rule intervention. Bounded scalar acceleration model, not calibrated dynamics or 2D occupancy. Stops at model route end or sampled/order crossing. Near time boundary UNKNOWN. No lane changes, births, traffic signal compliance, physical barriers, complete roster or legal authority evidence.
6. Source-bound cache + proposal replay can reconstruct *current* states, but cannot independently verify full map or raw roster. New spec reassigns receipts for the projected subset. No original future target read. Raw Scenario path separately supported.
7. `audit_pair` checks discrete kinematic recurrence, roster, message/effectivity, occupancy, A/AA, A/B exogenous consistency and mask. It is not an independent controller oracle or continuous safety proof. Source/candidate and actual physical resource still required. Plot is diagnostic only.
8. Keep all simulated training masks off until model/domain and target validation; formal SC still separate Native pipeline. Real factual learning can proceed independently.

## Next acceptance
- Enlarge training to 200/10 fixed validation (or larger separate validation set frozen before tuning), compare K1/K3, Gaussian/radial on identical split and seeds. No final test-set selection. Keep CV if no gain. Evaluate low-speed/moving groups, scene-level errors, mode calibration, NLL and ADE/FDE. Treat small pilot as diagnostic.
- Raw Scenario projected response: at least one complete horizon, A/AA, nontrivial ego response and separate nontrivial event response, trace replay, record rejection/route truncation. Expand mapped route through validated successors rather than silently extrapolate. Then SUMO/CARLA physical lane polygon, controls, observation, actor roster and execution ACK. Projected data cannot authorize these targets.
- Event/observation: exact or censored clock labels only with actual evidence; schedule-only labels explicitly conditional and never real timing. Use structure (external invariance and flow mediation) before adding model-specific causal losses. Full eight-head learning and Native SC pending.
