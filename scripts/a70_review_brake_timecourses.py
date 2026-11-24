#!/usr/bin/env python3
"""Independent raw 0.15/0.30/0.45 CARLA time-course diagnostics (not calibration)."""
import argparse,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'python'))
from rampd_core.a70_physics_timecourse import audit_brake_timecourses

def main(argv=None):
    ap=argparse.ArgumentParser()
    ap.add_argument('--arm',action='append',required=True,help='RUN_ID=raw.json (3 levels)')
    ap.add_argument('--min-repeats-per-level',type=int,default=1)
    ap.add_argument('--output',required=True)
    a=ap.parse_args(argv);out=Path(a.output)
    if out.exists():raise SystemExit('REFUSE_EXISTING_OUTPUT')
    runs={}
    for term in a.arm:
        if '=' not in term:raise SystemExit('RUN_ID=FILE required')
        key,path=term.split('=',1)
        if not key or key in runs:raise SystemExit('DUPLICATE_OR_EMPTY_RUN_ID')
        runs[key]=Path(path).read_bytes()
    result=audit_brake_timecourses(runs,min_repeats_per_level=a.min_repeats_per_level)
    out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
    print(json.dumps(dict(status=result['status'],reasons=result['reasons'],output=str(out)),indent=2))
    return 0 if result['status']=='DESCRIPTIVE_TIMECOURSES_RECOMPUTED_MODEL_UNRESOLVED' else 4

if __name__=='__main__':raise SystemExit(main())
