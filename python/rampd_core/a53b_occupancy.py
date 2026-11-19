"""Sufficient incumbent/no-reentry proof for static closed rectangular resources.

The entry history at mission start is *not* certified: already strictly inside
is an incumbent relative to the current planning horizon. All later boundary
instants inherit continuous state. No sampled endpoint transition is a proof.
"""
from .footprint import SweptFootprint
from .resources import ResourceRegion, strict_rectangular_overlap
from .interval import Interval, sin, cos


def strictly_inside(fp: SweptFootprint, region: ResourceRegion) -> bool:
    a = fp.aabb
    return (region.x.lo < a.x.lo <= a.x.hi < region.x.hi and
            region.y.lo < a.y.lo <= a.y.hi < region.y.hi)


def no_new_entry_proved(start: SweptFootprint, swept: SweptFootprint,
                        region: ResourceRegion, velocity, yaw_rate: Interval) -> bool:
    """No 0->1 occupancy transition on slab, including its left instant.

    Strict interior for whole slab suffices. If start is wholly strictly
    interior, constant heading and monotone world coordinates suffice. For each material point its membership
    time in a rectangle is a prefix interval: its two coordinate memberships
    are prefix intervals, so is their intersection. The union over material
    points is also a prefix interval. Thus an exit cannot be followed by entry.
    For partial initial overlap the four configuration-space facet projections
    must instead be monotone and strict overlap for every possible initial pose.
    The caller must bind all inputs to the same verified continuous trajectory.
    """
    if (start.start_time != start.end_time or start.start_time != swept.start_time
        or start.geometry != swept.geometry or start.vehicle_id != swept.vehicle_id):
        return False
    initial_inside = strictly_inside(start, region)
    # Every pose in the slab overlaps strictly, even with changing heading.
    if (initial_inside and strictly_inside(swept, region)) or (
            strict_rectangular_overlap(start,region) and strict_rectangular_overlap(swept,region)):
        return True
    if yaw_rate.lo != 0 or yaw_rate.hi != 0 or len(velocity)!=2:
        return False
    monotone=lambda v: v.lo>=0 or v.hi<=0
    if not all(monotone(v) for v in velocity): return False
    if initial_inside: return True
    # More general: prove strict initial overlap using interval SAT. For a fixed heading, the set of reference positions
    # whose body intersects the rectangular resource is a convex Minkowski sum.
    # Its facet normals are the two world axes and the two body axes. If each
    # of the four projected velocities has fixed sign, every defining slab
    # has prefix membership starting at t0; their intersection is a prefix.
    # Heading may be uncertain across traces but is constant along each trace.
    psi=start.state_tube.psi; c,s=cos(psi),sin(psi)
    vx,vy=velocity
    if not monotone(c*vx+s*vy) or not monotone(-s*vx+c*vy): return False
    return strict_rectangular_overlap(start,region)
