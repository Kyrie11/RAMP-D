# Numerical contract and scope (Phase 1D foundation; Phase 3 additions below)

The Phase 1A-1C numerical contract remains in force: MPFR directed rounding,
192-bit internal precision, outward conversion to binary64, strict Picard
self-inclusion, exact rational time bookkeeping, and fail-closed UNKNOWN.

## Phase 1D interval square root

For a finite interval `X=[a,b]`:
- if `b < 0`, square root is outside the real domain and the operation fails;
- if `a <= 0 <= b`, the lower bound is exactly zero;
- otherwise the lower endpoint is `sqrt(a)` rounded down;
- the upper endpoint is `sqrt(b)` rounded up.
Both MPFR results are converted to binary64 with the same directed rounding.
This operation is used to bound the norm of a fixed separating axis.

The native ABI is bumped from 2 to 3. The Python loader requires ABI 3 and will
reject a stale ABI-2 shared library. A clean `build_phase1d/` rebuild is
required; do not copy a Phase 1C `.so` into this release.

## Footprint geometry contract

For a complete state tube `X` over exact interval `I`, dimensions `L,W > 0`,
and body-frame center offset `o=(ox,oy)`, the rectangle is

    F(x) = p + R(psi)o + R(psi)([-L/2,L/2] x [-W/2,W/2]).

For any fixed exact-binary64 axis `n`, the support projection is enclosed by
interval evaluation of the center projection and

    (L/2) * abs(n dot R(psi)e_x)
  + (W/2) * abs(n dot R(psi)e_y).

The half dimensions are formed by MPFR interval division, not ordinary
floating-point division. The absolute-value upper bounds are computed from
the interval endpoints, and all radius/center operations use the MPFR-backed
interval API. AABB is the pair of projections on `(1,0)` and `(0,1)`.

Phase 2 fixes `px,py` at the rear axle, consistently with the bicycle ODE.
Geometry contains explicit `center_offset_x_m/y_m`; zero offset is not a universal assumption. Vehicle dimensions and offset are treated as fixed
configured constants in this release. Their calibration/uncertainty must be
addressed before physical claims on a real vehicle.

## Sufficient separation result

For two state tubes covering the same exact time interval, compute outward
projection intervals `P_A(n)` and `P_B(n)`. If one is strictly below the
other, the swept spatial sets are disjoint. The lower projection gap is
computed downward; its metric clearance lower bound divides by an outward
upper bound on `||n||`.

The fixed axes include world x/y and heading-midpoint axes for both vehicles.
The midpoint trigonometric calculation only selects a binary64 axis; it is
not part of the proof. The chosen axis is thereafter treated as an exact
binary64 vector and all projection/gap/norm calculations use MPFR interval
operations.

The finite axis set is not complete for arbitrary uncertain swept sets. A
failure to find a gap returns UNKNOWN. The API never returns COLLISION. If two
spatial paths cross at different times, their spatial swept unions may overlap
even without a simultaneous collision; this implementation may therefore
return UNKNOWN conservatively. Later temporal subdivision can tighten this.

For two adaptive tube results with different segment boundaries, the common
temporal refinement is formed exactly using rational times. Each source
segment's whole state tube is reused on the overlap subinterval. This is a
valid superset and therefore sound, but may be conservative. High-level
`separate_tube_results` accepts only complete `VALIDATED` dynamics results, checks
exact full-horizon coverage and endpoint linkage, and replays both source Picard
certificates before mapping their state boxes to geometry.

## Replay and provenance

A separation witness stores the two encoded state boxes, geometry constants,
common exact time interval, selected axis, projected intervals, gap and metric
clearance. Replay recomputes the projections and strict gap. It does not replay
the source Picard certificates; the claim is conditional on those state boxes
having come from complete sound dynamics tubes. A full-system certificate
must bind and replay the parent tube certificates as well as protocol and
resource branches.

## Historical Phase 1D exclusions (current scope below)

- No concrete collision/time-of-impact witness.
- No static obstacle or road-resource polygon intersection.
- No capacity/conflict monitor or traffic-rule checks.
- No full-support verifier `CERTIFIED` result.
- No S-infinity or backup controller.
- No simulator or dataset dependency.
- No claim that the tested finite candidate axes completely decide collision.
- No proof-assistant verification of the C++/MPFR implementation.

Unit tests, sanitizer runs and high-precision random corner audits can expose
bugs but cannot prove the absence of implementation or modeling errors.

## Phase 3 additions and current limits

The native arithmetic and Picard search are unchanged (ABI 3). `analytic_bounds.py` intersects independent integrator-chain bounds and exact-rational quadratic extrema with the Picard enclosures. `backup.py` adds state/friction and static corridor/gate/rectangular-obstacle checks, content-bound physical replay, and finite public-law search. `backup_graph.py` connects the Phase 2 information invariant to guarded executable local graphs. These additions do not implement dynamic resource polygons/capacity/conflicts, protocol enumeration, moving-agent response tubes, full-support certification, CEGAR or simulator bridges. See PHASE3_DESIGN.md for exact assumptions.
