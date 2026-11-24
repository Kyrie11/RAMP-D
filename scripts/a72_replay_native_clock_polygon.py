#!/usr/bin/env python3
"""Native proof replay bound to independently reconstructed two-world clock.
This CLI is ONLY the declared A70 microcase, not a production SC verifier.
"""
import argparse,json,sys
from pathlib import Path
from fractions import Fraction as Q
root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root/'python'))
from rampd_core.a60_clock_resource import ClockEvent
from rampd_core.a61_hybrid_partition import ClockWorld
from rampd_core.a72_native_world_resource import audit_clock_bound_polygon_exclusion
from rampd_core.a73_native_context import audit_context
from rampd_core.model import BicycleParameters
from dataclasses import asdict

def main():
 p=argparse.ArgumentParser();p.add_argument('--native-dir',type=Path,required=True)
 p.add_argument('--resource-file',type=Path,required=True)
 p.add_argument('--length',type=float,default=4.8);p.add_argument('--width',type=float,default=2.2)
 p.add_argument('--output',type=Path,required=True);a=p.parse_args()
 if a.output.exists():raise SystemExit('REFUSE_EXISTING_OUTPUT')
 report=json.loads((a.native_dir/'manifest_report.json').read_text())
 certs={}
 for r in report.get('rows',[]):
  w,s,e=r['world'],Q(r['start']),Q(r['end'])
  if w not in ('A','B'):raise ValueError('microcase world declaration mismatch')
  name=f'world_{w}_slab_{s.numerator}_{s.denominator}_{e.numerator}_{e.denominator}.json'
  certs[(w,s,e)]=json.loads((a.native_dir/name).read_text())
 worlds=tuple(ClockWorld(w,(ClockEvent('switch-'+w,'RULE_EFFECTIVE',Q(1,20),'DECLARED_TOY_MODEL'),),
                     declared_complete=True,public_history_id='same') for w in ('A','B'))
 resources=json.loads(a.resource_file.read_text())
 declarations={(w,lo,hi):dict(params=asdict(BicycleParameters(3,.9)),control=[[0,0],[0,0]],disturbance=[[0,0]]*6,initial=[[0,0],[0,0],[0,0],[4,4],[0,0],[0,0]] if lo==0 else None) for w in ('A','B') for lo,hi in ((Q(0),Q(1,20)),(Q(1,20),Q(1,10)))}
 r=audit_clock_bound_polygon_exclusion(report,certs,worlds,resources,start=Q(0),end=Q(1,10),
                                       length_m=a.length,width_m=a.width,physical_declarations=declarations)
 r['independent_physical_context_errors']=audit_context(certs,declarations)
 a.output.parent.mkdir(parents=True,exist_ok=True)
 a.output.write_text(json.dumps(r,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
 print(r['status']);return 0 if r['status']=='CONDITIONAL_DECLARED_POLYGON_EXCLUSION' else 4
if __name__=='__main__':raise SystemExit(main())
