#!/usr/bin/env python3
"""Isolated, explicit non-native adapter test. Native proof still mandatory!"""
import types,sys
from pathlib import Path
root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root/'python'))
package=types.ModuleType('rampd_core');package.__path__=[str(root/'python'/'rampd_core')];sys.modules['rampd_core']=package
import pytest
raise SystemExit(pytest.main(['-q',str(root/'tests'/'test_phase6c_a58_pure.py'),*sys.argv[1:]]))
