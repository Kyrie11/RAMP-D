# Phase 5 Hardening Audit

## Scope and goal

This revision audits the Phase 5 CEGAR implementation already present in the uploaded
archive. It preserves the paper's `CERTIFIED / COUNTEREXAMPLE / UNKNOWN` semantics and
keeps the assurance scope at `PHASE5_CEGAR_EXPLICIT_PROTOCOL_SUPPORT`.

The concrete goals were:

1. prevent evidence and replay callback exceptions from escaping the three-valued API;
2. return an outer CEGAR task to `pending` when verifier construction or execution fails;
3. compute a received-message public decision time from receipt/local clocks rather than
   treating a hidden physical change time as an observation;
4. identify the exact non-point public clock so refinement can split `change`, `receipt`,
   or `local` as appropriate;
5. bind verification budgets and queue generations to evidence versions.

## Implementation

- `full_verifier.py` now validates callback type and support atom type, catches callback
  exceptions, requires a strict boolean replay result, and records unresolved reasons.
- `_public_observation_time()` uses receipt/local for received messages. A silence branch
  uses local when available and falls back to change only when no local clock is declared.
- Public-time obligations include the transition ID and responsible clock. The default
  selector can construct a refinement action for all three clocks.
- `CegarEngine.run()` catches verifier factory/execution failures, rejects malformed
  verifier results and statuses, and requeues the in-flight outer task.
- `FullVerifierContract.digest` includes `max_tasks` and `max_path_length`; queue
  construction rejects a generation mismatch with the evidence registry.
- The package version is `0.8.1`, and `MANIFEST.sha256` was regenerated after removing
  temporary `pytest-of-agent` artifacts from the deliverable tree.

## Tests and evidence

The uploaded server archive remains the baseline evidence:

- Phase 4 outer regression: 328 Python tests passed, plus 3 native smoke tests.
- Phase 5 baseline: 10 dedicated tests passed.

The hardened source now contains 20 Phase 5 tests. The current container does not provide
pytest, CMake, or the official MPFR development headers, so the 9 new tests were not
claimed as executed here. `python -m compileall -q python tests` and `bash -n
scripts/validate_phase5.sh` pass. The target server must rerun the gate before treating
this revision as accepted:

```bash
cd /home/senzeyu2/code/RAMP-D
conda activate mfrp
PYTHON_BIN="$(command -v python)" \
  PYTHONPATH="$PWD/python${PYTHONPATH:+:$PYTHONPATH}" \
  bash scripts/validate_phase5.sh
```

The generated report should show at least 20 Phase 5 tests with zero failures, errors, or
skips, and should be uploaded together with the machine-readable summary.

## Remaining boundary

The resumable queue is still an outer refinement scheduler. It does not serialize the
internal `FullSupportVerifier` work deque, `seen` set, or unresolved evidence state.
Observation refinement still requires the caller to update the observation router/model.
The implementation remains synthetic and explicit: no WOMD, Argoverse 2, SUMO, or CARLA
is used, and no real-scene safety certificate is produced.
