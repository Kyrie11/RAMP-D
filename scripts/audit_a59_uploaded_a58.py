#!/usr/bin/env python3
"""Recompute A58 raw-trace obligations without rerunning SUMO."""
import argparse,json,sys,types
from pathlib import Path
root=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root/'python'))
# Forensic JSON/XML parsing never imports native mathematical operators.
package=types.ModuleType('rampd_core');package.__path__=[str(root/'python'/'rampd_core')];sys.modules['rampd_core']=package
from rampd_core.a59_sumo_forensics import audit_a58_archive

p=argparse.ArgumentParser();p.add_argument('--zip',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
a=p.parse_args()
r=audit_a58_archive(a.zip)
a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(r,indent=2,ensure_ascii=False)+'\n')
for row in r['runs']:
 print(f"{row['profile']:24} seed={row['seed']:2} {row['status']:49} {row['reasons']}")
print('forensic status:',r['status'],'full certificate:',False)
raise SystemExit(0 if r['status']=='ALL_DECLARED_REPORTS_MATCH_SCOPED_TRACES' else 4)
