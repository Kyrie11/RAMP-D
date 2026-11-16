# Phase 6C-A3 / mathematical SC-gate plan (2026-11-16)

## Inputs and scope

Source of record: current `AnonymousSubmission2027(1).tex`, Sect. **Safe-continuation feasibility and commitment timing**, Appendix **Set-Valued Viability, Optimization, and Verification Details**. Existing Phase 2 belief cells, atom-level `ActionWitness` and context-bound proof callback are reused. Existing Phase 4/5 protocol and CEGAR implementations are **not** replaced. This release is a mathematical-gate insertion before Phase 6C-B simulation.

## Must deliver

1. Restore missing `build_coverage_ledger` public API (previous `__init__.py` imported a nonexistent function).
2. Implement `W_0 = K_term`, `W_{r+1} = W_r ∪ (B_safe ∩ Pre_obs(W_r))` on finite **joint information-state cells**, with verified *finite-completion tails*, shared public actions, full protocol-support branch evidence, observation-merge, and safe-tube evidence.
3. Store least arrival rank and selected common action with observation children; never allow same-rank or self-loop progress.
4. Store exact rational worst-case completion bound: `T(C)=h + max_observation T(child)`, `h` being the positive common control step duration.
5. Make replanning inherit rather than reinitialize remaining rank budget, with a separate fail-closed execution contract.
6. Optionally derive conservative **lower bounds** on policy physical reserve using independently replayed tube margins; avoid claiming exact `V_H`, exact `Cons_H`, or physical safety from a raw floating-point score.
7. Run synthetic math tests, native Phase 4/5 regression, and Phase 6C-A2's data-contract regression; keep real-data validation as a separate hard gate.

## What is deliberately not delivered

- An independent all-history terminal-tail verifier against real CARLA/WOMD/AV2 scenes; `terminal_replayer` is a **required external trust boundary**.
- A full continuous or hybrid exact winning set, exact `V_H^SC`, a CCG three-layer graph with ICG, STNU dynamic controllability, optimized policies, learned predictors, or new CARLA/SUMO bridge.
- A certified claim merely because a callback returns `True`.  The algorithm is a conditional finite game whose premises require independently replayable native/protocol evidence.

## Expected gates

- **Local without MPFR headers**: 13 isolated finite-game tests plus 67 existing dependency-free data tests; not native acceptance.
- **Server**: 3 native CTest tests + Phase 4/5 + 13 new SC tests + 67 Phase 6C-A2 dependency-free tests; all required without skips. Separate WOMD/AV2 real smoke must report two PASS rather than SKIP.
- **Fail cases**: missing proof replay, stale context, incompletely enumerated observation support, terminal safety-only refuge, rank reset, unaccounted observation, unsafe cell, or model-version mismatch produce nonmembership/exception, not fabricated certification.
