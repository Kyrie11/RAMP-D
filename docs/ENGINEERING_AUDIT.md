# RAPID-AD v1 Run Audit, v2 Review, and v3 Fixes

## Scope

This audit uses the uploaded `RAPID-AD.zip` run artifacts and the v1 source package. It does not include a live connection to the user's CARLA server. Consequently, simulator-root-cause statements below distinguish observed failures from hypotheses.

## Observed results in the uploaded archive

| Run tag | Planned core cells | Metrics written | Python exception records | Notes |
|---|---:|---:|---:|---|
| `20261025_090445` | 6 smoke cells per controller | 18 total across Oracle/baseline/PID | Batch error record includes one `returncode=-6` | Metrics were written for the six Oracle, six baseline and six PID cases, but one child process terminated abnormally. |
| `20261025_091220` | 48 (16 cells x 3 seeds) | 29 Oracle metrics | 5 | The batch did not complete all planned cells and did not reach all requested controllers. |
| `20261025_092022` | 48 (16 cells x 3 seeds) | 7 Oracle metrics | 19 | Many later cases failed before metric output; the batch is not a valid factorial experiment. |

The uploaded v1 artifacts do not contain child stdout/stderr for the `returncode=-6` process. The exact cause of that signal therefore cannot be identified from the archive alone.

## Confirmed engineering defects

1. **The batch continued after simulator failures.** Later episodes then produced a mixture of `Failed to spawn ego vehicle at the assigned station` and CARLA RPC timeouts. These must be treated as infrastructure failures, not driving-policy failures.
2. **No per-episode child stdout/stderr was retained.** A non-zero exit code was recorded, but the native/Python cause was not diagnosable.
3. **The runner did not check server health and actor cleanup after every episode.** A synchronous-mode leak, stale actor, or stalled server could contaminate subsequent episodes.
4. **`core` was not the full event-order factorial.** v1 core used only `none` and `overlap`; it did not test `pre` and `post`. The full `all` suite contained the three event-order levels, but the uploaded core runs did not execute them.
5. **Static controls had semantically inapplicable metrics.** A static STOP case could show `resume_within_allowance=false` although no release occurred; a static GO case could show `stop_success=false` although no STOP was expected. These values must be null/not-applicable, not failures.
6. **The minimum recoverability margin was taken over the whole episode.** A correctly proceeding vehicle can later pass the virtual line, yielding a negative minimum unrelated to the transition response window.
7. **The phase variable was based on absolute distance.** At 12 km/h, the v1 `late` distance of 9 m still had roughly 4 m of estimated stopping margin in observed traces; it was not a near-boundary-but-recoverable condition.
8. **Recoverability was estimated with an uncalibrated deceleration constant.** v1 named this value `physically_recoverable`, which overstates what was measured. v2 reports an estimate and provides a calibration script; it only marks the estimate calibrated after an explicit calibration run.
9. **The STOP->GO branch began stationary at spawn.** This is acceptable for testing post-release progress, but it does not test stopping from motion. Its `stop_confirmed_before_release` is a liveness precondition, not evidence that the controller handled an approach-to-STOP event.
10. **The `control_transition` event and evidence times were not clearly separated from pseudo-anchors.** v2 keeps static-placebo anchor times but leaves actual transition evidence times null when no real transition occurred.
11. **The visual intervention only holds `observation['image']`.** It does not simulate physical occlusion or mask all possible sensors. This is intentionally documented as a front-RGB stale-frame intervention; do not generalize its result to multi-camera/LiDAR agents without adapting the intervention.
12. **The logs indicate a CARLA path discrepancy.** MARSHAL logged loading its agents package from `/data0/senzeyu2/dataset/CRADrive/CARLA_0.9.15/PythonAPI/carla`, while the configured root provided by the user is `/data0/senzeyu2/dataset/CRADrive/CARLA0.9.15`. This is a warning, not proof of the RPC timeout cause. v2 preflight prints the imported module path and scans MARSHAL's compatibility helper for alternate hard-coded paths.

## v2 safeguards

- Full 32-cell factorial per seed: two tasks x two transition states x two task-specific phases x four evidence windows (`none/pre/overlap/post`).
- `go_to_stop` phases target estimated stopping margins of 5.0 m and 1.5 m rather than hard-coded line distances.
- Static cells are matched placebo controls; actual transition/evidence times remain null when no transition occurs.
- Separate `setup_valid`, `exposure_valid`, `valid_for_safety_analysis`, `valid_for_liveness_analysis`, and `valid_for_causal_analysis` fields.
- Safety failure, post-release stale retention, evidence-before-recoverability-deadline, and invalid exposure are separate outcomes.
- Child stdout/stderr, wall timeout, return code, per-episode status, CARLA health, world sync state, actor count and spawn-clear checks are saved.
- Batch is fail-fast by default. A failed episode or unhealthy server stops the batch.
- Only selected diagnostic frames around the first frame, mask start/end and transition are saved; full PNG sequences are not required.
- Interaction estimates use complete matched seed/run blocks and bootstrap across blocks. Fewer than five independent blocks are explicitly flagged as underpowered.

## What remains unverified

- Whether the user's CARLA 0.9.15 server stays responsive for repeated episodes after the v2 cleanup checks.
- Whether the configured spawn transform is clear on the live Town03 world.
- Whether the actor's rendered gesture is visible and the control line is geometrically sensible in the saved diagnostic frames.
- Whether the 5.0 m and 1.5 m target margins are physically recoverable under the exact vehicle, weather, and friction settings. Run `scripts/calibrate_braking.py` and require the privileged Oracle to pass the relevant cells.
- Whether any non-privileged strong controller exhibits the hypothesized failures. The uploaded results do not establish this: only a small v1 smoke subset and incomplete Oracle-only core runs were recorded.

## What the six-cell v1 smoke subset actually suggests (not a research result)

The six-cell smoke subset per controller contains only two dynamic GO->STOP cells (late/no-gap and late/overlap), one static GO placebo, two dynamic STOP->GO cells (short/no-gap and long/overlap), and one static STOP placebo.

- The privileged `rapid_ad_oracle` stopped without crossing in both dynamic GO->STOP cells and resumed after both dynamic STOP->GO releases. This supports the narrow claim that these two tested instances were operationally solvable for that privileged controller.
- The route-following `baseline` and `pid` controllers crossed the control line in both dynamic GO->STOP cells. These controllers do not interpret the flagger's visual directive, so this is an expected lower-bound sanity check, not evidence that a strong vision model has the target failure.
- In one baseline GO->STOP cell, the v1 estimated margin at evidence availability was negative, while PID margins were positive (about 4.0 m and 2.9 m) despite unsafe continuation. Since the braking model was not calibrated and the phase was distance-based, this contrast is only a diagnostic hint.
- The STOP->GO baseline/PID runs include cases where the initial STOP was never established. Those are STOP-compliance failures, not stale retention after release. v2 keeps these separate from the liveness denominator.

No PNG frames were necessary to identify these metric/runner defects. Selected frames are still needed after the v2 smoke run to verify that the flagger gesture is visible, the frame-hold intervention actually presents a stale image, and the virtual control line is geometrically sensible.


## Additional v2 defects fixed in v3

The v2 source review found that the GO->STOP `pre/overlap/post` input-mask windows were still scheduled mainly by spatial stopping-margin ranges, so realized duration could vary with controller speed. A missing image cache could also be passed through while the episode was still marked exposed. The v2 liveness branch could label an episode as stale retention without a complete post-release observation window, and the interaction analyzer could mix v2 and v3 semantics.

v3 schedules evidence windows relative to the phase anchor using measured simulation time (with a predicted time-to-anchor only for pre-anchor starts), validates realized duration and ordering, excludes cache misses and phase-anchor misses, marks incomplete release follow-up as right-censored, and only uses schema-v3 episodes for factorial interactions. It adds a manual visual-audit manifest and a run-health summary script.

These are static code fixes only. No live CARLA 0.9.15/MARSHAL end-to-end run was performed in the package-building environment. The user must still validate the gesture visibility and timing in diagnostic JPEGs before making research claims.
