"""Legacy import alias for :mod:`rampd_core.vehicle_frame_conversion` (A75 compatibility)."""
from importlib import import_module as _import_module
import sys as _sys
_sys.modules[__name__] = _import_module(".vehicle_frame_conversion", __package__)
