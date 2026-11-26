"""Legacy import alias for :mod:`rampd_core.guard_execution_trace` (A75 compatibility)."""
from importlib import import_module as _import_module
import sys as _sys
_sys.modules[__name__] = _import_module(".guard_execution_trace", __package__)
