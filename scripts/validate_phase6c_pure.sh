#!/usr/bin/env bash
# Phase 6C-A3 + CV: all 80 dependency-free tests, *not* a native or dataset gate.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
export PYTEST_DISABLE_PLUGIN_AUTOLOAD=1
"${PYTHON_BIN:-python}" scripts/verify_release.py
"${PYTHON_BIN:-python}" scripts/validate_phase6c_a_dependency_free.py "$@"
