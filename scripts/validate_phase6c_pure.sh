#!/usr/bin/env bash
# Local diagnostic when official native MPFR development headers are absent.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-python}"
cd "$ROOT"
export PYTEST_DISABLE_PLUGIN_AUTOLOAD=1
"$PYTHON_BIN" - <<'PY'
import sys,types,pytest
pkg=types.ModuleType('rampd_core')
pkg.__path__=[str(__import__('pathlib').Path('python/rampd_core').resolve())]
sys.modules['rampd_core']=pkg
# All actual Phase 6 modules and protocol classes are imported, not mocked.
from rampd_core import record_adapters
for key in record_adapters.__all__:
    setattr(pkg,key,getattr(record_adapters,key))
raise SystemExit(pytest.main(['-q','tests/test_phase6_data_audit.py',
                              'tests/test_phase6b_record_adapters.py',
                              'tests/test_phase6c.py']))
PY
