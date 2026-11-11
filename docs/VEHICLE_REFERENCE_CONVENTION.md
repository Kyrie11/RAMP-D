# Vehicle reference-point decision (Phase 1D correction / Phase 2 contract)

## Decision

Use the **centre of the rear axle** as `(px, py)` for every vehicle represented
by the paper's kinematic bicycle ODE. `psi` is the body longitudinal heading,
`v` is signed longitudinal speed at the rear axle, and `delta` is the
single-track equivalent front-wheel steering angle.

This is not an arbitrary convention. The ODE

```
px_dot = v cos(psi)
py_dot = v sin(psi)
psi_dot = v tan(delta) / Lw
```

is the no-slip kinematic bicycle equation when position and longitudinal
velocity are referenced to the rear-axle midpoint. A body-centre reference
would need a different translational velocity relation. The choice is also
used in CommonRoad's kinematic single-track collision-avoidance benchmark.

## Footprint transform

For body length `L`, width `W`, and measured body-frame vector `o=(ox,oy)`
from rear-axle centre to the geometric centre of the body rectangle:

```
Q = [-L/2,L/2] x [-W/2,W/2]
F(x) = p + R(psi) o + R(psi) Q
```

If front and rear overhangs from axle centres are `of` and `or`,
`ox=(Lw+of-or)/2`. Do not set `ox=0` unless the body box is actually centred
on the rear axle. The Phase 1D support-projection implementation already
accepts this offset; this release adds an explicit vehicle-model profile and
records its provenance.

## Nominal reproducible passenger-car profile

The recommended development benchmark is the CommonRoad BMW 320i profile:

| Parameter | Value | Provenance |
|---|---:|---|
| Overall body length | 4.508 m | CommonRoad benchmark |
| Overall body width | 1.610 m | CommonRoad benchmark |
| Front axle to CG `a` | 1.1561957064 m | CommonRoad vehicle parameter mapping |
| Rear axle to CG `b` | 1.4227170936 m | CommonRoad vehicle parameter mapping |
| Wheelbase `Lw=a+b` | 2.5789128 m | Derived |
| Rear axle to body rectangle centre `ox` | 1.4227170936 m | **Nominal proxy only:** CG assumed to coincide with rectangle centre |
| Lateral offset `oy` | 0 m | Symmetric-body nominal assumption |
| Gravity | 9.81 m/s^2 | Benchmark value |

The CG-as-box-centre assumption is not exact vehicle metrology. It is a
reproducible initial benchmark only. The offset, dimensions, steering limits,
acceleration/jerk limits, and friction envelope must be calibrated before
physical safety claims. `mu_f` is deliberately not set by the vehicle profile:
it is a tire-road operating-condition parameter and must be supplied as a
conservative scenario-specific lower bound in verification.

## Real data / CARLA policy

- **Ego in CARLA:** obtain actor bounding-box `extent` (half dimensions) and
  actor-relative `location`; transform the box centre into the rear-axle body
  frame using a calibrated rear-axle location. CARLA `bounding_box.location`
  is relative to its parent actor. Account explicitly for CARLA's coordinate
  convention when converting lateral signs.
- **AV2/WOMD surrounding actors:** use each actor's reported length/width if
  available. If missing or unreliable, use conservative class-specific
  geometry bounds; do not assign every actor the ego BMW dimensions.
- **No silent fallback:** if the rear-axle offset or dimensions are unknown,
  mark the geometry uncalibrated and do not issue a physical collision
  certificate for that actor.

## Why not use the body geometric centre?

It is convenient for some perception and tracking datasets, but it is not the
reference point of the current ODE. Converting a body-centre state to this ODE
requires a consistent kinematic transformation of position and velocity.
Using body-centre coordinates while retaining the rear-axle ODE would create
an internally inconsistent model and could invalidate swept-footprint and
resource-occupancy claims.
