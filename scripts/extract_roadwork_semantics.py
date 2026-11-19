#!/usr/bin/env python3
"""GPS split raw semantic extraction; train-only empirical visual composition.
Do not infer legal permission, metric geometry, or physical/event timestamps.
"""
import argparse, hashlib, json, math, re
from collections import Counter, defaultdict
from pathlib import Path, PurePosixPath
from audit_roadwork import locate, reader, index, unique, unique_ids, positive_int


def canonical(v):
    return json.dumps(v,sort_keys=True,ensure_ascii=False,separators=(',',':'),allow_nan=False)


def extract(root, output_dir, alignment):
    if alignment.get('status')!='BOUNDED_ROADWORK_ALIGNMENT_PASS':raise ValueError('alignment audit must pass first')
    expected={s['split']:s for s in alignment['splits']}
    if set(expected)!={'train','val'}:raise ValueError('missing split')
    path=locate(root, ('annotations','scene/annotations'), ('annotations.zip',))
    output_dir.mkdir(parents=True,exist_ok=True)
    if any(output_dir.iterdir()):raise ValueError("semantic work directory must be empty")
    summary={}; filenames={}; video_keys={}; comp={}
    with reader(path) as z:
        idx=index(z)
        for split in ('train','val'):
            raw=z.read(unique(idx,f'instances_{split}_gps_split.json'));digest=hashlib.sha256(raw).hexdigest()
            if digest!=expected[split]['annotation_sha256']:raise ValueError('annotation digest differs from alignment report')
            data=json.loads(raw);images=unique_ids(data['images'],'id');anns=unique_ids(data['annotations'],'id');cats=unique_ids(data['categories'],'id')
            if len(images)!=expected[split]['images'] or len(anns)!=expected[split]['annotations']:raise ValueError('alignment count mismatch')
            byimage=defaultdict(list); raw_count=Counter(); good_count=Counter(); invalid=0; attribute_types=defaultdict(Counter); tag_types=Counter(); attr_values=defaultdict(Counter); tag_values=Counter(); compositions=Counter(); complete_video=0; videos=set(); names=set()
            for ann in anns.values():
                im=images[ann['image_id']];cat=cats[ann['category_id']]['name'];x,y,w,h=ann['bbox']
                if not all(type(v) in (int,float) and math.isfinite(v) for v in (x,y,w,h)) or min(w,h)<0:raise ValueError('bad bbox')
                geometry=w>0 and h>0 and x>=0 and y>=0 and x+w<=im['width']+1e-6 and y+h<=im['height']+1e-6
                if geometry:good_count[cat]+=1
                else:invalid+=1
                raw_count[cat]+=1; attr=ann.get('attributes'); attribute_types[cat][type(attr).__name__]+=1
                if isinstance(attr,dict):
                    for k,v in attr.items():attr_values[(cat,k)][canonical(v)]+=1
                byimage[im['id']].append(dict(annotation_id=ann['id'],category=cat,bbox=ann['bbox'],bbox_geometry_usable=geometry,source_attributes=attr,attributes_present='attributes' in ann and attr is not None))
            if dict(raw_count)!=expected[split]['category_instances'] or dict(good_count)!=expected[split]['geometry_usable_category_instances']:raise ValueError('category inventory mismatch')
            final=output_dir/f'{split}_visual_semantics.jsonl';tmp=final.with_suffix('.tmp')
            with tmp.open('w',encoding='utf-8') as f:
                for im in sorted(images.values(),key=lambda r:str(r['id'])):
                    name=PurePosixPath(im['file_name']).name
                    if name in names:raise ValueError('duplicate filename')
                    names.add(name); tags=im.get('scene_level_tags'); tag_types[type(tags).__name__]+=1
                    if tags is not None:tag_values[canonical(tags)]+=1
                    # Names with official city_hash_sequence_frame pattern: group
                    # by video hash, not frame. No assumption for other names.
                    m=re.search(r'_([0-9a-fA-F]{16,})_[0-9]+_[0-9]+\.[^.]+$',name)
                    if m:videos.add(m[1].lower());complete_video+=1
                    objects=byimage[im['id']];counts=Counter(o['category'] for o in objects if o['bbox_geometry_usable'])
                    compositions[canonical(sorted(counts.items()))]+=1
                    record=dict(source='ROADWork_GPS',split=split,annotation_sha256=digest,image_id=im['id'],file_name=im['file_name'],size=[im['width'],im['height']],scene_level_tags=tags,scene_description=im.get('scene_description'),gps=im.get('gps'),city_name=im.get('city_name'),video_info=im.get('video_info'),objects=objects,visual_only=True,formal_rule_target=None,event_clock_target=None,metric_geometry_target=None)
                    f.write(canonical(record)+'\n')
            tmp.replace(final);filenames[split]=names;video_keys[split]=videos;comp[split]=compositions
            summary[split]=dict(images=len(images),annotations=len(anns),sha256=digest,geometry_excluded=invalid,attribute_types={k:dict(v) for k,v in attribute_types.items()},attribute_values=[dict(category=k[0],field=k[1],distinct=len(v),top_values=v.most_common(15)) for k,v in sorted(attr_values.items())],scene_tag_types=dict(tag_types),top_raw_scene_tags=tag_values.most_common(20),video_hash_covered_images=complete_video,unique_inferred_video_hashes=len(videos),distinct_visual_compositions=len(compositions),artifact=str(final))
    overlap=sorted(filenames['train']&filenames['val']); video_overlap=sorted(video_keys['train']&video_keys['val'])
    prior=output_dir/'train_visual_compositions.json'
    if not overlap and not video_overlap:prior.write_text(canonical(dict(scope='EMPIRICAL_IMAGE_OBJECT_COUNTS_NOT_SPATIAL_OR_PHYSICAL_PRIOR',split='train',annotation_sha256=summary['train']['sha256'],compositions=[dict(counts=json.loads(k),images=v) for k,v in sorted(comp['train'].items())]))+'\n')
    return dict(status='VISUAL_SOURCE_EXTRACTION_PASS' if not overlap and not video_overlap else 'REVIEW_REQUIRED_SPLIT_OVERLAP',scope='RAW_VISUAL_SEMANTICS_NOT_FORMAL_RULE_LABELS',splits=summary,exact_filename_overlap=overlap,inferred_video_hash_overlap=video_overlap,complete_grouping_proved=False,semantic_vocabulary_verified=False,train_visual_prior=str(prior) if prior.exists() else None,formal_rule_labels_generated=False,metric_geometry_generated=False)


def main():
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);p.add_argument('--alignment',type=Path,required=True);p.add_argument('--work',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    try:out=extract(a.root,a.work,json.loads(a.alignment.read_text()))
    except Exception as e:out=dict(status='ERROR',reason=f'{type(e).__name__}: {e}')
    a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(out,indent=2,ensure_ascii=False,allow_nan=False)+'\n');print(out['status']);return 0 if out['status']=='VISUAL_SOURCE_EXTRACTION_PASS' else 4
if __name__=='__main__':raise SystemExit(main())
