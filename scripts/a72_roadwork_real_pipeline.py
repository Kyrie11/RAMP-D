#!/usr/bin/env python3
"""ROADWork official annotation -> alignment -> GPS group split -> templates -> auxiliary.

Extracted annotations/, images/ and gtFine/ MUST be available at --dataset-root.
Do not pass roadwork_files.json: that file is merely a file inventory.
"""
import argparse,subprocess,sys,json
from pathlib import Path
root=Path(__file__).resolve().parents[1]

def main():
    p=argparse.ArgumentParser();p.add_argument('--dataset-root',type=Path,required=True)
    p.add_argument('--output-dir',type=Path,required=True);p.add_argument('--max-templates',type=int,default=100)
    a=p.parse_args();data=a.dataset_root;out=a.output_dir
    if out.exists():raise SystemExit('REFUSE_EXISTING_OUTPUT_DIRECTORY')
    missing=[str(data/name) for name in ('annotations','images','gtFine') if not (data/name).is_dir()]
    if missing:raise SystemExit('MISSING_EXTRACTED_ROADWORK_DIRECTORIES: '+', '.join(missing))
    annotations=data/'annotations'
    out.mkdir(parents=True)
    commands=[
      ['audit_roadwork.py','--root',str(data),'--output',str(out/'alignment.json'),'--samples-per-split','3'],
      ['audit_a57_roadwork.py','--annotations',str(annotations),'--output',str(out/'gps_split.json')],
      ['export_a58_roadwork_templates.py','--annotations',str(annotations),'--output',str(out/'roadwork_templates.jsonl'),'--max-templates',str(a.max_templates)],
      ['a72_export_auxiliary_v2.py','--roadwork-templates',str(out/'roadwork_templates.jsonl'),
       '--output',str(out/'roadwork_auxiliary.jsonl'),'--quarantine',str(out/'roadwork_quarantine.jsonl')]]
    steps=[]
    for cmd in commands:
        result=subprocess.run([sys.executable,str(root/'scripts'/cmd[0])]+cmd[1:],text=True,capture_output=True)
        steps.append(dict(script=cmd[0],returncode=result.returncode,stdout=result.stdout[-3500:],stderr=result.stderr[-2500:]))
        if result.returncode!=0:break
    accepted=0
    if len(steps)==4 and all(not x['returncode'] for x in steps):
        audit=json.loads((out/'roadwork_auxiliary.jsonl.audit.json').read_text());accepted=audit['counts']['accepted']
    r=dict(accepted_visual_templates=accepted,schema='rampd.a72.roadwork.real_ingest.v1',status='DESCRIPTIVE_VISUAL_PIPELINE_COMPLETE' if accepted>0 else 'REVIEW',
           steps=steps,visual_annotations_verified=(accepted>0),
           pixel_boxes_are_not_metric_geometry=True,official_temporal_rule_authority_not_proved=True,
           formal_supervision_authorized=False)
    (out/'pipeline_review.json').write_text(json.dumps(r,indent=2,ensure_ascii=False)+'\n')
    print(r['status']);return 0 if r['status'].startswith('DESCRIPTIVE') else 4
if __name__=='__main__':raise SystemExit(main())
