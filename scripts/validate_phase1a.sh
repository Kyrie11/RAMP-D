#!/usr/bin/env bash
# Compatibility entrypoint; the old uncertified Boost backend has been removed.
set -euo pipefail
exec bash "$(dirname "$0")/validate_phase1b.sh" "$@"
