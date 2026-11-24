#!/usr/bin/env python3
"""Annotation-only source audit and optional group-disjoint visual manifest.
Official split unchanged; strict auxiliary split is separate (not benchmark).
Unknown groups quarantined, no inferred legal labels or metric geometry.
"""
import argparse,collections,hashlib,json,re
from pathlib import Path
from math import isfinite,sin,cos,radians,floor
from itertools import product
from audit_roadwork import reader, index
C=collections.Counter

def group(im):
    name=Path(im['file_name']).name;v=im.get('video_info')
    if v:
        vid=v.get('vid_id');seq=v.get('seq_id');frame=v.get('frame_id')
        if all(isinstance(x,str) and x for x in (vid,seq,frame)) and name.endswith(f'_{vid}_{seq}_{frame}'):
            return 'video:'+vid.lower(), 'video:'+vid.lower()+':'+seq
        raise ValueError('video metadata/filename mismatch '+name)
    m=re.fullmatch(r'pgh([^_]+)_\d+\.jpg',name,re.I)
    if m:return 'pgh:'+m[1],None
    return None,None

def indexed(rows):
    d={r['id']:r for r in rows}
    if len(d)!=len(rows):raise ValueError('duplicate ids')
    return d

def gps_point(g):
    if not isinstance(g,(list,tuple)) or len(g)!=2 or not all(isinstance(v,(float,int)) and isfinite(v) for v in g) or not -90<=g[0]<=90 or not -180<=g[1]<=180 or (g[0],g[1])==(0,0):return None
    lat,lon=map(radians,g);return (cos(lat)*cos(lon),cos(lat)*sin(lon),sin(lat))

def site_audit(train,val,radius=100.):
    # Unit sphere chord: bounded-distance spatial hash, all 27 adjacent cells.
    h=2*sin(radius/(2*6371008.8));grid=collections.defaultdict(list)
    bucket=lambda p:tuple(floor(x/h) for x in p)
    valid=0
    for r in val:
        p=gps_point(r.get('gps'))
        if p is not None:grid[bucket(p)].append(p);valid+=1
    near=[];unknown=[]
    for r in train:
        p=gps_point(r.get('gps'))
        if p is None:unknown.append(r['image_id']);continue
        b=bucket(p)
        if any(sum((x-y)**2 for x,y in zip(p,q))<=h*h for d in product((-1,0,1),repeat=3) for q in grid.get(tuple(x+y for x,y in zip(b,d)),())):near.append(r['image_id'])
    return dict(radius_m=radius,train_near_known_val=len(near),train_unknown_gps=len(unknown),val_known_gps=valid,val_unknown_gps=len(val)-valid,train_near_image_ids=near,all_sites_disjoint_proved=False)

def audit(zpath,manifest=None):
    data={};summary={};group_sets={};digests={}
    with reader(Path(zpath)) as z:
        members=index(z)
        for split in ('train','val'):
            files=[]
            for suffix in ('','_with_signs'):
                target=f'instances_{split}_gps_split{suffix}.json';matches=members.get(target, [])
                if len(matches)!=1:raise ValueError('missing/ambiguous '+target)
                raw=z.read(matches[0]);digests[target]=hashlib.sha256(raw).hexdigest();files.append(json.loads(raw))
            base,enh=files;ims=indexed(base['images']);sign_ims=indexed(enh['images']);anns=indexed(base['annotations']);sa=indexed(enh['annotations']);cats={k:v['name'] for k,v in indexed(base['categories']).items()};scats={k:v['name'] for k,v in indexed(enh['categories']).items()}
            if ims!=sign_ims or anns.keys()!=sa.keys():raise ValueError('sign variant inventory differs')
            objs=collections.defaultdict(list);refined=C();tags=C();field_counts=C();missing_group=0;unusable=0;group_map={};names=set()
            for k,a in anns.items():
                b=sa[k];c=cats[a['category_id']];s=scats[b['category_id']]
                if any(a.get(f)!=b.get(f) for f in ('image_id','bbox','segmentation','attributes','area','iscrowd')) or (s!=c and not(c=='Temporary Traffic Control Sign' and s.startswith(c+': '))):raise ValueError('sign variant identity/geometry differs')
                if s!=c:refined[s]+=1
                im=ims[a['image_id']];x,y,w,h=a['bbox'];ok=all(isfinite(v) for v in (x,y,w,h)) and min(x,y)>=0 and min(w,h)>0 and x+w<=im['width']+1e-6 and y+h<=im['height']+1e-6
                if not ok:unusable+=1
                att=a.get('attributes') or {}
                for key in att:field_counts[key]+=1
                objs[a['image_id']].append(dict(id=k,category=c,sign_subclass=s if s!=c else None,attributes=att,attributes_present=a.get('attributes') is not None,bbox=a['bbox'],bbox_usable=ok))
            rows=[]
            for k,im in ims.items():
                name=im['file_name'];g,seq=group(im)
                if name in names:raise ValueError('duplicate filename')
                names.add(name);missing_group+=g is None;group_map[k]=g
                rawtags=im.get('scene_level_tags') or {};tags.update(rawtags.get('travel_alteration',[]));rows.append(dict(image_id=k,file_name=name,group=g,sequence=seq,source_split=split,source_annotation_sha256=digests[f'instances_{split}_gps_split.json'],gps=im.get('gps'),city=im.get('city_name'),width=im['width'],height=im['height'],scene_tags=rawtags,description=im.get('scene_description'),objects=objs[k],formal_targets=None))
            data[split]=rows;group_sets[split]={g for g in group_map.values() if g};summary[split]=dict(images=len(ims),annotations=len(anns),base_categories=len(cats),expanded_categories=len(scats),sign_refined=sum(refined.values()),sign_subclasses=dict(refined),attribute_fields=dict(field_counts),travel_alteration=dict(tags),groups=len(group_sets[split]),unknown_group_images=missing_group,invalid_bbox=unusable)
    overlap=group_sets['train']&group_sets['val'];names=lambda s:{x['file_name'] for x in data[s]}
    if names('train')&names('val'):raise ValueError('exact frame overlap')
    kept={s:[r for r in data[s] if r['group'] is not None and (s=='val' or r['group'] not in overlap)] for s in data}
    assert not {r['group'] for r in kept['train']}&{r['group'] for r in kept['val']}
    sites=site_audit(kept['train'],kept['val'])
    # Prior on full image composition conditioned on multi-label scene tags;
    # image counts and group counts distinct. No pairwise recombination.
    prior=collections.defaultdict(lambda:[0,set()])
    for r in kept['train']:
        key=json.dumps([r['scene_tags'],sorted(C(o['category'] for o in r['objects'] if o['bbox_usable']).items())],sort_keys=True,ensure_ascii=False);v=prior[key];v[0]+=1;v[1].add(r['group'])
    if manifest:
        manifest.mkdir(parents=True,exist_ok=True)
        if any(manifest.iterdir()):raise ValueError('empty output directory required')
        for s,rows in kept.items():
            with (manifest/f'{s}.jsonl').open('w') as f:
                for r in rows:f.write(json.dumps(r,ensure_ascii=False,allow_nan=False)+'\n')
        (manifest/'train_compositions.json').write_text(json.dumps([dict(context=json.loads(k),image_count=v[0],group_count=len(v[1])) for k,v in sorted(prior.items())],ensure_ascii=False))
    return dict(status='GROUP_DISJOINT_ANNOTATION_REFERENCE_PASS',scope='AUXILIARY_GROUP_SPLIT_NOT_OFFICIAL_GPS_BENCHMARK',splits=summary,shared_groups=len(overlap),shared_groups_sorted=sorted(overlap),train_shared_group_images=sum(r['group'] in overlap for r in data['train']),kept={s:len(rows) for s,rows in kept.items()},quarantined={s:len(data[s])-len(rows) for s,rows in kept.items()},distinct_train_joint_compositions=len(prior),site_proximity_audit=sites,input_sha256=digests,complete_scene_grouping_proved=False,physical_rule_labels=False,metric_geometry=False,images_or_masks_decoded=False)

def main():
    p=argparse.ArgumentParser();p.add_argument('--annotations',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--work',type=Path);a=p.parse_args();r=audit(a.annotations,a.work);a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n');print(r['status']);return 0
if __name__=='__main__':raise SystemExit(main())
