#!/usr/bin/env python3
"""ROADWork official annotation -> alignment -> GPS group split -> templates -> auxiliary.

Images.zip and sem_seg_labels.zip/gtFine MUST be available at --dataset-root.
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
    annotations=next((p for p in (data/'annotations.zip',data/'archives'/'annotations.zip') if p.is_file()),None)
    if annotations is None:raise SystemExit('MISSING_OFFICIAL_ANNOTATIONS_ZIP_NOT_ROADWORK_FILES_JSON')
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
    r=dict(schema='rampd.a72.roadwork.real_ingest.v1',status='DESCRIPTIVE_VISUAL_PIPELINE_COMPLETE' if len(steps)==4 and all(not x['returncode'] for x in steps) else 'REVIEW',
           steps=steps,visual_annotations_verified=(len(steps)==4 and all(not x['returncode'] for x in steps)),
           pixel_boxes_are_not_metric_geometry=True,official_temporal_rule_authority_not_proved=True,
           formal_supervision_authorized=False)
    (out/'pipeline_review.json').write_text(json.dumps(r,indent=2,ensure_ascii=False)+'\n')
    print(r['status']);return 0 if r['status'].startswith('DESCRIPTIVE') else 4
if __name__=='__main__':raise SystemExit(main())
