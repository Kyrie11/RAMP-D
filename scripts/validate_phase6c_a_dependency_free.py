#!/usr/bin/env python3
"""Run dataset/prediction/Phase 6C contract tests without the native MPFR ABI.

This harness deliberately loads only dependency-free Phase 6 modules.  It does
not replace or claim to test the native interval/reachability/backup backend;
those remain covered by the regular server-side pytest + CTest suite.
"""
from __future__ import annotations

import importlib
from pathlib import Path
import sys
import types

ROOT = Path(__file__).resolve().parents[1]
PACKAGE_DIR = ROOT / "python" / "rampd_core"
sys.path.insert(0, str(ROOT / "python"))

# The normal package __init__ imports the MPFR-backed interval extension and
# correctly fails closed if its ABI is not built.  For these isolated adapter
# tests only, install a package shell and import the pure-Python submodules.
pkg = types.ModuleType("rampd_core")
pkg.__path__ = [str(PACKAGE_DIR)]
sys.modules["rampd_core"] = pkg

for name in ("protocol", "scene_schema", "record_adapters", "forecast", "phase6c",
             "dataset_audit"):
    module = importlib.import_module(f"rampd_core.{name}")
    for symbol in getattr(module, "__all__", ()):
        setattr(pkg, symbol, getattr(module, symbol))

import pytest

pytest_args = [
    "-q",
    str(ROOT / "tests" / "test_phase6b_record_adapters.py"),
    str(ROOT / "tests" / "test_phase6_data_audit.py"),
    str(ROOT / "tests" / "test_forecast_adapter.py"),
    str(ROOT / "tests" / "test_phase6c.py"),
    str(ROOT / "tests" / "test_phase6c_protocol_regression.py"),
]
raise SystemExit(pytest.main( [*pytest_args, *sys.argv[1:]] ))
