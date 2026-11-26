#!/usr/bin/env python3
"""Stable command-line entry point for a72_roadwork_real_pipeline.py; implementation kept for historical direct-file callers."""
import runpy
from pathlib import Path
if __name__ == "__main__":
    runpy.run_path(str(Path(__file__).with_name("a72_roadwork_real_pipeline.py")), run_name="__main__")
