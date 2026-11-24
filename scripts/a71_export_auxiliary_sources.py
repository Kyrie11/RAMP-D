#!/usr/bin/env python3
"""Convert *normalized* 511NY JSONL and grouped ROADWork templates into safe auxiliary records.
511NY CSV must first be parsed with the existing timezone/quality adapter.
"""
import argparse,json,sys,types
from pathlib import Path
root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root/'python'))
pkg=types.ModuleType('rampd_core');pkg.__path__=[str(root/'python'/'rampd_core')];sys.modules['rampd_core']=pkg
from rampd_core.a71_event_auxiliary import adapt_511ny_report,adapt_roadwork_scene

def main():
 p=argparse.ArgumentParser();p.add_argument('--normalized-511ny',type=Path);p.add_argument('--roadwork-templates',type=Path);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
 if not a.normalized_511ny and not a.roadwork_templates:p.error('at least one actual source required')
 if a.output.exists():raise SystemExit('output already exists; prevent overwrite')
 rows=[];errors=[]
 for path,fn in ((a.normalized_511ny,adapt_511ny_report),(a.roadwork_templates,adapt_roadwork_scene)):
  if not path:continue
  for line,raw in enumerate(path.read_text().splitlines(),1):
   if not raw.strip():continue
   try:rows.append(fn(json.loads(raw)))
   except (ValueError,TypeError,KeyError,UnicodeError) as e:errors.append(dict(source=str(path),line=line,reason=str(e)))
 a.output.parent.mkdir(parents=True,exist_ok=True)
 a.output.write_text(''.join(json.dumps(x,ensure_ascii=False,allow_nan=False)+'\n' for x in rows))
 summary=dict(status='DESCRIPTIVE_AUXILIARY_RECORDS_NO_FORMAL_LABELS' if not errors and rows else 'REVIEW',
              rows=len(rows),rejected=errors,formal_labels_authorized=False)
 a.output.with_suffix(a.output.suffix+'.audit.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
 print(json.dumps(summary,ensure_ascii=False));return 0 if not errors and rows else 4
if __name__=='__main__':raise SystemExit(main())
