"""Legacy import alias for :mod:`rampd_core.actor_response_envelope` (A75 compatibility)."""
from importlib import import_module as _import_module
import sys as _sys
_sys.modules[__name__] = _import_module(".actor_response_envelope", __package__)
