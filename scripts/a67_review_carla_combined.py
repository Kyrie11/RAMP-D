#!/usr/bin/env python3
"""Read-only independent combined-control dynamics report; no safety label."""
import argparse,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'python'))
from rampd_core.a67_carla_combined_diagnostics import audit_combined_dynamics

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--input',type=Path,required=True)
    ap.add_argument('--output',type=Path,required=True)
    args=ap.parse_args()
    if args.output.exists() or args.input.resolve()==args.output.resolve():
        raise FileExistsError('REFUSE_REPLACE_EXISTING_EVIDENCE')
    d=json.loads(args.input.read_text())
    report=audit_combined_dynamics(d)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
    print(report['status'],report['reasons'])
    return 0 if report['diagnostic_repetition_allowed'] else 4
if __name__=='__main__':raise SystemExit(main())
