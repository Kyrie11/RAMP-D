"""Native-only regression: no ordinary floating backend substitution."""
from fractions import Fraction as Q
from math import pi
import pytest
from rampd_core.interval import Interval
from rampd_core.model import StateBounds
from rampd_core.footprint import SweptFootprint,VehicleGeometry
from rampd_core.resources import (ResourceRegion,ResourceState,ActorFootprint,OccupancyStatus,ResourceStatus,
    strict_rectangular_overlap,rectangular_separated,occupancy,check_resources)
from rampd_core.a53b_occupancy import no_new_entry_proved


def fp(x,y,psi,length=8.,width=1.,start=Q(0),end=Q(0),offset=(0.,0.)):
    z=Interval.point(0)
    return SweptFootprint(StateBounds(x,y,psi,z,z,z),VehicleGeometry(length,width,*offset),start,end,'ego')


def test_cross_overlap_no_corner_or_center_witness_and_rotation_stays_occupied():
    # Resource far from vehicle center, narrow vertical bar intersects its body.
    r=ResourceRegion('r',Interval(2,3),Interval(-3,3))
    a=fp(Interval.point(0),Interval.point(0),Interval.point(0))
    b=fp(Interval(-.01,.01),Interval(-.01,.01),Interval(-.02,.02),end=Q(1))
    assert strict_rectangular_overlap(a,r) and strict_rectangular_overlap(b,r)
    assert no_new_entry_proved(a,b,r,(Interval(-1,1),Interval(-1,1)),Interval(-1,1))
    # Boundary touch is not a strict initial incumbent.
    touch=ResourceRegion('r',Interval(4,5),Interval(-.1,.1))
    assert not strict_rectangular_overlap(a,touch)
    assert not rectangular_separated(a,touch)


def test_rotated_box_body_axis_excludes_aabb_false_positive():
    a=fp(Interval.point(0),Interval.point(0),Interval.point(pi/4))
    r=ResourceRegion('r',Interval(2,2.1),Interval(-2.1,-2))
    assert a.aabb.x.hi>2 and a.aabb.y.lo<-2
    assert rectangular_separated(a,r)
    actor=ActorFootprint('ego',a,direction='forward')
    assert occupancy(actor,r).status is OccupancyStatus.PROVED_FREE


def test_body_offset_and_uncertain_overlap_not_promoted():
    a=fp(Interval.point(0),Interval.point(0),Interval.point(0),2.,1.,offset=(2.,0.))
    r=ResourceRegion('r',Interval(2,2.2),Interval(-.1,.1))
    assert strict_rectangular_overlap(a,r)
    b=fp(Interval(-10,0),Interval.point(0),Interval.point(0),2.,1.,offset=(2.,0.))
    assert not strict_rectangular_overlap(b,r) and not rectangular_separated(b,r)


def test_stay_forbidden_even_when_entry_allowed():
    a=fp(Interval.point(0),Interval.point(0),Interval.point(0),end=Q(1))
    r=ResourceRegion('r',Interval(-1,1),Interval(-1,1))
    result=check_resources((ResourceState('r',True,False,'forward',1),),(r,),(ActorFootprint('ego',a,direction='forward'),))
    assert result.status is ResourceStatus.UNKNOWN
    assert any('STAY_CLOSED' in x for x in result.unresolved)
