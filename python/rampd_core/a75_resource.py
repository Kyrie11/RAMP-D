"""Legacy import alias for :mod:`rampd_core.affine_resource_monitor` (A75 compatibility)."""
from importlib import import_module as _import_module
import sys as _sys
_sys.modules[__name__] = _import_module(".affine_resource_monitor", __package__)
