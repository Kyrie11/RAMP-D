"""Legacy import alias for :mod:`rampd_core.cosim_clock_contract` (A75 compatibility)."""
from importlib import import_module as _import_module
import sys as _sys
_sys.modules[__name__] = _import_module(".cosim_clock_contract", __package__)
