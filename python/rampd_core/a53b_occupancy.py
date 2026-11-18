"""Sufficient incumbent/no-reentry proof for static closed rectangular resources.

The entry history at mission start is *not* certified: already strictly inside
is an incumbent relative to the current planning horizon. All later boundary
instants inherit continuous state. No sampled endpoint transition is a proof.
"""
from .footprint import SweptFootprint
from .resources import ResourceRegion
from .interval import Interval


def strictly_inside(fp: SweptFootprint, region: ResourceRegion) -> bool:
    a = fp.aabb
    return (region.x.lo < a.x.lo <= a.x.hi < region.x.hi and
            region.y.lo < a.y.lo <= a.y.hi < region.y.hi)


def no_new_entry_proved(start: SweptFootprint, swept: SweptFootprint,
                        region: ResourceRegion, velocity, yaw_rate: Interval) -> bool:
    """No 0->1 occupancy transition on slab, including its left instant.

    Strict interior for whole slab suffices. Otherwise start must be wholly
    strictly interior and heading constant, with each center coordinate
    monotone (possibly different signs). For each material point its membership
    time in a rectangle is a prefix interval: its two coordinate memberships
    are prefix intervals, so is their intersection. The union over material
    points is also a prefix interval. Thus an exit cannot be followed by entry.
    The caller must bind all inputs to the same verified continuous trajectory.
    """
    if (start.start_time != start.end_time or start.start_time != swept.start_time
        or start.geometry != swept.geometry or start.vehicle_id != swept.vehicle_id):
        return False
    if not strictly_inside(start, region):
        return False
    if strictly_inside(swept, region):
        return True
    return (yaw_rate.lo == yaw_rate.hi == 0 and len(velocity)==2 and
            all(v.lo >= 0 or v.hi <= 0 for v in velocity))
