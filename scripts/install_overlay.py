#!/usr/bin/env python3
"""Install the small RAPID-AD scenario entrypoint into a local MARSHAL clone."""
from __future__ import annotations

import argparse
import shutil
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--marshal-root", required=True, help="Path to the cloned MARSHAL repository")
    parser.add_argument("--project-root", default=None, help="RAPID-AD root; inferred from this script if omitted")
    args = parser.parse_args()
    project_root = Path(args.project_root).resolve() if args.project_root else Path(__file__).resolve().parents[1]
    marshal_root = Path(args.marshal_root).resolve()
    if not (marshal_root / "marshal_bench" / "scenarios" / "_common.py").is_file():
        raise SystemExit(f"Not a MARSHAL repository: {marshal_root}")
    src = project_root / "marshal_overlay" / "rapid_ad_factorial_demo.py"
    dst = marshal_root / "marshal_bench" / "scenarios" / "rapid_ad_factorial_demo.py"
    if not src.is_file():
        raise SystemExit(f"Overlay entrypoint missing: {src}")
    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.exists():
        backup = dst.with_suffix(dst.suffix + ".bak")
        shutil.copy2(dst, backup)
        print(f"Backed up existing file to {backup}")
    shutil.copy2(src, dst)
    print(f"Installed: {dst}")
    print("No MARSHAL runner registry or original scenario files were modified.")
    print(f"Set PYTHONPATH={project_root}:{marshal_root}:$PYTHONPATH before running RAPID-AD.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
