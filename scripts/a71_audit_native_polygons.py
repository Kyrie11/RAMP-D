#!/usr/bin/env python3
"""Native MPFR/Picard certificate replay -> conservative polygon exclusion.
The source geometry is a *declared experiment* and is never asserted to be an
actual work-zone map. Other agents, legal admission and task acceptance remain
unproved. Native backend is REQUIRED; do not use the pure-test bypass here.
"""
import argparse,json,sys
from pathlib import Path
from fractions import Fraction as Q
root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root/'python'))
from rampd_core.a71_native_polygon_geometry import audit_native_polygon_resources

def main():
 p=argparse.ArgumentParser();p.add_argument('--native-dir',type=Path,required=True)
 p.add_argument('--resource-file',type=Path,required=True)
 p.add_argument('--length',type=float,required=True);p.add_argument('--width',type=float,required=True)
 p.add_argument('--offset-x',type=float,default=0.);p.add_argument('--offset-y',type=float,default=0.)
 p.add_argument('--output',type=Path,required=True);a=p.parse_args()
 if a.output.exists():raise SystemExit('REFUSE_EXISTING_OUTPUT')
 report=json.loads((a.native_dir/'manifest_report.json').read_text())
 certs={}
 for r in report.get('rows',()):
  w,s,e=r['world'],Q(r['start']),Q(r['end'])
  if not w.replace('_','').isalnum():raise ValueError('unsafe world name')
  name='world_%s_slab_%d_%d_%d_%d.json'%(w,s.numerator,s.denominator,e.numerator,e.denominator)
  certs[(w,s,e)]=json.loads((a.native_dir/name).read_text())
 resources=json.loads(a.resource_file.read_text())
 out=audit_native_polygon_resources(report,certs,resources,length_m=a.length,width_m=a.width,
    offset_x_m=a.offset_x,offset_y_m=a.offset_y)
 a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(out,indent=2,allow_nan=False)+'\n')
 print(out['status']);return 0 if out['status']=='CONDITIONAL_DECLARED_NATIVE_POLYGON_EXCLUSION' else 4
if __name__=='__main__':raise SystemExit(main())
