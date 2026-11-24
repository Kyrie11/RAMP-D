#!/usr/bin/env python3
"""Inspect user-supplied Native microcase ZIP *without* pretending to replay MPFR.

Checks only canonical byte-hash and exact-rational geometry vs the *reported*
6D interval box. For actual mathematical replay run a71_audit_native_polygons.py
on a server with a freshly built MPFR backend.
"""
from pathlib import Path
import argparse,json,hashlib,zipfile,types,sys
from fractions import Fraction as Q
root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root/'python'))
pkg=types.ModuleType('rampd_core');pkg.__path__=[str(root/'python'/'rampd_core')];sys.modules['rampd_core']=pkg
from rampd_core.a71_native_polygon_geometry import guaranteed_polygon_separation

def main():
 p=argparse.ArgumentParser();p.add_argument('--native-zip',type=Path,required=True)
 p.add_argument('--resources',type=Path,required=True);p.add_argument('--length',type=float,required=True)
 p.add_argument('--width',type=float,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
 if a.output.exists():raise SystemExit('REFUSE_EXISTING_OUTPUT')
 resources=json.loads(a.resources.read_text());reasons=[];rows=[]
 with zipfile.ZipFile(a.native_zip) as z:
  names=z.namelist();manifests=[x for x in names if x.endswith('/manifest_report.json') or x=='manifest_report.json']
  if len(manifests)!=1:raise ValueError('missing/ambiguous report')
  prefix=manifests[0].removesuffix('manifest_report.json')
  report=json.loads(z.read(manifests[0]));expected=report.get('expected_world_slabs')
  if report.get('status')!='CONDITIONAL_DECLARED_EGO_NATIVE_PICARD_SEGMENTED_REPLAY':
   reasons.append('NATIVE_SOURCE_REPORT_NOT_PASSED')
  if expected!=len(report.get('rows',[])) or expected!=report.get('replayed_world_slabs'):
   reasons.append('INCOMPLETE_NATIVE_DECLARED_SUPPORT')
  for r in report.get('rows',[]):
   w,s,e=r['world'],Q(r['start']),Q(r['end'])
   if not w.replace('_','').isalnum():raise ValueError('invalid world name')
   name=prefix+'world_%s_slab_%d_%d_%d_%d.json'%(w,s.numerator,s.denominator,e.numerator,e.denominator)
   try:cert=json.loads(z.read(name))
   except (KeyError,ValueError):reasons.append('MISSING_OR_BAD_NATIVE_ARTIFACT:'+name);continue
   raw=json.dumps(cert,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
   if hashlib.sha256(raw).hexdigest()!=r.get('certificate_sha256'):
    reasons.append('NATIVE_BYTES_MISMATCH:'+name);continue
   for i,seg in enumerate(cert.get('segments',[])):
    for resource,poly in resources.items():
     o=guaranteed_polygon_separation(seg['tube'],poly,length_m=a.length,width_m=a.width)
     rows.append(dict(world=w,slab=[str(s),str(e)],segment_index=i,
                      resource=resource,geometry=o['status']))
  if len(rows)==0:reasons.append('NO_POLYGON_CHECKS')
 may=any(r['geometry']!='DECLARED_TUBE_POLYGON_STRICTLY_SEPARATED' for r in rows)
 r=dict(schema='rampd.a71.offline_native_polygon_archive.v1',
   status='DESCRIPTIVE_DECLARED_OUTER_GEOMETRY_ONLY' if not reasons else 'REVIEW',
   reasons=sorted(set(reasons)),declared_world_slabs=expected,checked_segment_resources=len(rows),
   polygon_possible_contact=may,rows=rows,native_integrator_independently_replayed_here=False,
   certificate_true_physical_model_validated=False,hidden_world_support_physically_complete=False,
   real_map_registration_verified=False,full_sc_certified=False,formal_training_labels_allowed=False)
 a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(r,indent=2,allow_nan=False)+'\n');print(r['status']);return 0 if not reasons else 4
if __name__=='__main__':raise SystemExit(main())
