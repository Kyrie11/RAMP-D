"""Legacy import alias for :mod:`rampd_core.scoped_factual_labels` (A75 compatibility)."""
from importlib import import_module as _import_module
import sys as _sys
_sys.modules[__name__] = _import_module(".scoped_factual_labels", __package__)
