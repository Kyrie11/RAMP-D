"""Legacy import alias for :mod:`rampd_core.sumo_trace_forensics` (A75 compatibility)."""
from importlib import import_module as _import_module
import sys as _sys
_sys.modules[__name__] = _import_module(".sumo_trace_forensics", __package__)
