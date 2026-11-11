# Phase 2 reference-paper analysis and applicability limits

## Brown et al., CDC 2023

The uploaded paper studies **discrete-time nonlinear control-affine systems**
`x[k+1] = f0(x[k]) + sum_i gi(x[k]) u_i[k]`. It constructs interval/polytope
inclusion overapproximations, bisects state boxes when the predecessor test is
indeterminate, and iterates a robust controlled-invariant predecessor. Its
robustness-margin definition and finite bisection results rely on its stated
Lipschitz/inclusion-function assumptions and discrete-time model.

What we reuse:
- outside-in predecessor/fixed-point structure;
- box subdivision when a set inclusion cannot be decided;
- conservative inner approximation and explicit unresolved cells;
- do not sample the continuous control set and mistake sampled controls for
  a proof of existence.

What we do **not** copy as a theorem:
- its discrete-time control-affine reachable-set formulas do not directly
  certify the continuous-time bicycle ODE or RAMP-D's hybrid protocol;
- its maximal/near-maximal CIS statements do not automatically extend to
  partially observed belief supports and observation-conditioned policies.

## Schafer, Gruber, and Althoff, IEEE TAC 2024

The uploaded paper studies robust invariant sets of perturbed nonlinear
**sampled-data** systems using zonotopes, a parameterized reachability
approximation, successive convexification, and a separate safety-verification
step. It explicitly distinguishes candidate synthesis from verification and
checks constraints over both sampling instants and the inter-sample interval.

What we reuse:
- set-valued state representation and robust disturbance semantics;
- candidate synthesis must be followed by independent reachable-set
  verification;
- continuous inter-sample constraints matter even when the terminal map is
  discrete-time;
- a local optimizer or approximate reachable set is not itself a certificate.

What we do **not** copy as a theorem:
- their zonotope RCI algorithm is not a ready-made belief-space invariant
  solver; it has a different state space and sampled-data controller class;
- the paper's fixed-dimensional zonotope parameterization and convexification
  assumptions are not assumed for RAMP-D's hybrid information-state game.

## Phase 2 implementation consequence

Phase 2 implements the **finite abstract information-state game** from the
RAMP-D Appendix. A `BeliefCell` is one whole information support represented
by a union of continuous boxes and discrete protocol/resource/agent modes.
For each cell, a candidate `ActionWitness` contains exactly one common
`(jerk, steering_rate)` control and a complete transition record for every
source atom. For each observation label, successors from all compatible
source atoms are aggregated into one posterior support. That posterior must
be covered by one retained belief cell.

The fixed-point engine is exact for this supplied finite abstraction. It is
not, by itself, a concrete `S_in` proof: transition evidence is checked through
an injected evidence-verifier interface, and Phase 4 must bind those evidence
references to complete protocol, continuous-tube, resource, and full-support
verification. The API and certificates therefore say
`S_in_candidate` / `FINITE_ABSTRACTION_ONLY`, never `CERTIFIED`.

The two uploaded papers are sufficient for Phase 2's mathematical design.
No further papers are required for this phase. For Phase 3, additional
references may be requested if we decide to use a particular robust MPC,
feedback synthesis, or constrained control solver.
