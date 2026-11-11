#!/usr/bin/env python3
"""Package a Phase 3 report, including diagnostics from unsuccessful runs."""
import argparse
from pathlib import Path
import zipfile


TEXT_SUFFIXES = frozenset({".log", ".json", ".xml", ".txt", ".csv", ".md",
                           ".yaml", ".yml", ".sha256"})


def main():
    root = Path(__file__).resolve().parents[1]
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--report", type=Path)
    ap.add_argument("--output", type=Path,
                    default=root / "reports" / "RAMP-D_Phase3_server_report.zip")
    args = ap.parse_args()
    report = args.report
    if report is None:
        report_root = root / "reports"
        choices = ([] if not report_root.is_dir() else [
            path for path in report_root.iterdir()
            if path.is_dir() and (path / "phase3_validation.log").is_file()
        ])
        if not choices:
            raise SystemExit("No Phase 3 report found. Run scripts/validate_phase3.sh first, or pass --report.")
        report = max(choices, key=lambda path: (path / "phase3_validation.log").stat().st_mtime)
    report = report.resolve()
    if not report.is_dir():
        raise SystemExit(f"Report directory does not exist: {report}")
    output = args.output.resolve()
    selected = []
    for path in sorted(report.rglob("*")):
        if (not path.is_file() or path.is_symlink() or
                path.suffix.lower() not in TEXT_SUFFIXES or path.resolve() == output):
            continue
        if not path.resolve().is_relative_to(report):
            continue
        # Suffix filtering excludes build products and nested ZIPs. Refuse
        # NUL-containing files too; reports are text, not native executables.
        if b"\0" in path.read_bytes():
            print(f"Skipping binary report entry: {path.relative_to(report)}")
            continue
        selected.append(path)
    if not selected:
        raise SystemExit(f"No text report artifacts found in: {report}")
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in selected:
            archive.write(path, str(Path(report.name) / path.relative_to(report)))
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
