"""Legacy import alias for :mod:`rampd_core.sumo_campaign_audit` (A75 compatibility)."""
from importlib import import_module as _import_module
import sys as _sys
_sys.modules[__name__] = _import_module(".sumo_campaign_audit", __package__)
