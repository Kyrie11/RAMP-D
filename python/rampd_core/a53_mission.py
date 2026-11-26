"""Legacy import alias for :mod:`rampd_core.absolute_time_mission` (A75 compatibility)."""
from importlib import import_module as _import_module
import sys as _sys
_sys.modules[__name__] = _import_module(".absolute_time_mission", __package__)
