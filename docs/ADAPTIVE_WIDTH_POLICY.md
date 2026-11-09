# Adaptive local tube-width policy (Phase 1C)

## 1. Purpose and scope

Phase 1B accepted a substep when its Picard self-inclusion was proved. That is
necessary for a sound local flow enclosure, but a successful enclosure can
still be too coarse for downstream geometric predicates. Phase 1C adds a
separate resolution policy: after Picard inclusion succeeds, measure the
coordinate diameters of the local tube box. If any configured cap is exceeded,
reject that candidate *for resolution purposes*, bisect the time interval, and
recompute both children.

This is not a new physical constraint and is not a collision test. It must not
be interpreted as a safety margin.

## 2. Width definition

For a closed interval `X_i=[l_i,u_i]` whose endpoints are finite binary64
numbers, define

`width_i(X) = exact_real(u_i) - exact_real(l_i)`.

The implementation maps each endpoint to its exact rational value using
`Fraction.from_float` and subtracts exactly. Thus width comparison cannot
underflow/overflow or round across a configured cap. Certificate schema v2
stores the exact rational numerator/denominator pair for every coordinate.

Coordinate order and units:

| Index | State | Unit | Cap meaning |
|---:|---|---|---|
| 0 | `px` | m | maximum x-coordinate span in one local tube |
| 1 | `py` | m | maximum y-coordinate span in one local tube |
| 2 | `psi` | rad | maximum heading span in one local tube |
| 3 | `v` | m/s | maximum speed span in one local tube |
| 4 | `a` | m/s^2 | maximum acceleration span in one local tube |
| 5 | `delta` | rad | maximum steering-angle span in one local tube |

The measured span includes the actual coordinate movement over the substep,
initial support uncertainty, propagated uncertainty, and interval enclosure
inflation/dependency. It is deliberately not labelled as pure numerical error.

## 3. Acceptance rule

For configured positive finite caps `c_i`, an accepted local segment must obey

`width_i(Z) <= c_i` for every state coordinate `i`.

Equality is accepted. No epsilon is added. The Picard proof remains mandatory:

`Z0 + [0,h] F(Z,U,W) subset int(Z)`

and the endpoint enclosure remains

`Z+ = Z0 + h F(Z,U,W)`.

The width test is applied only after the candidate Picard witness has passed
inclusion. A candidate failing the width test is not appended to the output
segment list. It is bisected and both halves are recomputed from the correct
initial/endpoint boxes.

## 4. Why subdivision may not help

Subdivision reduces the time-local range traversed by the state and often
reduces interval dependency. It does not remove true uncertainty. If the initial
support diameter already exceeds a configured cap, no time split can satisfy
the cap at time zero; the algorithm returns `UNKNOWN: INITIAL_WIDTH_LIMIT`.
Likewise, if genuine uncertainty grows beyond the cap, the algorithm eventually
hits a minimum-step/depth/split/attempt/time budget and returns `UNKNOWN`.

No width-policy failure is a physical counterexample. No successful width
policy proves the system is collision-free or lawful.

## 5. Cost controls

- `max_width_subdivisions`: maximum additional bisections specifically caused
  by an already-validated but too-wide candidate.
- `max_steps`: accepted segment budget.
- `max_attempts`: total Picard trial budget.
- `max_depth`: maximum bisection depth.
- `min_step_s`: minimum permitted child step.
- `time_limit_s`: wall-clock budget.

The split tree is processed left-to-right. The left child is fully validated
before its endpoint becomes the initial set for the right child. Exact rational
bookkeeping of binary64 durations prevents gaps or overlap in the requested
horizon.

## 6. Certificate and replay

Schema `rampd.picard-tube.v2` records the options and exact local widths. Replay
recomputes every Picard witness, every segment width and the configured cap
check. Schema v1 remains accepted for historical Phase 1B certificates; it has
no width-policy claim.

The replay implementation shares the MPFR interval arithmetic backend with
search. It is an independent search-path replay, not a separately implemented
arithmetic proof checker.

## 7. Benchmark interpretation

The benchmark uses one deterministic synthetic bicycle case and compares:

1. fixed coarse schedule, no width caps;
2. fixed fine schedule, no width caps;
3. coarse initial schedule with adaptive local width caps.

It records accepted segments, attempts, bisections, width rejections, maximum
per-coordinate local tube widths, width-cap ratio, witness replay and median
wall time. Timing is descriptive and machine-dependent. The benchmark is not
an AV2/WOMD experiment, not a CARLA/SUMO experiment, and not a real-vehicle
performance claim.
