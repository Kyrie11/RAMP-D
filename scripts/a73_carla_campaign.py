#!/usr/bin/env python3
import argparse,json,sys,types
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'python'));pkg=types.ModuleType('rampd_core');pkg.__path__=[str(ROOT/'python'/'rampd_core')];sys.modules['rampd_core']=pkg
from rampd_core.a73_physics import campaign

def main():
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--dt',type=float,choices=(.05,.025),default=.05);a=p.parse_args()
    if a.output.exists():raise SystemExit('REFUSE_OVERWRITE')
    arms={(b,m):[json.loads(f.read_text()) for f in sorted((a.root/f'{m}_b{int(round(b*100)):03d}').glob('run*.json'))] for b in (.15,.30,.45) for m in ('pure','combined')}
    result=campaign(arms,dt=a.dt);a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(result,indent=2,allow_nan=False)+'\n');print(result['status'],result['errors']);return 0 if result['status'].startswith('DESCRIPTIVE') else 4
if __name__=='__main__':raise SystemExit(main())
