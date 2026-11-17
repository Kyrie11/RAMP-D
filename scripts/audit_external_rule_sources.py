#!/usr/bin/env python3
"""Inventory downloaded authoritative feed / ROADWork annotation artifacts.
Never turn geographic data or images into a certificate or event clock label.
"""
import argparse, hashlib, json
from pathlib import Path
from collections import Counter
from datetime import datetime


def wzdx_summary(data):
    if data.get('type')!='FeatureCollection' or not isinstance(data.get('features'),list):
        raise ValueError('expected WZDx GeoJSON FeatureCollection')
    counts=Counter();flags=Counter();dur=[];ids=[];errors=[]
    for f in data['features']:
        if not isinstance(f,dict): errors.append('non-object feature');continue
        p=f.get('properties') or {};core=p.get('core_details') or {};kind=core.get('event_type',p.get('event_type','UNKNOWN'))
        counts[str(kind)]+=1;ids.append(f.get('id'))
        for k in ('is_start_date_verified','is_end_date_verified','is_start_position_verified','is_end_position_verified'):
            v=p.get(k);flags[k+':'+str(v)]+=1
        a,b=p.get('start_date'),p.get('end_date')
        if a and b:
            try:
                t1=datetime.fromisoformat(a.replace('Z','+00:00'));t2=datetime.fromisoformat(b.replace('Z','+00:00'))
                if t1.tzinfo is None or t2.tzinfo is None or t2<t1:raise ValueError('invalid interval')
                # descriptive, not legal effective time
                if p.get('is_start_date_verified') is True and p.get('is_end_date_verified') is True:dur.append((t2-t1).total_seconds())
            except (TypeError,ValueError,AttributeError):errors.append(f'{f.get("id")}: invalid date interval')
    ident=[x for x in ids if isinstance(x,str) and x]
    if len(set(ident))!=len(ids):errors.append('missing or duplicate feature ids')
    return dict(features=len(ids),event_types=dict(counts),verification_flag_counts=dict(flags),verified_declared_durations_s=dur,errors=errors,schema_validation_complete=False,physical_onset_label=False,ego_receipt_label=False)


def coco_summary(data):
    if not all(isinstance(data.get(k),list) for k in ('images','annotations','categories')):raise ValueError('expected COCO-style annotation JSON; no schema inference')
    def get_ids(rows):return [x['id'] for x in rows]
    images=get_ids(data['images']);cats=get_ids(data['categories']);ann=get_ids(data['annotations'])
    if any(len(x)!=len(set(x)) for x in (images,cats,ann)):raise ValueError('duplicate COCO ids')
    counts=Counter();si=set(images);sc=set(cats)
    for r in data['annotations']:
        if r['image_id'] not in si or r['category_id'] not in sc:raise ValueError('dangling COCO annotation reference')
        counts[str(r['category_id'])]+=1
    return dict(images=len(images),annotations=len(ann),category_counts=dict(counts),category_names={str(c['id']):c.get('name') for c in data['categories']},image_files_checked=False,physical_geometry_label=False,rule_timing_label=False)


def main():
    p=argparse.ArgumentParser();p.add_argument('--wzdx',type=Path,action='append',default=[]);p.add_argument('--roadwork-coco',type=Path,action='append',default=[]);p.add_argument('--output',type=Path,required=True);a=p.parse_args();o={'status':'ERROR','scope':'EXTERNAL_SOURCE_INVENTORY_ONLY','sources':[],'training_labels_generated':False}
    failed=False
    for path,fn in [(x,wzdx_summary) for x in a.wzdx]+[(x,coco_summary) for x in a.roadwork_coco]:
        row={'file':str(path)}
        try:
            raw=path.read_bytes();row['sha256']=hashlib.sha256(raw).hexdigest();row.update(fn(json.loads(raw)));failed|=bool(row.get('errors'))
        except Exception as exc: row['error']=f'{type(exc).__name__}: {exc}';failed=True
        o['sources'].append(row)
    if o['sources'] and not failed:o['status']='INVENTORY_PASS'
    a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(o,indent=2)+'\n');print(o['status']);return 0 if o['status']=='INVENTORY_PASS' else 4
if __name__=='__main__':raise SystemExit(main())
