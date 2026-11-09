"""Python wrapper around the C++ outward-rounded interval backend."""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import ctypes as C
import math
import os
from typing import Iterable


class IntervalError(RuntimeError):
    pass

@dataclass(frozen=True)
class Interval:
    lo: float
    hi: float
    def __post_init__(self):
        if not (math.isfinite(self.lo) and math.isfinite(self.hi) and self.lo <= self.hi):
            raise ValueError(f"invalid finite interval [{self.lo}, {self.hi}]")


def _load_library():
    candidates = []
    if os.environ.get("RAMPD_INTERVAL_LIB"):
        candidates.append(Path(os.environ["RAMPD_INTERVAL_LIB"]))
    root = Path(__file__).resolve().parents[2]
    candidates += [root / "build" / "librampd_interval.so", root / "build" / "librampd_interval.dylib", root / "build" / "rampd_interval.dll"]
    for p in candidates:
        if p.exists():
            return C.CDLL(str(p))
    raise FileNotFoundError("C++ backend not found; build with cmake -S . -B build && cmake --build build")

_LIB = _load_library()
_D = C.c_double
_P = C.POINTER(_D)
for _name in ("rampd_interval_add", "rampd_interval_mul", "rampd_interval_div"):
    _fn = getattr(_LIB, _name); _fn.argtypes = [_D,_D,_D,_D,_P,_P]; _fn.restype=C.c_int
for _name in ("rampd_interval_sin", "rampd_interval_cos", "rampd_interval_tan"):
    _fn = getattr(_LIB, _name); _fn.argtypes = [_D,_D,_P,_P]; _fn.restype=C.c_int
_LIB.rampd_bicycle_rhs.argtypes = [_P,_P,_P,_P,_P,_P,_D,_P,_P]
_LIB.rampd_bicycle_rhs.restype = C.c_int
_LIB.rampd_friction_lhs.argtypes = [_P,_P,_D,_D,_D,_P,_P]
_LIB.rampd_friction_lhs.restype = C.c_int
_LIB.rampd_interval_backend.restype = C.c_char_p


def backend_name() -> str:
    return _LIB.rampd_interval_backend().decode("ascii")

def _call_scalar(name: str, *args: float) -> Interval:
    lo, hi = _D(), _D()
    rc = getattr(_LIB, name)(*map(_D,args), C.byref(lo), C.byref(hi))
    if rc: raise IntervalError(f"{name} failed (backend status {rc})")
    return Interval(lo.value, hi.value)

def add(a: Interval,b: Interval) -> Interval: return _call_scalar("rampd_interval_add",a.lo,a.hi,b.lo,b.hi)
def mul(a: Interval,b: Interval) -> Interval: return _call_scalar("rampd_interval_mul",a.lo,a.hi,b.lo,b.hi)
def div(a: Interval,b: Interval) -> Interval: return _call_scalar("rampd_interval_div",a.lo,a.hi,b.lo,b.hi)
def sin(a: Interval) -> Interval: return _call_scalar("rampd_interval_sin",a.lo,a.hi)
def cos(a: Interval) -> Interval: return _call_scalar("rampd_interval_cos",a.lo,a.hi)
def tan(a: Interval) -> Interval: return _call_scalar("rampd_interval_tan",a.lo,a.hi)

def _arrays(intervals: Iterable[Interval]):
    xs=list(intervals)
    return ( (_D*len(xs))(*[x.lo for x in xs]), (_D*len(xs))(*[x.hi for x in xs]) )

def _read_pair(lo,hi,n): return tuple(Interval(lo[i],hi[i]) for i in range(n))

def bicycle_rhs(state: tuple[Interval,...], control: tuple[Interval,...], wheelbase: float,
                derivative_disturbance: tuple[Interval,...] | None = None) -> tuple[Interval,...]:
    """Interval extension of the paper's six-state kinematic bicycle ODE.

    Disturbance is an explicitly supplied additive derivative box. The paper
    does not specify its injection matrix/units; default is exactly zero.
    """
    if len(state)!=6 or len(control)!=2: raise ValueError("state must have 6 and control 2 intervals")
    if derivative_disturbance is None: derivative_disturbance=tuple(Interval(0.0,0.0) for _ in range(6))
    if len(derivative_disturbance)!=6: raise ValueError("derivative_disturbance must have 6 intervals")
    xl,xh=_arrays(state); ul,uh=_arrays(control); wl,wh=_arrays(derivative_disturbance)
    ol=( _D*6 )(); oh=( _D*6 )()
    rc=_LIB.rampd_bicycle_rhs(xl,xh,ul,uh,wl,wh,_D(wheelbase),ol,oh)
    if rc: raise IntervalError(f"bicycle RHS failed (backend status {rc})")
    return _read_pair(ol,oh,6)

def friction_lhs(state: tuple[Interval,...], wheelbase: float, mu: float, gravity: float) -> Interval:
    if len(state)!=6: raise ValueError("state must have 6 intervals")
    xl,xh=_arrays(state); lo,hi=_D(),_D()
    rc=_LIB.rampd_friction_lhs(xl,xh,_D(wheelbase),_D(mu),_D(gravity),C.byref(lo),C.byref(hi))
    if rc: raise IntervalError(f"friction evaluation failed (backend status {rc})")
    return Interval(lo.value,hi.value)
