"""Legacy import alias for :mod:`rampd_core.split_family_firewall` (A75 compatibility)."""
from importlib import import_module as _import_module
import sys as _sys
_sys.modules[__name__] = _import_module(".split_family_firewall", __package__)
