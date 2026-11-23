#!/usr/bin/env python3
"""Independent non-certifying CARLA lateral evidence audit."""
from __future__ import annotations
import argparse,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'python'))
from rampd_core.a66_carla_lateral_witness import audit_steering_lane_witness

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--input',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args()
    if a.input.resolve()==a.output.resolve() or a.output.exists():
        raise FileExistsError('REFUSE_EXISTING_EVIDENCE_OUTPUT')
    report=audit_steering_lane_witness(json.loads(a.input.read_text()))
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(report,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
    print(report['status'])
    return 0 if report['status']=='DESCRIPTIVE_STEER_SAMPLE_AND_INTERPOLATION_WITNESS_NOT_CERTIFIED' else 4
if __name__=='__main__':raise SystemExit(main())
