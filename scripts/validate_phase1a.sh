#!/usr/bin/env bash
# Backward-compatible entry point: run the complete current regression suite.
set -euo pipefail
exec bash "$(dirname "$0")/validate_phase1c.sh" "$@"
