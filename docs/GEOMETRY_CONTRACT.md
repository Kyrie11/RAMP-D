# Phase 1D geometry and proof contract

## 1. Concrete set represented

For one time interval `I`, the input state box `X` must contain every true
state `x(t)` for every `t in I`. The model state is
`(px, py, psi, v, a, delta)`. Vehicle dimensions are fixed binary64 constants
`L > 0`, `W > 0`. The rectangle's geometric center is offset from the state
reference by the body-frame vector `o=(ox,oy)`.

With `R(psi)=[[cos,-sin],[sin,cos]]`, the rectangle at a state is

    F(x) = p + R(psi)o + R(psi) Q,
    Q = [-L/2,L/2] x [-W/2,W/2].

The swept spatial set is `S = union_{t in I} F(x(t))`.

## 2. Outward projection enclosure

Choose a fixed nonzero axis `n=(nx,ny)` whose components are exact binary64
numbers. Define

    c = p + R(psi)o
    alpha = nx cos(psi) + ny sin(psi)
    beta  = -nx sin(psi) + ny cos(psi).

For every point in `F(x)`, its projection is

    n dot c + xi alpha + eta beta,
    |xi| <= L/2, |eta| <= W/2.

The implementation computes interval enclosures `C`, `A`, `B` for the center
projection, `alpha`, and `beta`. Let

    Aabs = max(abs(A.lo), abs(A.hi))
    Babs = max(abs(B.lo), abs(B.hi))
    Rhi = upper((L/2)*[0,Aabs] + (W/2)*[0,Babs]).

All products, sums, half-dimension conversions and endpoint operations use
MPFR directed rounding, then outward conversion to binary64. The returned
projection interval is `C + [-Rhi,Rhi]`. Thus every point in every rectangle
for every state in `X` is contained in the projection interval. Since `X`
encloses the full trajectory over `I`, this encloses the entire swept spatial
set `S`.

AABB is obtained by choosing `n=(1,0)` and `n=(0,1)`.

## 3. Sufficient pairwise separation theorem

Let `S_A` and `S_B` be the two true swept spatial sets, and let `P_A(n)` and
`P_B(n)` be their outward projection enclosures. If

    P_A(n).hi < P_B(n).lo

or the reverse inequality holds, then the projections of `S_A` and `S_B` are
disjoint. A common point in `S_A intersect S_B` would have the same projection
in both sets, a contradiction. Therefore `S_A intersect S_B = empty`.

The gap is computed with downward rounding. For non-unit `n`, its metric lower
bound is divided by an MPFR upper enclosure of `sqrt(nx^2+ny^2)`. The result is
a conservative lower bound on Euclidean distance between the swept spatial
sets.

The code tests world x/y axes and fixed axes selected from both interval
heading midpoints. Axis selection itself is not used as a numerical proof:
its output binary64 vector is treated as an exact fixed axis in all subsequent
MPFR operations. Any fixed axis is valid for the sufficient projection-gap
argument. The finite candidate set is not complete; failure to separate means
`UNKNOWN`, not collision.

## 4. Time alignment

Two footprints must refer to the same exact rational time interval. For two
adaptive segmentations, `separate_tube_sequences` forms their common temporal
refinement. On an overlap interval, the entire source segment tube is reused;
this is a superset of the state set on the overlap and is therefore sound,
though it may be wide. Every overlap interval must be separated to return
aggregate `SEPARATED`.

## 5. Result semantics and non-claims

- `SEPARATED`: a strict outward projection gap proves the encoded swept sets
  disjoint, conditional on valid input state tubes and calibrated geometry.
- `UNKNOWN`: no tested axis proved strict separation or an enclosure could not
  be represented. It is never converted to `COLLISION`.
- The algorithm does not produce a concrete collision trace or contact time.
- It does not check static obstacles, road-resource polygons, capacity, rules,
  monitor states, or multi-agent resource conflicts.
- It does not validate the parent dynamics tubes; use complete `VALIDATED`
  `TubeResult` inputs through `separate_tube_results`.
- It does not establish the full planner's `CERTIFIED` status.

## 6. Reference point is now fixed: rear-axle centre

The current bicycle ODE is defined with `(px,py)` at the centre of the rear
axle, `v` as signed longitudinal speed at that point, and `psi` as body
heading. This is the standard kinematic single-track convention used by the
model equations. The body rectangle is not assumed to be centred at the rear
axle. `center_offset_x_m/y_m` are the explicit body-frame displacement from
the rear-axle centre to the geometric centre of the rectangle.

`python/rampd_core/vehicle.py` provides
`commonroad_bmw_320i_benchmark()` as a reproducible nominal profile:
4.508 m x 1.610 m, wheelbase 2.5789128 m, and rear-axle-to-body-centre offset
1.4227170936 m. The latter is a nominal proxy obtained by assuming the CG is
the rectangle centre; it is not exact body metrology. Replace it with measured
CARLA bounding-box geometry and a calibrated rear-axle location before making
physical safety claims. Surrounding actors should use per-actor dimensions or
conservative class envelopes. Friction is not part of the chassis geometry;
it must be supplied as a scenario-specific conservative tire-road bound.
