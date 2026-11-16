# Proof obligations and limitations: finite safe continuation

## Formal statement of the kernel

Let `C` denote an **entire correlated information support**, not one hidden physical state.  `gamma(C)` is a union of `SupportAtom` boxes with the same public observation history. The computed family is conditional on these external proof obligations:

**P0 (sound containment).** `SafeDomain.contains_atom` is sufficient only for initial bounds. `evidence_replayer(EvidenceContext, SCContract)` must independently check that the exact action's outward continuous reachable tube (including disturbances, footprints, resources and all responses of that source) stays in the hard-safe domain and that the successor boxes are sound. The Boolean return itself is not proof; the replay implementation must be audited.

**P1 (complete successor/observability).** `branch_cover_replayer(C,action,contract)` must prove that the action contains all admissible protocol responses and observation realizations, with no unverified hidden modes deleted; labels claimed distinct must be distinguishable under the public observation model. Overlapping measurement histories must be combined into a single child. A numerical partition does not confer observability.

**P2 (tail).** `terminal_replayer(C,tail,contract)` must independently verify the full public observation-conditioned tail for all concrete supports in `gamma(C)`, task automaton acceptance `F_T`, a finite upper completion time, and protocol/clock/model matching. A safe stopping refuge alone is invalid.

**P3 (semantic identity).** Version bindings must refer to the same protocol, clocks, physical/agent envelope and task identity throughout one certificate. Any external update invalidates the old certificate.

Given P0–P3, the kernel computes `\underline W_0 = { C : P2 and safe(C) }`. At each integer `r >= 1`, it adds a previously absent cell `C` iff a **single common** candidate action is replayed, P0 and P1 hold, and for each observation class `o`, the complete successor posterior union is contained in a previously admitted child `C_o`. It does **not** demand that a globally optimal `C_o` or continuous control be found.

## Inductive correctness argument

**Base (`r=0`)**: by P2, every concrete state represented by any retained terminal cell has a policy reaching `F_T` in at most its verified `T_tail(C)` while staying hard-safe.

**Step**: assume every cell in `\underline W_{r-1}` has a stored safe, task-reaching public conditional policy and finite bound `T(child)`. P0 ensures the common prefix is continuously safe for the whole source support. P1 and the posterior-union subset test ensure **every** possible observation leads to one publicly selectable child covering the full conditional posterior. The stored child belongs to the previous family. Appending that child's induction-hypothesis policy is safe and task-completing for all hidden histories, with bound

`T(C) = h + max_{o} T(C_o)`.

Because `h > 0` and every newly added cell points only to previous-family cells, storing the first admission index `d(C)` ensures every edge `d(child) < d(C)`. No waiting self-loop gains finite rank. From a rank `d` start the loose uniform bound is `d*h + max_{admissible terminals} T_tail`, while the stored per-cell `T(C)` can be tighter. This does **not** assert safety after task acceptance unless separately provided by the tail.

## Rank persistence under replanning

`start_sc_execution` sets inherited rank `d_0`. `advance_sc_execution` accepts only the exact stored observation-to-child mapping and decreases the **inherited budget** by one; a new certificate is accepted by `replan_sc_execution` only for the same support/model context and with `d_new(C) <= budget`. Hence reset-to-H cannot evade finite progress. The executor does not itself observe the car or validate the physical successor; the runtime must also establish the actual observation and physical containment.

## Physical reserve and value

For a terminal verified margin lower bound `\underline m_tail(C)`, a proven action lower bound `\underline g(C,u)` and selected child margin lower bounds, the code computes

`\underline Q(C,u) = min(\underline g(C,u), min_o \underline V(C_o))`,

then chooses the greatest available **fully replayed** candidate lower bound. This is an achievable-policy lower bound for the *rank-at-first-admission* certificate, NOT the full horizon-wise `V_H^SC` or the exact `Cons_H`. All comparisons and time sums in this kernel use exact `Fraction` arithmetic; decimal physical margins are accepted only when the independent replayer proves their outward lower-bound status. Missing margin proof leaves `margin_lower=None`; no fabricated 0 or 1. Claims of exact physical margin are out of scope.

## Non-proven assumptions / current engineering gaps

The callbacks in unit tests use explicitly declared **synthetic toy oracles**. The project has not supplied end-to-end proof artifacts connecting the callback implementation to actual MPFR tubes, full protocol branches, terminal tail, and resource geometry. The finite algorithm is exact relative to its supplied cells/candidates/verified transitions, but is generally a conservative **inner approximation** of the concrete reach--avoid winning set. Its incomplete output is not an infeasibility oracle. `certified_full_support` is intentionally always false in this release.
