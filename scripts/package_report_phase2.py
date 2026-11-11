#!/usr/bin/env python3
"""Package a Phase 2 server acceptance report, including failed-run logs."""
import argparse
from pathlib import Path
import zipfile

if __name__=='__main__':
    root=Path(__file__).resolve().parents[1]
    ap=argparse.ArgumentParser()
    ap.add_argument('--report',type=Path)
    ap.add_argument('--output',type=Path,default=root/'reports'/'RAMP-D_Phase2_server_report.zip')
    args=ap.parse_args()
    report=args.report
    if report is None:
        choices=[p for p in (root/'reports').glob('phase2_*') if p.is_dir() and (p/'validation.log').is_file()]
        if not choices: raise SystemExit('No Phase 2 report found. Run scripts/validate_phase2.sh first.')
        report=max(choices,key=lambda p:p.stat().st_mtime)
    report=report.resolve()
    if not report.is_dir(): raise SystemExit(f'Report directory does not exist: {report}')
    args.output.parent.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(args.output,'w',zipfile.ZIP_DEFLATED) as z:
        for p in sorted(report.rglob('*')):
            if p.is_file() and p.suffix in ('.log','.json','.xml','.txt','.csv'):
                z.write(p,str(Path(report.name)/p.relative_to(report)))
    print(args.output.resolve())
