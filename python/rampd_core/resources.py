"""Conservative dynamic-resource and complete-footprint checks for Phase 4.

Resource occupancy is evaluated from swept full-body AABBs.  Overlap means
``MAYBE_OCCUPIED`` and is charged to capacity; only a proved separating AABB
or a uniformly separating interval SAT inequality returns ``PROVED_FREE``.  This deliberately prefers ``UNKNOWN`` to silently
under-counting a vehicle or treating an entry gate as a collision-free point.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from .footprint import SweptFootprint
from .interval import Interval, sin, cos


class OccupancyStatus(str, Enum):
    PROVED_FREE = "PROVED_FREE"
    PROVED_OCCUPIED = "PROVED_OCCUPIED"
    MAYBE_OCCUPIED = "MAYBE_OCCUPIED"


class ResourceStatus(str, Enum):
    SAFE = "SAFE"
    VIOLATION = "VIOLATION"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class ResourceRegion:
    resource_id: str
    x: Interval
    y: Interval
    capacity: int = 1
    demand_unit: int = 1

    def __post_init__(self):
        if not self.resource_id or not isinstance(self.x, Interval) or not isinstance(self.y, Interval):
            raise TypeError("resource bounds must be Interval objects")
        if type(self.capacity) is not int or type(self.demand_unit) is not int or self.capacity < 0 or self.demand_unit <= 0:
            raise ValueError("invalid resource region")
        object.__setattr__(self, "capacity", int(self.capacity))
        object.__setattr__(self, "demand_unit", int(self.demand_unit))


@dataclass(frozen=True)
class ResourceState:
    resource_id: str
    alpha: bool
    beta: bool
    direction: str
    capacity: int
    controller_state: str = ""

    def __post_init__(self):
        if not self.resource_id or not self.direction or type(self.capacity) is not int or self.capacity < 0:
            raise ValueError("invalid resource state")
        if not isinstance(self.alpha, bool) or not isinstance(self.beta, bool):
            raise TypeError("alpha and beta must be bool values")
        object.__setattr__(self, "alpha", bool(self.alpha))
        object.__setattr__(self, "beta", bool(self.beta))
        object.__setattr__(self, "capacity", int(self.capacity))


@dataclass(frozen=True)
class ActorFootprint:
    actor_id: str
    swept: SweptFootprint
    demand: int = 1
    demand_unit: int = 1
    direction: str | None = None
    already_inside: tuple[str, ...] = ()

    def __post_init__(self):
        if not self.actor_id or not isinstance(self.swept, SweptFootprint):
            raise TypeError("actor footprint requires a SweptFootprint")
        if type(self.demand) is not int or type(self.demand_unit) is not int or self.demand <= 0 or self.demand_unit <= 0:
            raise ValueError("invalid actor footprint")
        object.__setattr__(self, "demand", int(self.demand))
        object.__setattr__(self, "demand_unit", int(self.demand_unit))
        object.__setattr__(self, "already_inside", tuple(sorted(set(self.already_inside))))


@dataclass(frozen=True)
class Occupancy:
    actor_id: str
    resource_id: str
    status: OccupancyStatus
    load: int
    reason: str


@dataclass(frozen=True)
class ResourceCheck:
    status: ResourceStatus
    reason: str
    occupancies: tuple[Occupancy, ...] = ()
    unresolved: tuple[str, ...] = ()


def _aabb_separated(aabb, region: ResourceRegion):
    return (aabb.x.hi < region.x.lo or aabb.x.lo > region.x.hi or
            aabb.y.hi < region.y.lo or aabb.y.lo > region.y.hi)


def _abs_interval(x: Interval) -> Interval:
    """Outward absolute value: endpoint magnitudes are exact binary64 values."""
    return Interval(0.0 if x.lo <= 0 <= x.hi else min(abs(x.lo),abs(x.hi)),
                    max(abs(x.lo),abs(x.hi)))


def rectangular_sat_bounds(fp: SweptFootprint, region: ResourceRegion):
    """Four exact SAT axis formulas enclosed for *every* pose in the tube.

    The body axes vary with heading; the formulas are evaluated with directed
    interval arithmetic, not midpoint axes or two overlapping outer boxes.
    Return (absolute center separation, combined support radius) per axis.
    """
    px,py,psi=fp.state_tube.px,fp.state_tube.py,fp.state_tube.psi
    c,s=cos(psi),sin(psi); ac,ass=_abs_interval(c),_abs_interval(s)
    g=fp.geometry; hx,hy=g.half_length_interval,g.half_width_interval
    ox,oy=Interval.point(g.center_offset_x_m),Interval.point(g.center_offset_y_m)
    xl,xh=Interval.point(region.x.lo),Interval.point(region.x.hi)
    yl,yh=Interval.point(region.y.lo),Interval.point(region.y.hi)
    rx,ry=(xh-xl)/2,(yh-yl)/2
    dx=px-(xl+xh)/2;dy=py-(yl+yh)/2
    # Body projections of the reference displacement plus the body offsets.
    # Do not numerically apply R^T R to those offsets: the rotation is exact.
    return (( _abs_interval(dx+c*ox-s*oy),rx+hx*ac+hy*ass),
            ( _abs_interval(dy+s*ox+c*oy),ry+hx*ass+hy*ac),
            ( _abs_interval(c*dx+s*dy+ox),hx+rx*ac+ry*ass),
            ( _abs_interval(-s*dx+c*dy+oy),hy+rx*ass+ry*ac))


def strict_rectangular_overlap(fp: SweptFootprint, region: ResourceRegion) -> bool:
    """Every enclosed pose has positive-area intersection (no touch-only)."""
    return (region.x.lo < region.x.hi and region.y.lo < region.y.hi and
            all(d.hi < r.lo for d,r in rectangular_sat_bounds(fp,region)))


def rectangular_separated(fp: SweptFootprint, region: ResourceRegion) -> bool:
    """A separating inequality holds uniformly; contact is not separation."""
    return any(d.lo > r.hi for d,r in rectangular_sat_bounds(fp,region))


def occupancy(actor: ActorFootprint, region: ResourceRegion) -> Occupancy:
    aabb_free = _aabb_separated(actor.swept.aabb, region)
    if aabb_free or rectangular_separated(actor.swept, region):
        # ``already_inside`` is part of the resource contract.  A declared
        # in-resource actor cannot be silently discharged by a geometrically
        # disjoint swept outer approximation; the two pieces of evidence are
        # inconsistent and must remain unresolved.
        if region.resource_id in actor.already_inside:
            return Occupancy(actor.actor_id, region.resource_id,
                             OccupancyStatus.MAYBE_OCCUPIED, actor.demand,
                             "DECLARED_INSIDE_BUT_FOOTPRINT_SEPARATED")
        return Occupancy(actor.actor_id, region.resource_id, OccupancyStatus.PROVED_FREE, 0,
                         "FULL_FOOTPRINT_AABB_SEPARATED" if aabb_free else "FULL_FOOTPRINT_INTERVAL_SAT_SEPARATED")
    # The AABB overlap proves only possibility; it is intentionally charged
    # against capacity instead of being interpreted as no occupancy.
    if actor.demand_unit != region.demand_unit or actor.demand % actor.demand_unit:
        return Occupancy(actor.actor_id, region.resource_id, OccupancyStatus.MAYBE_OCCUPIED,
                         actor.demand, "CAPACITY_UNIT_UNRESOLVED")
    return Occupancy(actor.actor_id, region.resource_id, OccupancyStatus.MAYBE_OCCUPIED,
                     actor.demand // actor.demand_unit, "FULL_FOOTPRINT_MAY_INTERSECT")


def check_resources(states: tuple[ResourceState, ...], regions: tuple[ResourceRegion, ...],
                    actors: tuple[ActorFootprint, ...],
                    conflicts: tuple[tuple[str, str], ...] = ()) -> ResourceCheck:
    states = tuple(states); regions = tuple(regions); actors = tuple(actors)
    if len({s.resource_id for s in states}) != len(states):
        return ResourceCheck(ResourceStatus.UNKNOWN, "DUPLICATE_RESOURCE_STATE_ID")
    if len({r.resource_id for r in regions}) != len(regions):
        return ResourceCheck(ResourceStatus.UNKNOWN, "DUPLICATE_RESOURCE_REGION_ID")
    smap = {s.resource_id: s for s in states}; rmap = {r.resource_id: r for r in regions}
    if set(smap) != set(rmap):
        return ResourceCheck(ResourceStatus.UNKNOWN, "RESOURCE_STATE_REGION_MISMATCH")
    if len({a.actor_id for a in actors}) != len(actors):
        return ResourceCheck(ResourceStatus.UNKNOWN, "DUPLICATE_ACTOR_ID")
    known_resources = set(rmap)
    if any(resource_id not in known_resources
           for actor in actors for resource_id in actor.already_inside):
        return ResourceCheck(ResourceStatus.UNKNOWN, "ACTOR_REFERENCES_UNKNOWN_RESOURCE")
    all_occ = []
    unresolved = []
    for rid in sorted(rmap):
        region, state = rmap[rid], smap[rid]
        if state.capacity != region.capacity:
            return ResourceCheck(ResourceStatus.UNKNOWN, "CAPACITY_CONTRACT_MISMATCH")
        current = []
        for actor in actors:
            item = occupancy(actor, region)
            all_occ.append(item)
            if item.status is not OccupancyStatus.PROVED_FREE:
                current.append((actor, item))
                if item.reason == "CAPACITY_UNIT_UNRESOLVED":
                    unresolved.append(f"{actor.actor_id}:{rid}:CAPACITY_UNIT_UNRESOLVED")
                if item.reason == "DECLARED_INSIDE_BUT_FOOTPRINT_SEPARATED":
                    unresolved.append(f"{actor.actor_id}:{rid}:DECLARED_INSIDE_GEOMETRY_INCONSISTENT")
                if actor.direction is None:
                    unresolved.append(f"{actor.actor_id}:{rid}:DIRECTION_UNKNOWN")
                elif actor.direction != state.direction:
                    # AABB overlap is only a possible occupancy.  It cannot
                    # by itself prove that a concrete trajectory violated the
                    # direction guard; retain the obligation as UNKNOWN.
                    unresolved.append(f"DIRECTION_NOT_ALLOWED_POSSIBLE:{actor.actor_id}:{rid}")
                if rid not in actor.already_inside and not state.alpha:
                    unresolved.append(f"ENTRY_CLOSED_POSSIBLE:{actor.actor_id}:{rid}")
                if not state.beta:  # possible swept occupancy can persist after entry
                    unresolved.append(f"STAY_CLOSED_POSSIBLE:{actor.actor_id}:{rid}")
        load = sum(item.load for _, item in current)
        if load > state.capacity:
            unresolved.append(f"CAPACITY_EXCEEDED_POSSIBLE:{rid}")
    # Unknown occupancy is deliberately not promoted to a concrete collision;
    # a conflict involving two possible occupancies remains unresolved.
    for left, right in conflicts:
        if left not in rmap or right not in rmap or left == right:
            return ResourceCheck(ResourceStatus.UNKNOWN, "INVALID_CONFLICT_EDGE", tuple(all_occ))
        for actor in actors:
            a_left = occupancy(actor, rmap[left]); a_right = occupancy(actor, rmap[right])
            for other in actors:
                if other.actor_id == actor.actor_id:
                    continue
                b_left = occupancy(other, rmap[left]); b_right = occupancy(other, rmap[right])
                # A conflict is cross-resource: i in r and j in s, or i in s
                # and j in r.  A single long actor spanning both resources is
                # not a two-vehicle conflict.
                cross = ((a_left.status is not OccupancyStatus.PROVED_FREE and
                          b_right.status is not OccupancyStatus.PROVED_FREE) or
                         (a_right.status is not OccupancyStatus.PROVED_FREE and
                          b_left.status is not OccupancyStatus.PROVED_FREE))
                if cross:
                    unresolved.append(f"CONFLICT_MAY_OCCUR:{actor.actor_id}:{other.actor_id}:{left}:{right}")
    if unresolved:
        return ResourceCheck(ResourceStatus.UNKNOWN, "RESOURCE_OCCUPANCY_OR_CONFLICT_UNRESOLVED",
                             tuple(all_occ), tuple(sorted(set(unresolved))))
    return ResourceCheck(ResourceStatus.SAFE, "RESOURCE_RULES_PROVED", tuple(all_occ))
