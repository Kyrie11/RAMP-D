#!/usr/bin/env python3
"""Build conservative ROADWork visual templates from A57 group-disjoint JSONL.
No GPS geometry in metres, signal semantics, event time or safety teacher labels.
"""
from pathlib import Path
import argparse,json,sys,tempfile,types
root=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root/'python'))
# Pure source-annotation utility: do not import the native proof backend.
pkg=types.ModuleType('rampd_core');pkg.__path__=[str(root/'python'/'rampd_core')];sys.modules['rampd_core']=pkg
from rampd_core.a58_roadwork_templates import template_from_manifest_row
from audit_a57_roadwork import audit

def main():
    p=argparse.ArgumentParser();p.add_argument('--annotations',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--max-templates',type=int,default=100)
    p.add_argument('--split',choices=('train','val'),default='train');a=p.parse_args()
    if not 1<=a.max_templates<=50000:raise ValueError('bounded extraction required')
    with tempfile.TemporaryDirectory() as d:
        work=Path(d)/'source';info=audit(a.annotations,work)
        seen=set();output=[]
        with (work/(a.split+'.jsonl')).open() as f:
            for line in f:
                row=json.loads(line)
                if row['group'] in seen:continue
                # Quarantine malformed boxes without silently deleting an object.
                if any(not o['bbox_usable'] for o in row['objects']):continue
                output.append(template_from_manifest_row(row));seen.add(row['group'])
                if len(output)>=a.max_templates:break
    a.output.parent.mkdir(parents=True,exist_ok=True)
    with a.output.open('w') as f:
        for t in output:f.write(json.dumps(t,ensure_ascii=False,sort_keys=True)+'\n')
    print(json.dumps({'status':'VISUAL_TEMPLATES_ONLY','templates':len(output),'split':a.split,
                      'complete_ground_truth':False,'formal_labels':False}))
if __name__=='__main__':main()
