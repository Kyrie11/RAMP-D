#!/usr/bin/env python3
"""Package text artifacts from a Phase 6A validation directory."""
from __future__ import annotations
import argparse
from pathlib import Path
import zipfile

SUFFIXES = {".log", ".json", ".xml", ".txt", ".csv", ".md", ".yaml", ".yml", ".sha256"}


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--output", type=Path,
                        default=root / "reports" / "RAMP-D_Phase6A_server_report.zip")
    args = parser.parse_args()
    report = args.report.resolve()
    if not report.is_dir():
        raise SystemExit(f"report directory does not exist: {report}")
    files = [p for p in sorted(report.rglob("*"))
             if p.is_file() and not p.is_symlink() and p.suffix.lower() in SUFFIXES]
    if not files:
        raise SystemExit("No text artifacts in report")
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in files:
            archive.write(path, str(Path(report.name) / path.relative_to(report)))
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

