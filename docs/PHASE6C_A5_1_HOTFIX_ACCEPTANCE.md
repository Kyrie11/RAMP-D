# Phase 6C-A5/1 hotfix — 2026-11-17

## Goal and scope
User reported `validate_phase6c_a6.sh`: 454 passed, 1 failed at
`test_native_ctest_requires_nonempty_discovery`. Uploaded ZIP is byte-identical
to the previously supplied A5/1 release; it contains no A6 script or A6 source.
This release repairs A5/1, not the unavailable A6 implementation. A separate
source-hash-checked shared gate installer can be used on a compatible A6 tree.
Do not overlay the complete A5 release onto A6.

## Implementation and failure analysis
- Reproduced the exact assertion: the old fixture has no CMakeCache, so it fails
  before discovery. Add the cache ON entry; separately test missing/OFF cache.
- CTest gate checks exact discovered names, unique count and all actual Passed
  rows, not mere substring membership or the summary percentage. C locale;
  cwd compatibility retained. CTest failures/missing executable remain ERROR.
- A5 finite policy snapshots input lists and memoizes (state,remaining) visits,
  preserving exact worst-case Fraction and universal branch quantification.
- A5 physical world v2 digest includes declared bicycle parameters, six
  derivative disturbance intervals, allowed control bounds, and safe domain.
  Require matching parameters, declared disturbance subset of replayed box,
  admissible constant control, explicit matching friction parameters, and
  actual membership of evidence source/action/transition in the cell.
- With no independently justified conditional endpoint partition, require
  every declared successor atom to cover the entire endpoint and be safe.
  This is a conservative sufficient condition; not a general union-cover test.
  The protocol gate refuses unmodeled extra mode changes, other coordinates,
  and nonempty resource monitors without a mapping to the physical world.
- No entry/stay classifier exists in A5. If a resource may be occupied, both
  alpha and beta must hold. The synthetic forward direction remains a model
  assumption; general lane orientation and dynamic resource semantics pending.
- Previous resource and branch tests could reject merely on changed digests.
  Reseal the candidate and model consistently; regenerate the clock digest
  before testing actual branch rejection. The resource test includes a
  positive open-resource control with nonzero forward velocity.
- Found 11 failures in the old `validate_sc_discrete_only.py` carrier after
  support digest changes; add float lo/hi and as_tuple. No native operations
  are mocked as verified. No modification of SC mathematics or C++ core.

## Acceptance record (this sandbox)
- Original reported test reproduced: 1 failed, 83 deselected.
- Phase 6 dependency-free real-code regression: 84 passed after fix.
- Native discovery gate fixtures (real CMake/CTest, dummy commands): 8 passed.
- Exact finite task tests: 10 passed; release integrity fixtures: 6 passed.
  The above three suites together: 24 passed.
- SC discrete-only carrier: initially 11 failed/2 passed, then 13 passed.
- Physical/protocol replay Python files: syntax check PASS; native regression
  NOT RUN. CMake native configuration fails because MPFR/GMP development
  headers/libraries are unavailable here. Do not interpret gate fixtures as
  successful execution of numerical C++ tests.
- No WOMD, AV2, CARLA or SUMO needed or used. No complete physical tail,
  full-support certificate, deadline proof, or real-world assurance claimed.

## Server acceptance
Unpack into NEW directory; run `python scripts/verify_release.py`, then
`bash scripts/validate_phase6c_a5.sh`. The complete A5 suite must pass including
MPFR replay and all Python regression tests. Use existing A6 tree only with
separate shared gate patch; run `bash scripts/validate_phase6c_a6.sh` there.
A5 v2 world/contract/evidence digests must be rebuilt from the declared model;
old hashes are not reusable. A6 call sites need review before physical changes
are ported. Do not disable tests, allow skipped mandatory tests, or accept
UNKNOWN as proof. Send A6 source ZIP + actual logs for further review.
