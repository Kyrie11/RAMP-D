#!/usr/bin/env python3
"""Independent ROADWork GPS-split inventory and bounded pixel alignment audit.

Reads official extracted directories or archives without extraction. Counts all COCO-like metadata
for one official split family only. Does not infer metric resource geometry,
formal rule state, incident timing, or real traffic-flow probabilities.
"""
import argparse
from collections import Counter, defaultdict
from contextlib import ExitStack
import hashlib
import io
import json
import math
from pathlib import Path, PurePosixPath
import statistics
import zipfile


def archive(root, names):
    for folder in (root, root/'archives'):
        for name in names:
            p=folder/name
            if p.is_file(): return p
    raise FileNotFoundError('missing archive: '+', '.join(names))


class DirectoryMember:
    def __init__(self, path, root):
        self.path=path
        self.filename=path.relative_to(root).as_posix()
    def is_dir(self): return False

class DirectoryReader:
    def __init__(self, root): self.root=root
    def __enter__(self): return self
    def __exit__(self, *args): return False
    def infolist(self):
        return [DirectoryMember(p,self.root) for p in sorted(self.root.rglob('*')) if p.is_file()]
    def read(self, member): return member.path.read_bytes()


def locate(root, dirs, archives):
    # Prefer explicitly extracted scene tree; do not recurse into pathways.
    for name in dirs:
        p=root/name
        if p.is_dir(): return p
    return archive(root, archives)


def reader(path):
    return DirectoryReader(path) if path.is_dir() else zipfile.ZipFile(path)


def index(z):
    out=defaultdict(list)
    for i in z.infolist():
        if not i.is_dir(): out[PurePosixPath(i.filename).name].append(i)
    return out


def unique(idx,name):
    rows=idx.get(PurePosixPath(name).name,[])
    if len(rows)!=1: raise ValueError(f'expected unique archive member {name}, got {len(rows)}')
    return rows[0]


def unique_ids(rows,key):
    out={}
    for r in rows:
        k=r[key]
        if k in out: raise ValueError(f'duplicate {key}: {k}')
        out[k]=r
    return out


def positive_int(x): return type(x) is int and x>0


def audit(root: Path, sample_per_split=6, plot=None):
    from PIL import Image, ImageDraw
    if type(sample_per_split) is not int or sample_per_split<=0: raise ValueError('positive sample required')
    files={'annotations':locate(root,('annotations','scene/annotations'),('annotations.zip',)),
           'images':locate(root,('images','scene/images'),('images.zip',)),
           'semantic':locate(root,('gtFine','scene/gtFine','scene/sem_seg/gtFine','sem_seg/gtFine'),('sem_seg_labels.zip','sem_seg_lables.zip'))}
    out={'status':'ERROR','scope':'GPS_SPLIT_METADATA_AND_BOUNDED_PIXEL_ALIGNMENT_ONLY',
         'archives':{k:{'path':str(p),'bytes':p.stat().st_size if p.is_file() else None,'storage':'directory' if p.is_dir() else 'zip'} for k,p in files.items()},
         'splits':[], 'formal_rule_labels_generated':False,'metric_resource_geometry_generated':False,
         'traffic_flow_labels_generated':False,'event_time_labels_generated':False,'full_geographic_leakage_checked':False}
    panels=[]; sets={}; all_names={}; all_keys={};
    with ExitStack() as ctx:
        za,zi,zs=(ctx.enter_context(reader(files[k])) for k in ('annotations','images','semantic'))
        ia,ii,iss=map(index,(za,zi,zs))
        for split in ('train','val'):
            member=unique(ia,f'instances_{split}_gps_split.json'); raw=za.read(member); data=json.loads(raw)
            images=unique_ids(data['images'],'id'); categories=unique_ids(data['categories'],'id'); anns=unique_ids(data['annotations'],'id')
            if not images or not categories or not anns: raise ValueError('empty official split')
            names={}; imfields=Counter(); anfields=Counter(); percat=Counter(); imagecats=defaultdict(set); sizes=defaultdict(list); byimage=defaultdict(list); segtypes=Counter(); pairs=Counter()
            for i,r in images.items():
                if not positive_int(r['width']) or not positive_int(r['height']): raise ValueError(f'invalid image size {i}')
                name=PurePosixPath(r['file_name']).name
                if name in names: raise ValueError('duplicate filename '+name)
                names[name]=i; unique(ii,name); unique(iss,PurePosixPath(name).stem+'_labelIds.png');imfields.update(r.keys())
            for a in anns.values():
                i,c=a['image_id'],a['category_id']; r=images[i]; cat=categories[c]['name']
                box=a['bbox']
                if len(box)!=4 or any(not isinstance(x,(float,int)) or isinstance(x,bool) or not math.isfinite(x) for x in box): raise ValueError('invalid bbox')
                x,y,w,h=box
                # COCO allows zero area/crowd anomalies in some releases; reject
                # nonphysical extents, record out-of-image anomalies explicitly.
                if min(w,h)<=0: raise ValueError('nonpositive bbox extent')
                if x<0 or y<0 or x+w>r['width']+1e-6 or y+h>r['height']+1e-6: pairs['bbox_outside_image']+=1
                percat[cat]+=1; imagecats[i].add(cat); sizes[cat].append(w*h/(r['width']*r['height'])); byimage[i].append(a);anfields.update(a.keys())
                seg=a.get('segmentation');segtypes['polygon' if isinstance(seg,list) and seg else 'rle' if isinstance(seg,dict) else 'missing_or_empty']+=1
            for values in imagecats.values():
                cats=sorted(values)
                for j,left in enumerate(cats):
                    for right in cats[j+1:]: pairs[(left,right)]+=1
            keys=sorted(names); selected=[keys[i*len(keys)//min(sample_per_split,len(keys))] for i in range(min(sample_per_split,len(keys)))]; samples=[]
            for name in selected:
                r=images[names[name]]; info=unique(ii,name)
                with Image.open(io.BytesIO(zi.read(info))) as src:
                    src.load(); image=src.convert('RGB')
                if image.size!=(r['width'],r['height']): raise ValueError('image metadata size mismatch: '+name)
                stem=PurePosixPath(name).stem; mask_info=unique(iss,stem+'_labelIds.png')
                with Image.open(io.BytesIO(zs.read(mask_info))) as src:
                    src.load(); mask_size=src.size; mask_mode=src.mode; extrema=src.getextrema()
                    if mask_mode not in ('L','P','I','I;16','I;16B','I;16L'): raise ValueError('labelIds must be scalar or palette indices: '+name)
                    hist=Counter(src.get_flattened_data() if hasattr(src,'get_flattened_data') else src.getdata())
                if mask_size!=image.size: raise ValueError('image / labelIds size mismatch: '+name)
                samples.append({'image':name,'size':list(image.size),'mask_mode':mask_mode,'mask_extrema':extrema,'mask_pixel_counts':dict(hist),'annotations':len(byimage[r['id']])})
                if plot is not None:
                    draw=ImageDraw.Draw(image)
                    for a in byimage[r['id']]:
                        x,y,w,h=a['bbox'];draw.rectangle((x,y,x+w,y+h),outline='yellow',width=max(1,image.width//400));draw.text((max(0,x),max(0,y-11)),str(categories[a['category_id']]['name'])[:24],fill='yellow')
                    image.thumbnail((480,270));panels.append((split,name,image))
            sets[split]=set(names); all_names[split]=len(names)
            out['splits'].append({'split':split,'annotation_member':member.filename,'annotation_sha256':hashlib.sha256(raw).hexdigest(),
                'images':len(images),'annotations':len(anns),'categories':sorted(set(c['name'] for c in categories.values())),
                'category_instances':dict(percat),'category_image_counts':dict(Counter(c for v in imagecats.values() for c in v)),
                'median_relative_bbox_area':{k:statistics.median(v) for k,v in sizes.items()},
                'cooccurrence_image_counts': [{'categories':list(k),'images':v} for k,v in sorted(((k,v) for k,v in pairs.items() if isinstance(k,tuple)))],
                'bbox_outside_image':pairs['bbox_outside_image'],'image_fields':dict(imfields),'annotation_fields':dict(anfields),
                'segmentation_types':dict(segtypes),'decoded_samples':samples})
        overlap=sorted(sets['train']&sets['val']);out['exact_filename_overlap']=overlap
        if overlap: raise ValueError('GPS split exact filename overlap')
        if any(g['bbox_outside_image'] for g in out['splits']):
            out['status']='REVIEW_REQUIRED_BBOX_EXTENTS'
        else: out['status']='BOUNDED_ROADWORK_ALIGNMENT_PASS'
    if plot is not None:
        canvas=Image.new('RGB',(960,300*((len(panels)+1)//2)), '#20252b');draw=ImageDraw.Draw(canvas)
        for k,(sp,name,im) in enumerate(panels):
            x=(k%2)*480;y=(k//2)*300;canvas.paste(im,(x,y+25));draw.text((x+4,y+4),f'{sp}: {name}'[:75],fill='white')
        plot.parent.mkdir(parents=True,exist_ok=True);canvas.save(plot)
    return out


def main():
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);p.add_argument('--samples-per-split',type=int,default=6);p.add_argument('--output',type=Path,required=True);p.add_argument('--plot',type=Path);a=p.parse_args()
    try: out=audit(a.root,a.samples_per_split,a.plot)
    except Exception as e: out={'status':'ERROR','scope':'GPS_SPLIT_METADATA_AND_BOUNDED_PIXEL_ALIGNMENT_ONLY','reason':f'{type(e).__name__}: {e}'}
    a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(out,indent=2,ensure_ascii=False)+'\n');print(out['status']);return 0 if out['status']=='BOUNDED_ROADWORK_ALIGNMENT_PASS' else 4
if __name__=='__main__': raise SystemExit(main())
