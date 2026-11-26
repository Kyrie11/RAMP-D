"""Legacy import alias for :mod:`rampd_core.declared_task_tail` (A75 compatibility)."""
from importlib import import_module as _import_module
import sys as _sys
_sys.modules[__name__] = _import_module(".declared_task_tail", __package__)
