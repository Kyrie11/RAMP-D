#!/usr/bin/env python3
"""Stable command-line entry point for probe_sumo_alternating.py; implementation kept for historical direct-file callers."""
import runpy
from pathlib import Path
if __name__ == "__main__":
    runpy.run_path(str(Path(__file__).with_name("probe_sumo_alternating.py")), run_name="__main__")
