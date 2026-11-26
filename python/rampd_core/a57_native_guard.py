"""Legacy import alias for :mod:`rampd_core.native_tick_guard` (A75 compatibility)."""
from importlib import import_module as _import_module
import sys as _sys
_sys.modules[__name__] = _import_module(".native_tick_guard", __package__)
