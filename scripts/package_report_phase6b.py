#!/usr/bin/env python3
"""Package a Phase 6B validation report directory without touching datasets."""
from __future__ import annotations

import argparse
from pathlib import Path
import zipfile


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    report = args.report.resolve()
    if not report.is_dir():
        parser.error(f"report directory does not exist: {report}")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(args.output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(report.rglob("*")):
            if path.is_file():
                archive.write(path, path.relative_to(report).as_posix())
    print(f"packaged={args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
