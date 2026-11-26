#!/usr/bin/env python3
"""Legacy CLI/import alias for native_multi_actor_microcase.py. New callers use the semantic name."""
import importlib as _importlib
import runpy as _runpy
import sys as _sys
from pathlib import Path as _Path
if __name__ == "__main__":
    _runpy.run_path(str(_Path(__file__).with_name("native_multi_actor_microcase.py")), run_name="__main__")
else:
    _module = _importlib.import_module("native_multi_actor_microcase")
    _sys.modules[__name__] = _module
