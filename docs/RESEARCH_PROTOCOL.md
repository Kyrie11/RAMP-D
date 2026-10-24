# RAPID-AD Research Protocol (Stages 1-3)

## What the first implementation can establish

1. **Engineering validity**: CARLA/MARSHAL can execute the same fixed scenario under multiple controllers and save aligned state, gesture, frame, and control logs.
2. **Stimulus validity**: the control transition is actually issued at the intended distance/time; the evidence mask has the intended ordering; the vehicle reaches the target phase; the oracle can stop/resume within the defined physics envelope.
3. **Behavioral replication**: a non-privileged controller repeatedly violates STOP or retains STOP after a valid release, under valid and physically recoverable episodes.
4. **Mechanism localization**: only if the controller exposes suitable decisions/logs or controlled interventions can we distinguish perception/evidence delay from decision/plan response delay. For black-box controllers, report observable behavior only.

## What it cannot establish by itself

- A failure in one controller or one fixed Town03 spawn does not establish generality.
- Frame holding is not equivalent to physical occlusion; it isolates evidence availability but requires a later physical-occluder check.
- A stop-line violation is a safety-relevant behavior proxy, not proof that a collision would occur in real traffic.
- A positive three-factor interaction estimate from a handful of runs is not sufficient for a causal claim.

## Valid episode criteria

An episode is eligible for the main causal comparison only if:

- CARLA client/server versions match;
- the officer and camera were spawned and the initial directive is visually present;
- the control line geometry is valid and the phase anchor is reached;
- the directive transition actually occurs when the case requires it;
- the vehicle is moving before a GO-to-STOP transition, or it has demonstrably stopped before a STOP-to-GO release;
- the evidence-time recovery margin is positive for an avoidable-revocation claim.

Invalid or unexposed episodes must be reported, not silently dropped. Report both the overall rate and the rate conditional on these criteria.

## Failure taxonomy

- `unsafe_continuation`: front bumper crosses the control line while STOP is active.
- `stop_not_completed`: the transition occurred, the vehicle was moving beforehand, the recovery margin was positive, but no sustained stop was achieved.
- `unrecoverable_before_evidence`: the estimated safe stopping margin was already non-positive when the relevant frame became available.
- `decision_after_recovery_deadline`: the first observed fresh-image decision occurred after the estimated recovery margin became non-positive.
- `initial_stop_not_established`: STOP-to-GO release occurred without a sustained pre-release stop; not a stale-retention result.
- `stale_retention`: a sustained stop was established, a valid release occurred, but the controller did not resume within the configured response allowance.
- `not_exposed_moving` / `anchor_not_reached`: the policy never entered the intended motion phase, so it cannot be used to infer plan revocation under motion commitment.

## Recommended evidence hierarchy

1. Oracle success on every cell: necessary physics/scene check.
2. Matched static controls: prove each stable control state is understood/obeyed.
3. Transition cells without evidence gap: isolate control-state transition.
4. Gap-only static controls: isolate observation intervention.
5. Transition + gap: test interaction.
6. Pre/overlap/post order cells: test event-order sensitivity.
7. Repeats and a second controller family: test reproducibility.
8. Physical occlusion and a second map/control type: external validity.
