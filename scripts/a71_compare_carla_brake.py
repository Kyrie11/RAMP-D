#!/usr/bin/env python3
"""Offline independent comparison of uploaded pure brake and combined CARLA."""
from pathlib import Path
import argparse,sys,json,hashlib
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'python'))
# Do not import the MPFR-heavy package initializer for a descriptive data audit.
import types
root=Path(__file__).resolve().parents[1]
pkg=types.ModuleType('rampd_core');pkg.__path__=[str(root/'python'/'rampd_core')];sys.modules['rampd_core']=pkg
from rampd_core.a71_carla_factor_pairs import audit_brake_steer_pair

def main():
 p=argparse.ArgumentParser();p.add_argument('--pure',type=Path,required=True);p.add_argument('--combined',type=Path,required=True);p.add_argument('--brake',type=float,default=.15);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
 raw_pure=a.pure.read_bytes();raw_combined=a.combined.read_bytes()
 r=audit_brake_steer_pair(json.loads(raw_pure),json.loads(raw_combined),brake=a.brake)
 r['actual_input_raw_byte_sha256']={'pure':hashlib.sha256(raw_pure).hexdigest(),
   'combined':hashlib.sha256(raw_combined).hexdigest()}
 a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(r,ensure_ascii=False,indent=2,allow_nan=False)+'\n');print(r['status']);return 0 if not r['reasons'] else 4
if __name__=='__main__':raise SystemExit(main())
