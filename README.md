# RAMP-D — Phase 6C-A development snapshot (0.9.0)

This repository contains the current research implementation of RAMP-D. The mathematical specification of record is `AnonymousSubmission2027(1).tex`; implementation history and phase acceptance criteria are in `docs/`.

## Current status

- **Phase 6B:** parser and scene contracts have been audited and corrected locally. The uploaded server report shows WOMD Scenario validation PASS (3 records) and AV2 Motion SKIP because the server environment lacked `pyarrow`/`fastparquet`; therefore Phase 6B is not yet accepted end-to-end.
- **Phase 6C-A:** pure-Python contracts for history/future separation, joint modes, observation histories, RuleNet-inspired soft ordering, and CARLA/SUMO synchronization are implemented. The dependency-free validation harness currently reports **47 passed**.
- **Cross-phase audit:** a protocol timing bug was corrected so a hidden rule change that occurs before message receipt remains in support. Message receipt and local detection are independent observation channels.
- **Not complete:** native MPFR replay, full Phase 2–5 mathematical audit, finite-horizon `W_H^SC`/rank/value/CCG coverage, replayable silence-deadline evidence, vector-map geometry adapters, actual CARLA/SUMO bridge, predictor training, and closed-loop experiments.

No current report should be interpreted as `full_support_certified=true` or as a real-road safety guarantee.

## Validation

From the project root, in the server environment:

```bash
# Install the optional parquet readers used by AV2 Motion
pip install -e ".[datasets]"

# Full project tests plus real WOMD/AV2 validation samples.
# The capital-B entry point is kept as a compatibility wrapper.
bash scripts/validate_phase6B.sh

# Pure-Python Phase 6B adapter + Phase 6C-A regression harness.
scripts/validate_phase6c_a.sh
```

The Phase 6B script returns exit code `0` for PASS, `3` for SKIP, and `4` for ERROR. A SKIP is not a pass. Dataset roots default to the paths supplied in the project configuration and can be overridden with the environment variables documented in `docs/PHASE6B_ACCEPTANCE.md`.

## Important implementation documents

- `docs/PHASE6B_AUDIT_AND_FIXES.md` — data schema, masks, timestamps, digests, and original server report findings.
- `docs/PHASE6C_A_PLAN.md` — Phase 6C-A contracts, RuleNet math, supervision boundaries, and next subphases.
- `docs/PHASE6C_A_IMPLEMENTATION_REPORT.md` — code changes, tests, and explicit limitations.
- `docs/MATHEMATICAL_AUDIT_PHASE1_5.md` — current cross-phase math audit and unresolved gaps.
- `docs/DATASETS_AND_SIMULATORS.md` — WOMD, AV2, CARLA 0.9.16, and SUMO 1.20 data/integration policy.
- `PROGRESS.json` — machine-readable development status.

## Dataset and simulator policy

Use WOMD `scenario` protobufs as the canonical source for track identity, SDC identity, vector-map and dynamic-map semantics. In AV2 Motion, the official API convention `track_id == "AV"` identifies the ego vehicle; `focal_track_id` remains a separate prediction-target identity. The separate AV2 Map Change dataset is reserved for map-change robustness work.

CARLA/SUMO have not been started by this repository snapshot. Phase 6C-B will require a single orchestrator tick owner, matched fixed time steps, one traffic-light authority, and separate sensor production/delivery timestamps. See the simulator policy before launching experiments.
