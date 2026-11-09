"""Exact-rational arithmetic checks plus independent high-precision audits.
The mpmath checks are falsification tests, not formal transcendental proofs.
"""
import math
import random
import sys
from fractions import Fraction as Q
from concurrent.futures import ThreadPoolExecutor
import mpmath as mp
import pytest
from rampd_core import *

@pytest.mark.parametrize("operation,exact", [(add,lambda x,y:x+y), (sub,lambda x,y:x-y),
                                              (mul,lambda x,y:x*y), (div,lambda x,y:x/y)])
def test_arithmetic_against_exact_rational_corners(operation, exact):
    rng = random.Random(6402)
    for _ in range(300):
        a = sorted([rng.uniform(-100, 100), rng.uniform(-100, 100)])
        b = sorted([rng.uniform(.01, 20), rng.uniform(.01, 20)])
        if rng.random() < .5: b = [-b[1], -b[0]]
        result = operation(Interval(*a), Interval(*b))
        corners = [exact(Q(x), Q(y)) for x in a for y in b]
        assert Q(result.lo) <= min(corners)
        assert Q(result.hi) >= max(corners)

@pytest.mark.parametrize("value", ["0.1", "-0.1", "2.8", "1e-320", "-1e-320", "0", "123456789.0123456789"])
def test_decimal_literal_is_enclosed(value):
    z = Interval.from_decimal(value)
    assert Q(z.lo) <= Q(value) <= Q(z.hi)

@pytest.mark.parametrize("value", ["", "abc", "1xyz", "nan", "inf", "1e10000"])
def test_invalid_decimal_rejected(value):
    with pytest.raises((ValueError, IntervalError)):
        Interval.from_decimal(value)

@pytest.mark.parametrize("fun,reference", [(sin,mp.sin), (cos,mp.cos)])
def test_trig_critical_points_and_wide_ranges(fun, reference):
    rng = random.Random(317)
    cases = [(-10, 10), (-.1, .1), (0, 0), (1e20, 1e20), (-1e20, -1e20)]
    for k in range(-15, 16):
        c = k * math.pi / 2
        cases.append((math.nextafter(c, -math.inf), math.nextafter(c, math.inf)))
    cases += [(v := rng.uniform(-1e6, 1e6), v + rng.uniform(0, 8)) for _ in range(120)]
    with mp.workdps(100):
        for lo, hi in cases:
            result = fun(Interval(lo, hi))
            for numerator in range(9):
                point = mp.mpf(lo) + (mp.mpf(hi)-mp.mpf(lo))*numerator/8
                value = reference(point)
                assert mp.mpf(result.lo) <= value <= mp.mpf(result.hi)

def test_tan_multiple_branches_and_poles():
    with mp.workdps(100):
        for k in range(-4, 5):
            c = k * math.pi
            z = tan(Interval(c-.2, c+.2))
            for x in (c-.2, c, c+.2):
                assert mp.mpf(z.lo) <= mp.tan(mp.mpf(x)) <= mp.mpf(z.hi)
            pole = c + math.pi/2
            with pytest.raises(IntervalError): tan(Interval(pole-.01, pole+.01))

def test_subnormal_and_overflow_handling():
    tiny = math.nextafter(0, 1)
    z = mul(Interval.point(tiny), Interval.point(.5))
    assert z.lo == 0 and z.hi == tiny
    z = mul(Interval.point(-tiny), Interval.point(.5))
    assert z.lo == -tiny and z.hi == 0
    with pytest.raises(IntervalError):
        mul(Interval.point(sys.float_info.max), Interval.point(2))

@pytest.mark.parametrize("value", [math.nan, math.inf, -math.inf, 0, -1])
def test_nonfinite_and_invalid_parameters(value):
    with pytest.raises(ValueError): BicycleParameters(value, .9)
    with pytest.raises(ValueError): BicycleParameters(2.8, value)
    with pytest.raises(ValueError): BicycleParameters(2.8, .9, value)

def test_friction_point_checked_without_prerounding_mu_g():
    rng = random.Random(9007)
    with mp.workdps(100):
        for _ in range(100):
            L, mu, g = rng.uniform(2,4), rng.uniform(.3,1.1), rng.uniform(9.7,9.9)
            v, a, d = rng.uniform(0,30), rng.uniform(-4,4), rng.uniform(-.4,.4)
            p = BicycleParameters(L,mu,g); x = StateBounds.point([0,0,0,v,a,d])
            z = friction_value_enclosure(x,p)
            vv,aa,dd,ll,mm,gg = map(mp.mpf, (v,a,d,L,mu,g))
            exact = (aa/(mm*gg))**2 + (vv**2*mp.tan(dd)/(ll*mm*gg))**2
            assert mp.mpf(z.lo) <= exact <= mp.mpf(z.hi)

def test_monotone_enclosure_under_box_extension():
    for fn in (sin, cos, square):
        for x in (-4, -1, 0, .2, 2, 4):
            small = fn(Interval(x-.01,x+.01)); large = fn(Interval(x-.1,x+.1))
            assert large.contains(small)

def test_threaded_determinism():
    xs = [Interval(i/100, (i+1)/100) for i in range(-200,200)]
    baseline = [sin(x) for x in xs]
    with ThreadPoolExecutor(max_workers=4) as executor:
        assert list(executor.map(sin,xs)) == baseline
