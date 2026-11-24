#!/usr/bin/env python3
"""Offline independent TraCI signal state/clock audit, not physical ACK."""
import argparse,json,sys,types
from pathlib import Path
root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root/'python'))
pkg=types.ModuleType('rampd_core');pkg.__path__=[str(root/'python'/'rampd_core')];sys.modules['rampd_core']=pkg
from rampd_core.a71_sumo_tls_evidence import read_jsonl,audit_sumo_signal_trace

def main():
 p=argparse.ArgumentParser();p.add_argument('--summary',type=Path,required=True);p.add_argument('--trace',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
 r=audit_sumo_signal_trace(json.loads(a.summary.read_text()),read_jsonl(a.trace))
 a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(r,indent=2,allow_nan=False)+'\n');print(r['status']);return 0 if not r['reasons'] else 4
if __name__=='__main__':raise SystemExit(main())
