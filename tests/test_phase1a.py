import math
import pytest
from rampd_core import Interval, add, mul, div, sin, cos, tan, backend_name, BicycleParameters, StateBounds, ControlBounds, rhs, friction_value_enclosure

def test_backend_loaded():
    assert "Boost.Numeric.Interval" in backend_name()

def test_arithmetic_contains_extrema():
    assert add(Interval(1,2),Interval(3,4)) == Interval(4,6)
    z=mul(Interval(-2,3),Interval(4,5)); assert z.lo <= -10 and z.hi >= 15
    with pytest.raises(Exception): div(Interval(1,2),Interval(-1,1))

def test_trigonometric_enclosures():
    s=sin(Interval(-math.pi/2,math.pi/2)); c=cos(Interval(0,math.pi)); t=tan(Interval(-.2,.2))
    assert s.lo <= 0 and s.hi >= 1
    assert c.lo <= 0 and c.hi >= 1
    assert t.lo <= math.tan(-.2) and t.hi >= math.tan(.2)

def test_bicycle_rhs_matches_point_formula_inside_box():
    p=BicycleParameters(2.8,.9)
    x=StateBounds(Interval(0,0),Interval(0,0),Interval(.2,.3),Interval(10,11),Interval(1,2),Interval(.1,.2))
    u=ControlBounds(Interval(-1,1),Interval(-.1,.1))
    f=rhs(x,u,p)
    psi=.25; v=10.5; a=1.5; delta=.15; jerk=.2; steer=.03
    point=[v*math.cos(psi),v*math.sin(psi),v*math.tan(delta)/2.8,a,jerk,steer]
    for q,I in zip(point,f): assert I.lo <= q <= I.hi

def test_friction_constraint_interval():
    p=BicycleParameters(2.8,.9)
    x=StateBounds(Interval(0,0),Interval(0,0),Interval(0,0),Interval(5,5.1),Interval(.1,.2),Interval(.01,.02))
    z=friction_value_enclosure(x,p)
    assert 0 <= z.lo <= z.hi

def test_random_pointwise_rhs_and_friction_coverage():
    import random
    rng=random.Random(20261109)
    p=BicycleParameters(2.75,.85)
    for _ in range(250):
        psi0=rng.uniform(-1.0,1.0); v0=rng.uniform(0.2,20.0)
        a0=rng.uniform(-3.0,2.0); delta0=rng.uniform(-0.35,0.35)
        j0=rng.uniform(-4.0,3.0); sr0=rng.uniform(-0.25,0.25)
        x=StateBounds(Interval(-1,1),Interval(-1,1),Interval(psi0-.01,psi0+.01),
                      Interval(v0-.05,v0+.05),Interval(a0-.05,a0+.05),
                      Interval(delta0-.005,delta0+.005))
        u=ControlBounds(Interval(j0-.1,j0+.1),Interval(sr0-.01,sr0+.01))
        f=rhs(x,u,p)
        q=[v0*math.cos(psi0),v0*math.sin(psi0),v0*math.tan(delta0)/p.wheelbase_m,a0,j0,sr0]
        for val,I in zip(q,f): assert I.lo <= val <= I.hi
        fr=friction_value_enclosure(x,p)
        exact=(a0/(p.friction_coefficient*p.gravity_mps2))**2 + (v0*v0*math.tan(delta0)/(p.wheelbase_m*p.friction_coefficient*p.gravity_mps2))**2
        assert fr.lo <= exact <= fr.hi

def test_friction_square_nonnegative_when_acceleration_spans_zero():
    p=BicycleParameters(2.8,.9)
    x=StateBounds(Interval(0,0),Interval(0,0),Interval(0,0),Interval(0,1),Interval(-1,1),Interval(0,0))
    fr=friction_value_enclosure(x,p)
    assert fr.lo >= 0
