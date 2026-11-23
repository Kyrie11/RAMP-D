#!/usr/bin/env python3
"""Independent on-disk review of a single controlled CARLA experiment."""
import argparse,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'python'))
from rampd_core.a64_carla_smoke_evidence import audit_single_control_smoke

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--input',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args()
    if a.input.resolve()==a.output.resolve() or a.output.exists():
        raise FileExistsError('REFUSE_REUSE_EVIDENCE_OUTPUT')
    report=audit_single_control_smoke(json.loads(a.input.read_text()))
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(report,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
    print(report['status'])
    return 0 if report['status']=='DESCRIPTIVE_SINGLE_CONTROL_SMOKE_CAPTURED_NOT_CALIBRATED' else 4

if __name__=='__main__':raise SystemExit(main())
