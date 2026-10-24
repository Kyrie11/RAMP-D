#!/usr/bin/env python3
"""Dependency-light self-test for the design generator and project files."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from rapid_ad.design import build_design, write_design  # noqa: E402


def main() -> int:
    smoke = build_design("smoke", [0])
    core = build_design("core", [0])
    full = build_design("all", [0])
    assert len(smoke) == 6, len(smoke)
    assert len(core) == 16, len(core)
    assert len(full) == 32, len(full)
    assert len({c["case_id"] for c in full}) == len(full)
    assert {c["gap_timing"] for c in full} == {"none", "pre", "overlap", "post"}
    temp = ROOT / "_selftest_output"
    write_design(smoke, temp)
    manifest = json.loads((temp / "manifest.json").read_text(encoding="utf-8"))
    assert len(manifest) == 6
    print("RAPID-AD self-test passed: smoke=6 core=16 all=32")
    print(f"Temporary manifest: {temp / 'manifest.csv'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
