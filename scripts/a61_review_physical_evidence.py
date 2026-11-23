#!/usr/bin/env python3
"""Offline, independent descriptive diagnostic for A59/1a CARLA JSON."""
from pathlib import Path
import argparse,json,importlib.util
spec=importlib.util.spec_from_file_location("a61_carla_calibration", Path(__file__).resolve().parents[1]/"python"/"rampd_core"/"a61_carla_calibration.py")
module=importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
describe_control_trials=module.describe_control_trials
reconstruct_actor_geometry=module.reconstruct_actor_geometry

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--input',type=Path,required=True)
    ap.add_argument('--output',type=Path,required=True)
    ap.add_argument('--repeats',type=int,default=3)
    a=ap.parse_args()
    if a.output.exists() or a.output.resolve()==a.input.resolve():raise FileExistsError('refuse to overwrite evidence')
    d=json.loads(a.input.read_text())
    if d.get('schema')=='rampd.carla.a59_1.raw_trials.v1':
        out=describe_control_trials(d,expected_repeats=a.repeats)
    else:
        out=reconstruct_actor_geometry(d)
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(out,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
    print(out['status']);return 0 if out['status'].startswith('DESCRIPTIVE_') else 4

if __name__=='__main__':raise SystemExit(main())
