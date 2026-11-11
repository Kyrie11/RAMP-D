# Phase 2 design: finite belief-support cells and information-state invariant

## 1. Scope

Implement the finite information-state abstraction and greatest fixed point
from the paper's Appendix. Do not yet synthesize continuous feedback gains,
run SUMO/CARLA, parse AV2/WOMD, or claim full protocol safety.

## 2. Data model

- `SupportAtom`: one continuous ego-state box, optional other-agent continuous
  boxes, and a discrete mode tuple (protocol, resource monitor, agent-response
  mode, etc.).
- `BeliefCell`: one **complete belief support** represented by a union of
  support atoms. It is one policy node; it is not an individual hidden state.
- `ActionWitness`: one common 2-D ego control `(jerk, steering_rate)` for every
  source atom in the belief cell.
- `AtomTransition`: for each source atom, a proof verdict/reference and every
  possible nonempty observation branch.
- `SafeDomain`: hard ego-state bounds, other-state bounds, required/allowed
  discrete modes, and optional interval friction check.

## 3. Robust information predecessor

For a current retained family `S`, a cell `B` is retained iff there exists an
`ActionWitness` such that:

1. the witness has exactly one transition for every source atom in `B`;
2. every source-atom transition is `PROVED` by the supplied evidence verifier;
3. all source atoms use the same control vector;
4. for each observation label `Y`, successors from all source atoms that can
   produce `Y` are aggregated into the posterior support `Post(B,u,Y)`;
5. each nonempty posterior is covered by one cell in `S`.

The box coverage test is conservative: every posterior atom box must be
contained in one target atom box with identical discrete mode. A posterior
box that is only covered by the union of several partial boxes is unresolved,
not accepted.

## 4. Fixed point

Start with cells wholly inside the hard-safe domain. Repeatedly remove every
cell for which no common action satisfies the robust predecessor test against
the current family. Removal is simultaneous per iteration. The set decreases
monotonically; with `M` finite cells, there are at most `M` removal rounds and
one final no-removal round.

The returned set is named `S_in_candidate`. It is an exact fixed point of the
supplied finite abstraction, but not a concrete safety certificate until the
abstraction coverage and every evidence reference are verified by Phase 4.

## 5. Refinement semantics

`split_support_atom` bisects one box along a selected dimension into two closed
halves that overlap at the representable midpoint. The union is exactly the
parent box. It preserves the same `cell_id` and `policy_node_id`, creates no
new observation branch, and invalidates old transition evidence. Recompute
all transitions after splitting. A geometric split must never be used to let
policies distinguish histories that have the same realized observations.

## 6. Evidence trust boundary

The fixed-point engine requires an `evidence_verifier(evidence_ref)` callback.
If absent, if a transition is `UNKNOWN`, if a reference fails replay, or if a
source atom is missing, the action is rejected. Phase 2 tests use a deterministic
in-memory finite-game verifier only to test the abstract algorithm. Production
references must later be replayed by the integrated validated tube / protocol
/ resource verifier.

## 7. Non-goals

- no public backup controller synthesis yet (Phase 3);
- no protocol automaton enumeration or full-support verification yet (Phase 4);
- no CEGAR loop yet (Phase 5);
- no prediction training or simulator dependence yet (Phase 6).
