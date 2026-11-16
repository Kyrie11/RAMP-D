#!/usr/bin/env bash
# Compatibility wrapper for the capitalization used in the project notes.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec "$SCRIPT_DIR/validate_phase6b.sh" "$@"
