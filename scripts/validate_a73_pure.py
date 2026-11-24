#!/usr/bin/env python3
import pathlib,sys,types,os
root=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(root/'python'));sys.path.insert(0,str(root/'scripts'))
# Native-independent modules only. In native gate, normal imports are used.
if not os.environ.get('RAMPD_INTERVAL_LIB'):
    pkg=types.ModuleType('rampd_core');pkg.__path__=[str(root/'python'/'rampd_core')];sys.modules['rampd_core']=pkg
import pytest
raise SystemExit(pytest.main(['-q',str(root/'tests'/'test_a73.py'),*sys.argv[1:]]))
