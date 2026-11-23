#!/usr/bin/env python3
"""Read-only independent A65 brake trace conformance check."""
import argparse,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'python'))
from rampd_core.a65_carla_conformance import audit_brake_conformance

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--input',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args()
    if a.output.resolve()==a.input.resolve() or a.output.exists():
        raise FileExistsError('REFUSE_OVERWRITE_EVIDENCE')
    data=json.loads(a.input.read_text())
    report=audit_brake_conformance(data)
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(report,indent=2,ensure_ascii=False,allow_nan=False)+'\n')
    print(report['status'],report['reasons'])
    return 0 if not report['reasons'] else 4
if __name__=='__main__':raise SystemExit(main())
