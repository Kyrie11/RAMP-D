#!/usr/bin/env python3
"""Run new pure audits without loading the MPFR backend; never certifies native."""
import sys,types
from pathlib import Path
root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root/'python'))
pkg=types.ModuleType('rampd_core');pkg.__path__=[str(root/'python'/'rampd_core')];sys.modules['rampd_core']=pkg
import pytest
raise SystemExit(pytest.main(['-q',str(root/'tests'/'test_a71_parallel_pure.py'),*sys.argv[1:]]))
