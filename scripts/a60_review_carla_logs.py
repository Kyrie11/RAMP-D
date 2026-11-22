#!/usr/bin/env python3
import argparse,json,sys,importlib.util
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('a60_carla_evidence', ROOT/'python'/'rampd_core'/'a60_carla_evidence.py')
module=importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
inspect_trials=module.inspect_trials

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--input',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--repeats',type=int,default=3)
    a=p.parse_args()
    if a.input.resolve()==a.output.resolve():raise ValueError('read input and output paths must differ')
    if a.output.exists():raise FileExistsError('refuse to overwrite previous review')
    report=inspect_trials(json.loads(a.input.read_text()),required_repeats=a.repeats)
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(report,indent=2,ensure_ascii=False,allow_nan=False)+'\n')
    print(report['status'],report['trial_count'],'/',report['expected_trials'])
    return 0 if report['status'].startswith('SAMPLED_ACTOR_') else 4
if __name__=='__main__':raise SystemExit(main())
