"""Legacy import alias for :mod:`rampd_core.artifact_byte_binding` (A75 compatibility)."""
from importlib import import_module as _import_module
import sys as _sys
_sys.modules[__name__] = _import_module(".artifact_byte_binding", __package__)
