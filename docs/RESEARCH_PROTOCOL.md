# RAPID-AD Stage 1-3 Research Protocol (v3)

## Research questions

- **RQ1 - Failure localization:** Separate scene/setup validity, evidence availability, visible-cue interpretation (manual visual audit and controller logs where available), external decision/action response, and estimated physical recoverability. For black-box policies, do not claim to observe internal belief-update or plan-invalidation time unless the controller exposes those states.
- **RQ2 - Causal interaction:** Test whether control transition, evidence-window timing, and motion/recoverability phase interact to change closed-loop outcomes beyond constituent effects. Use matched seed blocks and realized, not merely requested, intervention timing.
- **Liveness check:** For STOP->GO, measure resumption only after a real release and only if a stable STOP existed before release and the full post-evidence follow-up interval was observed. Static STOP placebo cells have no release latency.

## Factors

### Primary safety task: GO -> STOP

- `control_transition=false`: static PROCEED placebo; `true`: actual PROCEED->STOP transition.
- `phase=early/late`: target estimated stopping margin 5.0 m / 1.5 m. These are *estimated* margins and require vehicle-specific braking calibration before recoverability claims.
- `gap_timing=none/pre/overlap/post`: front-RGB frame hold relative to the phase anchor. Requested duration defaults to 1.0 simulation second. `pre` starts from a finite-difference prediction of time-to-anchor; `overlap` starts half a duration before the anchor and ends half a duration after; `post` starts at the anchor. Actual mask start/end timestamps, duration, cache availability, and number of substitutions are recorded. Cells whose realized timing fails the validity checks are excluded.
- `seed`: shared across matched cells. It pairs the scenario seed, but does not guarantee identical vehicle trajectories across controllers.

### Secondary liveness task: STOP -> GO

- `control_transition=false`: static STOP placebo; `true`: actual STOP->PROCEED release.
- `phase=short_wait/long_wait`: scheduled release anchor at 3 s / 7 s.
- Same evidence timing levels, scheduled in simulation time around the release anchor.
- The liveness branch is analyzed separately from the primary safety branch; its phase means wait duration, not vehicle motion stage.

`core` has 32 cells per seed: 2 tasks x 2 transition states x 2 task-specific phases x 4 evidence windows. `smoke` is a 14-cell integration subset, not a balanced statistical design.

## Evidence intervention semantics

`frame_hold` replays the last unmasked front-RGB frame while the CARLA world and other observation fields continue updating. A fixed one-frame guard is applied after a transition to avoid using a frame captured before the gesture update; this baseline capture guard is common to transition conditions. The intervention is not physical occlusion and does not mask other cameras, LiDAR, maps, or privileged inputs. Multi-sensor policies are not considered exposed to the intervention unless their complete sensor interface is explicitly wired.

The first unmasked front-RGB frame after a transition is an **evidence-delivery timestamp**, not proof that the gesture is visually legible. Diagnostic frames must be manually audited before final causal claims. Black-box model inference wall time does not advance synchronous CARLA simulation time; measured response latencies are simulation-time latencies unless a separate action-delay intervention is implemented.

## Validity rules

1. **Setup valid:** CARLA scene, ego, officer, geometry and actors initialized without setup errors.
2. **Phase anchor valid:** actual anchor falls within the declared phase tolerance (0.75 m for GO->STOP margin; 0.10 s or one tick for STOP->GO schedule).
3. **Exposure valid:** anchor reached, transition command succeeded when requested, frame cache was available, actual mask substitution occurred for requested gaps, and measured mask timing/duration passed checks.
4. **Behavior precondition:** for GO->STOP, the ego was moving before a dynamic transition; for release liveness, a stable STOP existed before release.
5. **Safety-valid:** use valid setup/exposure and require movement before GO->STOP. For STOP->GO, an initial STOP violation remains a safety outcome even if it invalidates the later liveness precondition.
6. **Causal-valid:** require the relevant behavior precondition and measured evidence time for real transitions. Static placebo cells have no true evidence-available time but remain matched controls if their anchor and intervention are valid.
7. **Infrastructure-invalid:** spawn failure, RPC timeout, native crash, missing metrics, server health failure, actor leak, phase-anchor miss, or unrealized evidence intervention. Never score these as policy failures.
8. **Visual audit:** for final interaction estimates, use `make_visual_audit_manifest.py`, fill `audit_pass=yes/no`, and run `analyze_results.py --require-visual-audit --visual-audit-csv ...`. Without this, interaction estimates are provisional.

## Outcomes

- `unsafe_crossing_while_stop`: front bumper crosses the experimental virtual control line while STOP is active. This is a custom proxy line, not a claim about a jurisdiction's legal stop line.
- `stop_success`: dynamic GO->STOP only; sustained near-zero speed with the configured clearance buffer.
- `stale_retention`: dynamic STOP->GO only, after a real release and complete follow-up; vehicle does not resume within the predeclared allowance.
- `right_censored_after_release`: not enough post-evidence simulation time to evaluate the liveness allowance; excluded from liveness causal analysis.
- `unrecoverable_before_evidence`: analytical stopping-margin estimate is non-positive when the first unmasked frame is delivered. This is a model-based estimate, not a formal physical proof.
- `estimated_avoidable_failure`: behavior failure under a positive estimated stopping margin. Treat as provisional unless the vehicle-specific calibration and Oracle solvability checks pass.
- `decision_action_change_latency_*`: available only when the controller exposes decision history; an external action proxy, not an internal plan invalidation timestamp.
- `speed_drop_latency_*` / `speed_increase_latency_*`: physical speed-response proxies, distinct from control-command response.

## Minimum run order

1. Run self-test, preflight, CARLA health, spawn-clear check, and vehicle-specific braking calibration.
2. Run exactly one `rapid_ad_oracle` smoke episode. Inspect status, trace and JPEG diagnostic frames.
3. Run the remaining Oracle smoke cases. Dynamic GO->STOP must stop before the virtual line; STOP->GO must resume after a valid release.
4. Create a visual-audit manifest and verify cue visibility / frame-hold delivery on smoke cases.
5. Run controller smoke tests, one controller per batch, fail-fast.
6. Run core with at least five matched seeds for pilot estimates; more seeds may be needed for stable intervals.
7. Make the visual-audit CSV and require it during final analysis. Report invalid/unexposed episodes separately. Do not make causal claims from a point estimate or fewer than five complete matched seed blocks.

## Interpretation limits

The primary causal analysis is GO->STOP. STOP->GO is a complementary liveness check and has a different phase meaning. The current factor `phase` represents motion/recoverability stage; it does **not** directly manipulate a controller's internal trajectory commitment. The initial scenario has no opposing traffic and uses a virtual line; this isolates the mechanism but does not establish generalization to complete work-zone traffic. Add physical cones/opposing traffic and additional constraint types only after the minimal mechanism is reproducible.
