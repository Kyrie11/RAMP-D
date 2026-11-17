#!/usr/bin/env python3
"""Pure discrete SC/rank tests with a NO-CERTIFICATION value carrier.

Explicitly NOT MPFR / C++ / continuous reachability, and NEVER a replacement
for native tests. The carrier implements elementary interval containment used
by synthetic fixtures only; any physical friction proof raises an exception.
"""
import sys
from pathlib import Path
import types
from dataclasses import dataclass
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'python'))
pkg=types.ModuleType('rampd_core'); pkg.__path__=[str(ROOT/'python/rampd_core')]
sys.modules['rampd_core']=pkg
interval=types.ModuleType('rampd_core.interval')
@dataclass(frozen=True)
class CarrierInterval:
    lower: float
    upper: float
    def __post_init__(self):
        if self.lower > self.upper: raise ValueError('reversed bounds')
    @property
    def lo(self):
        return float(self.lower)
    @property
    def hi(self):
        return float(self.upper)
    def contains(self, other):
        return self.lo <= other.lo and other.hi <= self.hi
interval.Interval=CarrierInterval
sys.modules['rampd_core.interval']=interval
model=types.ModuleType('rampd_core.model')
@dataclass(frozen=True)
class CarrierStateBounds:
    slots: tuple
    def __init__(self, *values):
        if len(values)!=6: raise ValueError('six state coordinates required')
        object.__setattr__(self,'slots',tuple(values))
    @classmethod
    def point(cls, values):
        return cls(*(CarrierInterval(v,v) for v in values))
    def as_tuple(self):
        return self.slots
    def contains(self, other):
        return all(x.contains(y) for x,y in zip(self.slots,other.slots))
class NoFrictionProof:
    pass
def refuse_friction(*args):
    raise RuntimeError('no MPFR backend in this synthetic carrier')
model.StateBounds=CarrierStateBounds
model.BicycleParameters=NoFrictionProof
model.prove_friction_feasible=refuse_friction
sys.modules['rampd_core.model']=model
import pytest
raise SystemExit(pytest.main(['-q',str(ROOT/'tests/test_sc_inner.py'),*sys.argv[1:]]))
