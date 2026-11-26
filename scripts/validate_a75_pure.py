#!/usr/bin/env python3
import pathlib,sys,types,os
root=pathlib.Path(__file__).resolve().parents[1];sys.path[:0]=[str(root/'python'),str(root/'scripts'),str(root/'tests')]
if not os.environ.get('RAMPD_INTERVAL_LIB'):
    pkg=types.ModuleType('rampd_core');pkg.__path__=[str(root/'python'/'rampd_core')];sys.modules['rampd_core']=pkg
import pytest
raise SystemExit(pytest.main(['-q',str(root/'tests'/'test_a73.py'),str(root/'tests'/'test_a74.py'),str(root/'tests'/'test_a75.py'),*sys.argv[1:]]))
