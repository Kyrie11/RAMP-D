#!/usr/bin/env python3
"""Offline physical-readiness review; never requests CARLA or emits labels."""
from __future__ import annotations
import argparse,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'python'))
from rampd_core.a62_carla_readiness import inspect_readiness_log

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--input',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args()
    if a.output.resolve()==a.input.resolve() or a.output.exists():
        raise RuntimeError('REFUSE_OVERWRITE_OR_INPUT_OUTPUT_ALIAS')
    x=json.loads(a.input.read_text())
    r=inspect_readiness_log(x)
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n')
    print(r['status'])
    return 0 if r['status']=='DESCRIPTIVE_PRETRIAL_EVIDENCE_COMPLETE_NOT_CERTIFIED' else 4
if __name__=='__main__':raise SystemExit(main())
