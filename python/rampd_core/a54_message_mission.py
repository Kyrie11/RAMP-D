"""Legacy import alias for :mod:`rampd_core.message_mission_compiler` (A75 compatibility)."""
from importlib import import_module as _import_module
import sys as _sys
_sys.modules[__name__] = _import_module(".message_mission_compiler", __package__)
