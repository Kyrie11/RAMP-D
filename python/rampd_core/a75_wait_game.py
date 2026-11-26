"""Legacy import alias for :mod:`rampd_core.finite_wait_reference` (A75 compatibility)."""
from importlib import import_module as _import_module
import sys as _sys
_sys.modules[__name__] = _import_module(".finite_wait_reference", __package__)
