"""Finite closed binary64 intervals; every arithmetic bound is computed in C/MPFR.

A float input denotes its exact binary value. Use Interval.from_decimal() to
include an exact decimal literal. No epsilon or ordinary libm is a certificate.
"""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import ctypes as C
import math
import os
from typing import Iterable

class IntervalError(RuntimeError):
    """An interval operation could not produce a valid finite enclosure."""

@dataclass(frozen=True)
class Interval:
    lo: float
    hi: float
    def __post_init__(self):
        lo, hi = float(self.lo), float(self.hi)
        if not (math.isfinite(lo) and math.isfinite(hi) and lo <= hi):
            raise ValueError(f"invalid finite interval [{lo}, {hi}]")
        object.__setattr__(self, "lo", lo)
        object.__setattr__(self, "hi", hi)
    @classmethod
    def point(cls, x: float) -> Interval:
        return cls(x, x)
    @classmethod
    def from_decimal(cls, text: str) -> Interval:
        lo, hi = _D(), _D()
        _check(_LIB.rampd_interval_decimal(text.encode("ascii"), C.byref(lo), C.byref(hi)))
        return cls(lo.value, hi.value)
    def contains(self, value: float | Interval) -> bool:
        if isinstance(value, Interval):
            return self.lo <= value.lo and value.hi <= self.hi
        return self.lo <= value <= self.hi
    def interior_contains(self, other: Interval) -> bool:
        return self.lo < other.lo and other.hi < self.hi
    def __add__(self, other): return add(self, _coerce(other))
    def __radd__(self, other): return add(_coerce(other), self)
    def __sub__(self, other): return sub(self, _coerce(other))
    def __rsub__(self, other): return sub(_coerce(other), self)
    def __mul__(self, other): return mul(self, _coerce(other))
    def __rmul__(self, other): return mul(_coerce(other), self)
    def __truediv__(self, other): return div(self, _coerce(other))
    def __neg__(self): return Interval(-self.hi, -self.lo)
    def width_upper(self) -> float:
        return sub(Interval.point(self.hi), Interval.point(self.lo)).hi

def _coerce(x):
    return x if isinstance(x, Interval) else Interval.point(float(x))

def _load_library():
    explicit = os.environ.get("RAMPD_INTERVAL_LIB")
    root = Path(__file__).resolve().parents[2]
    candidates = [Path(explicit)] if explicit else [
        root / "build_phase1c" / "librampd_interval.so"]
    for p in candidates:
        if not p.is_file():
            continue
        lib = C.CDLL(str(p.resolve()))
        try:
            lib.rampd_abi_version.restype = C.c_int
            if lib.rampd_abi_version() != 2:
                raise AttributeError("ABI mismatch")
        except AttributeError as exc:
            raise ImportError(f"Stale/incompatible backend at {p}. Build Phase 1C; do not load a stale native library.") from exc
        return lib, str(p.resolve())
    raise FileNotFoundError("Phase 1B backend not found. Run scripts/validate_phase1c.sh; "
                            "or set RAMPD_INTERVAL_LIB to the NEW library's absolute path.")

_LIB, LIBRARY_PATH = _load_library()
_D, _P = C.c_double, C.POINTER(C.c_double)
for _name in ("add", "sub", "mul", "div"):
    fn = getattr(_LIB, "rampd_interval_" + _name)
    fn.argtypes, fn.restype = [_D, _D, _D, _D, _P, _P], C.c_int
for _name in ("square", "sin", "cos", "tan"):
    fn = getattr(_LIB, "rampd_interval_" + _name)
    fn.argtypes, fn.restype = [_D, _D, _P, _P], C.c_int
_LIB.rampd_interval_decimal.argtypes = [C.c_char_p, _P, _P]
_LIB.rampd_interval_decimal.restype = C.c_int
_LIB.rampd_interval_pi.argtypes = [_P, _P]
_LIB.rampd_interval_pi.restype = C.c_int
_LIB.rampd_bicycle_rhs.argtypes = [_P, _P, _P, _P, _P, _P, _D, _P, _P]
_LIB.rampd_bicycle_rhs.restype = C.c_int
_LIB.rampd_friction_lhs.argtypes = [_P, _P, _D, _D, _D, _P, _P]
_LIB.rampd_friction_lhs.restype = C.c_int
for _name in ("rampd_interval_backend", "rampd_last_error", "rampd_build_info"):
    getattr(_LIB, _name).argtypes = []
    getattr(_LIB, _name).restype = C.c_char_p

def _check(rc):
    if rc:
        raise IntervalError(f"native status {rc}: {_LIB.rampd_last_error().decode('utf-8')}")

def backend_name() -> str:
    return _LIB.rampd_interval_backend().decode("ascii")

def build_info() -> str:
    return _LIB.rampd_build_info().decode("ascii")

def _call_scalar(name: str, *args: float) -> Interval:
    lo, hi = _D(), _D()
    _check(getattr(_LIB, name)(*args, C.byref(lo), C.byref(hi)))
    return Interval(lo.value, hi.value)

def add(a, b): return _call_scalar("rampd_interval_add", a.lo, a.hi, b.lo, b.hi)
def sub(a, b): return _call_scalar("rampd_interval_sub", a.lo, a.hi, b.lo, b.hi)
def mul(a, b): return _call_scalar("rampd_interval_mul", a.lo, a.hi, b.lo, b.hi)
def div(a, b): return _call_scalar("rampd_interval_div", a.lo, a.hi, b.lo, b.hi)
def square(a): return _call_scalar("rampd_interval_square", a.lo, a.hi)
def sin(a): return _call_scalar("rampd_interval_sin", a.lo, a.hi)
def cos(a): return _call_scalar("rampd_interval_cos", a.lo, a.hi)
def tan(a): return _call_scalar("rampd_interval_tan", a.lo, a.hi)
def pi_interval(): return _call_scalar("rampd_interval_pi")

def _arrays(intervals: Iterable[Interval]):
    xs = tuple(intervals)
    if not all(isinstance(x, Interval) for x in xs):
        raise TypeError("expected Interval objects")
    return ((_D * len(xs))(*[x.lo for x in xs]), (_D * len(xs))(*[x.hi for x in xs]))

def _read_pair(lo, hi, n):
    return tuple(Interval(lo[i], hi[i]) for i in range(n))

def bicycle_rhs(state, control, wheelbase, derivative_disturbance=None):
    if len(state) != 6 or len(control) != 2:
        raise ValueError("state must have 6 and control 2 intervals")
    w = tuple(Interval(0, 0) for _ in range(6)) if derivative_disturbance is None else tuple(derivative_disturbance)
    if len(w) != 6:
        raise ValueError("derivative disturbance must have 6 intervals")
    xl, xh = _arrays(state); ul, uh = _arrays(control); wl, wh = _arrays(w)
    lo, hi = (_D * 6)(), (_D * 6)()
    _check(_LIB.rampd_bicycle_rhs(xl, xh, ul, uh, wl, wh, wheelbase, lo, hi))
    return _read_pair(lo, hi, 6)

def friction_lhs(state, wheelbase, mu, gravity):
    if len(state) != 6:
        raise ValueError("state must have 6 intervals")
    xl, xh = _arrays(state); lo, hi = _D(), _D()
    _check(_LIB.rampd_friction_lhs(xl, xh, wheelbase, mu, gravity, C.byref(lo), C.byref(hi)))
    return Interval(lo.value, hi.value)
