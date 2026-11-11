#!/usr/bin/env python3
"""Package a Phase 3 acceptance report."""
from __future__ import annotations

import argparse
from pathlib import Path
import zipfile


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    ap = argparse.ArgumentParser()
    ap.add_argument("--report", type=Path)
    ap.add_argument("--output", type=Path,
                    default=root / "reports" / "RAMP-D_Phase3_server_report.zip")
    args = ap.parse_args()
    report = args.report
    if report is None:
        choices = [p for p in (root / "reports").glob("phase3_*")
                   if p.is_dir() and (p / "acceptance_summary.json").is_file()]
        if not choices:
            raise SystemExit("No Phase 3 report found. Run scripts/validate_phase3.sh first.")
        report = max(choices, key=lambda p: p.stat().st_mtime)
    report = report.resolve()
    if not report.is_dir():
        raise SystemExit(f"Report directory does not exist: {report}")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(args.output, "w", zipfile.ZIP_DEFLATED) as z:
        for path in sorted(report.rglob("*")):
            if path.is_file() and path.suffix in {".json", ".log", ".xml", ".csv", ".txt"}:
                z.write(path, str(Path(report.name) / path.relative_to(report)))
    print(args.output.resolve())


if __name__ == "__main__":
    main()
