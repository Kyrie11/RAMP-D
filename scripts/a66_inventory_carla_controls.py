#!/usr/bin/env python3
"""Build a fail-closed noncertifying CARLA smoke evidence inventory."""
from __future__ import annotations
import argparse,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'python'))
from rampd_core.a66_evidence_inventory import inventory_single_control_inputs


def main():
    ap=argparse.ArgumentParser()
    for key in ('brake','steer','combined'):
        ap.add_argument('--'+key,type=Path)
    ap.add_argument('--output',required=True,type=Path)
    args=ap.parse_args()
    output=args.output.resolve()
    paths={k:getattr(args,k) for k in ('brake','steer','combined')}
    if output.exists() or any(p is not None and p.resolve()==output for p in paths.values()):
        raise FileExistsError('REFUSE_OVERWRITE_OR_IN_PLACE_REVIEW')
    if any(p is not None and not p.is_file() for p in paths.values()):
        raise FileNotFoundError('CONTROL_EVIDENCE_NOT_FOUND')
    raw={k:json.loads(p.read_text()) if p is not None else None for k,p in paths.items()}
    result=inventory_single_control_inputs(raw)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,indent=2,ensure_ascii=False,allow_nan=False)+'\n')
    print(result['status'], {k:v['status'] for k,v in result['trials'].items()})
    return 0 # missing trials are an expected partial evidence state, not a cert
if __name__=='__main__':raise SystemExit(main())
