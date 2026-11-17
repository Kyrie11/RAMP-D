# Phase 6C-A5/3b first increment — acceptance

## Baseline and target
Uploaded A5/3a server report: native 3/3, finite 29, data 112, mathematical 140, full 528, no skips. WOMD bounded 60+60 accepted (6 shards per split); AV2 both ERROR at start_timestamp. Waymax data ingestion only PASS at raw step 0 -> 1. Manuscript snapshot is byte-identical to the latest supplied TeX.

Goal: retain certified Picard witness and constant public action; partition physical resource checks on independent exact event boundaries; include terminal right-continuous rule and all declared hidden-branch schedules. Full moving-agent/event correlation/online SC/message/observation semantics remain open. Resource checks conservatively require entry and stay, direction and capacity; no invented mode classification. Member schedules are externally declared and time-unrolled, not derived from simulator replay. Full-support/completeness/real task-tail flags remain false.

## Changes
- a53_schedule: right-continuous permission lookup, closed subslabs, terminal point, branch-family intersection.
- a53_mission: independent schedule digest and all transition bindings; optional preceding whole-step checker retained for comparison.
- a5_replay_bridge: replays original MPFR witness, intersects state tube with exact-time subslab Euler enclosure; direction derivative bound; no private observation/control updates. footprint: explicit instantaneous closed interval geometry permitted (native integration remains strictly positive duration).
- a53b_interlock: independent interval-clearance observation, deployment/absence acknowledgements tied to event/version/resource/command time, conservative interruption/cancellation path. This is a simulator-facing reference state machine, NOT a certified observation source or actual CARLA/SUMO control implementation. Existing alternating controller retains point-sample assumptions; actual detector latency/clearance and yellow/all-red phases still required. 
- record_adapters: normalize Arrow timestamp logical columns by physical int64 ticks before reading Python objects; no float epoch conversion. The real failure cause must be verified against server schema. New fixture/probe script.
- probe_waymax: align to standard current step 10 then replay 11. No responsive background model yet.
- probe_wosac: official ChallengeType API, optional deterministic CV baseline or external binary rollouts, exact identity set/shape checks, config fingerprint; real evaluation pending. No network training.
- audit_supervision_quality / audit_external_rule_sources: bounded inventory checks; no generated proof/occupancy/causal labels.

## Tests executed locally
- dependency-free 128 passed (includes prior 112 plus new timestamp, interlock, inventory and additional schedule cases), 29 finite/gate/time passed, 13 independent SC passed. Overlap exists; not summed.
- Uploaded report independent audit NOT_PASSED: AV2 both ERROR, Waymax old clock. WOMD data source counts and chart exported; no raw trajectory/geometry realism validation.
- Python compileall and shell syntax pass.
- Actual Arrow fixture cannot execute in local environment (ModuleNotFoundError pyarrow). WOSAC/Waymax/SUMO/CARLA target runtime absent. Native CMake requires official MPFR development headers; no mock/temporary header or rounding substitutions. Native six new segmented cases and complete suite require target-server gate.

## Server gates
`bash scripts/validate_phase6c_a5_3b.sh` distinct fresh build and strict nonempty CTest + all Python no skips, baseline >=528. Expected marker A5_3B_SCOPED_GATE_PASS only if actual tests pass. Then run actual Arrow fixture + dual real label smoke, Waymax aligned probe, optional WOSAC official baseline. See companion source plan. Never alter manifest or suppress failing assertions. Any evidence gap = UNKNOWN, not infeasible or safe.

## Remaining sequence
A5/3b first increment is NOT all A5/3b. Follow-up: independently bounded moving actors and time-unrolled conditionally reachable protocol/observation branches; actual dynamic controller state/causal guard coverage; continuous entry/stay classification and variable direction field; online SC absolute deadline and tail linkage; teacher and real ODD model; actual simulator label generation and quality audit before training.
