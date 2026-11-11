# Phase 3 design: public backup controller

## Scope

Phase 3 compiles the retained Phase 2 information-state witnesses into an
executable public policy graph. A node represents one complete belief support
and contains exactly one common `(jerk, steering_rate)` action. Observation
labels route the node to a retained child only after the observation is
actually received.

The first implementation is the constant-control subclass of the paper's
`u_B + K_B(x-x_bar)` controller (`K_B = 0`). This is deliberate: the action
was already accepted by the Phase 2 robust information predecessor, while a
nonzero gain needs a public-state interval image and a new validated tube
certificate. Such an affine public feedback extension is reserved for the
next verifier-integrated step. Hidden-atom-dependent gains are forbidden.

## Implemented contract

- `BackupControlLimits` validates jerk, steering-rate, state-limit metadata,
  and decision period.
- `BackupMode` labels `brake_to_stop`, `hold_before_gate`, `yield`, and
  `clear_merge`. The label is semantic metadata; it does not assert safety.
- `BackupPolicyGraph` exposes `control(node_id)`, `route(node_id, observation)`,
  and `step(...)`. There is no hidden atom argument.
- `synthesize_public_backup` checks the Phase 2 fixed-point result, selected
  action identity, complete source-atom transition coverage, exact observation
  branch agreement, retained-child closure, and actuator limits.
- `execute_tube` passes one constant public action to the Phase 1 validated
  Picard integrator. A `VALIDATED` tube is a dynamics enclosure only; it is not
  a Phase 3 safety certificate.
- JSON save/replay checks the graph schema, assurance scope, controls, node
  closure, and retained-cell identity.

## Assurance boundary

The output status is `BACKUP_GRAPH_SYNTHESIZED` with
`assurance_scope=PUBLIC_CONTROLLER_SYNTHESIS_ONLY` and `certified=false`.
Protocol automata, complete observation support, resource capacity/conflict
checks, agent tubes, and terminal invariant membership remain Phase 4 work.

Phase 3 uses no AV2/WOMD data and does not require SUMO or CARLA.
