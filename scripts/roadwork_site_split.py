#!/usr/bin/env python3
"""Create independent known-GPS bounded split. Entire ambiguous/near family
removed from train, no claim about scene isolation beyond provided metadata."""
import argparse,json,tempfile,hashlib
from pathlib import Path
from audit_a57_roadwork import audit,site_audit,gps_point

def strict_split(train,val):
    if not val or any(gps_point(r.get('gps')) is None for r in val):raise ValueError('validation GPS missing')
    if {r['group'] for r in train}&{r['group'] for r in val}:raise ValueError('group overlap')
    site=site_audit(train,val);near=set(site['train_near_image_ids']);bad={r['group'] for r in train if r['image_id'] in near or gps_point(r.get('gps')) is None}
    kept=[r for r in train if r['group'] not in bad];excluded=[r for r in train if r['group'] in bad]
    if not kept:raise ValueError('no train samples after strict site gate')
    return kept,val,excluded,site

def main():
    p=argparse.ArgumentParser();p.add_argument('--annotations',type=Path,required=True);p.add_argument('--output-dir',type=Path,required=True);a=p.parse_args()
    if a.output_dir.exists():raise SystemExit('REFUSE_OVERWRITE')
    with tempfile.TemporaryDirectory() as tmp:
        path=Path(tmp)/'m';src=audit(a.annotations,path);load=lambda s:[json.loads(l) for l in (path/(s+'.jsonl')).read_text().splitlines()];tr,va,qu,site=strict_split(load('train'),load('val'))
    a.output_dir.mkdir(parents=True)
    for name,rows in [('train',tr),('validation',va),('quarantine_train',qu)]:
        (a.output_dir/(name+'.jsonl')).write_text(''.join(json.dumps(r,ensure_ascii=False,allow_nan=False)+'\n' for r in rows))
    r=dict(status='DECLARED_GPS_AND_VIDEO_FILTERED_AUXILIARY_SPLIT',counts={'train':len(tr),'validation':len(va),'quarantine_train':len(qu)},before=site,after=site_audit(tr,va),source_sha256=src['input_sha256'],official_benchmark_unchanged=True,actual_site_isolation_proved=False,formal_labels_authorized=False)
    (a.output_dir/'audit.json').write_text(json.dumps(r,indent=2)+'\n');print(r['status'])
if __name__=='__main__':main()
