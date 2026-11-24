#!/usr/bin/env python3
"""Replay actual A71 SUMO 12x and 3-way Waymax IDM lookahead artifacts."""
import argparse,json,sys,types
from pathlib import Path
root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root/'python'))
pkg=types.ModuleType('rampd_core');pkg.__path__=[str(root/'python'/'rampd_core')];sys.modules['rampd_core']=pkg
from rampd_core.a72_sumo_campaign import audit_campaign
from rampd_core.a72_waymax_sensitivity import audit_waymax_lookahead

def main():
 p=argparse.ArgumentParser();p.add_argument('--sumo-campaign',type=Path)
 p.add_argument('--waymax-arm',action='append',default=[],help='N:path, e.g. 30:report.json');p.add_argument('--output',type=Path,required=True)
 a=p.parse_args();r={}
 if a.sumo_campaign:r['sumo']=audit_campaign(a.sumo_campaign)
 if a.waymax_arm:
  ds={}
  for item in a.waymax_arm:
   n,sep,path=item.partition(':')
   if not sep or n in ds:raise ValueError('required distinct lookahead:value filename')
   ds[n]=json.loads(Path(path).read_text())
  r['waymax']=audit_waymax_lookahead(ds)
 if not r:p.error('at least one source required')
 out=dict(schema='rampd.a72.parallel_independent.v1',sources=r,formal_safe_training_labels_allowed=False)
 a.output.parent.mkdir(parents=True,exist_ok=True)
 if a.output.exists():raise SystemExit('REFUSE_OVERWRITE')
 a.output.write_text(json.dumps(out,indent=2,ensure_ascii=False)+'\n')
 print({k:v['status'] for k,v in r.items()});return 0 if all(not x['reasons'] for x in r.values()) else 4
if __name__=='__main__':raise SystemExit(main())
