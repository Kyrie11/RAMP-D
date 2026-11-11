#!/usr/bin/env python3
"""Package a Phase 4 acceptance report without including native build products."""
from __future__ import annotations
import argparse
from pathlib import Path
import zipfile

TEXT_SUFFIXES = frozenset({".log", ".json", ".xml", ".txt", ".csv", ".md", ".yaml", ".yml", ".sha256"})

def main() -> int:
    root = Path(__file__).resolve().parents[1]
    ap = argparse.ArgumentParser()
    ap.add_argument("--report", type=Path, default=None)
    ap.add_argument("--output", type=Path, default=root / "reports" / "RAMP-D_Phase4_server_report.zip")
    args = ap.parse_args()
    if args.report is None:
        choices = [p for p in (root / "reports").iterdir() if p.is_dir() and (p / "phase4_acceptance_summary.json").is_file()]
        if not choices:
            raise SystemExit("No Phase 4 report found; run scripts/validate_phase4.sh first or pass --report")
        report = max(choices, key=lambda p: (p / "phase4_acceptance_summary.json").stat().st_mtime)
    else:
        report = args.report
    report = report.resolve()
    if not report.is_dir():
        raise SystemExit(f"report directory does not exist: {report}")
    output = args.output.resolve()
    files = []
    for path in sorted(report.rglob("*")):
        if not path.is_file() or path.is_symlink() or path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        if path.resolve() == output or not path.resolve().is_relative_to(report):
            continue
        data = path.read_bytes()
        if b"\0" in data:
            continue
        files.append(path)
    if not files:
        raise SystemExit("No text report artifacts found")
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as z:
        for path in files:
            z.write(path, str(Path(report.name) / path.relative_to(report)))
    print(output)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
