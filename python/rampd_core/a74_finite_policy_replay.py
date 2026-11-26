"""Legacy import alias for :mod:`rampd_core.finite_policy_replay` (A75 compatibility)."""
from importlib import import_module as _import_module
import sys as _sys
_sys.modules[__name__] = _import_module(".finite_policy_replay", __package__)
