"""Exact rational time versus binary64 endpoints; no epsilon matching."""
from fractions import Fraction
import math


def binary64_bracket(q: Fraction) -> tuple[float, float]:
    if type(q) is not Fraction or q < 0:
        raise ValueError('nonnegative exact Fraction required')
    f = float(q)
    if not math.isfinite(f):
        raise ValueError('time not representable by finite binary64 enclosure')
    fq = Fraction.from_float(f)
    lo = math.nextafter(f, -math.inf) if fq > q else f
    hi = math.nextafter(f, math.inf) if fq < q else f
    if not math.isfinite(hi) or not Fraction.from_float(lo) <= q <= Fraction.from_float(hi):
        raise ValueError('invalid time enclosure')
    return lo, hi
