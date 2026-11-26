#!/usr/bin/env python3
import argparse,json
from pathlib import Path

def bind(templates,train,validation,audit):
    def index(rows):
        out={}
        for r in rows:
            k=(r['group'],r['image_id'],r['file_name'])
            if k in out:raise ValueError('duplicate manifest row')
            out[k]=r
        return out
    tr=index(train);va=index(validation)
    if set(tr)&set(va) or {k[0] for k in tr}&{k[0] for k in va}:raise ValueError('split overlap')
    hashes=set(audit['source_sha256'].values());kept=[];quarantine=[];seen=set()
    for t in templates:
        s=t['source'];k=(s['source_group'],s['source_image_id'],s['image_file']);reason=None
        if s['source_annotation_sha256'] not in hashes:reason='source annotation hash mismatch'
        elif k not in tr or s['source_split']!='train' or tr[k]['source_annotation_sha256']!=s['source_annotation_sha256']:reason='not in strict train manifest'
        elif k in seen:reason='duplicate template image'
        if reason:quarantine.append({'reason':reason,'template':t});continue
        seen.add(k);kept.append(t)
    return kept,quarantine

def main():
    p=argparse.ArgumentParser();p.add_argument('--strict',type=Path,required=True);p.add_argument('--templates',type=Path,required=True);p.add_argument('--output-dir',type=Path,required=True);a=p.parse_args()
    load=lambda p:[json.loads(l) for l in p.read_text().splitlines() if l.strip()]
    r,q=bind(load(a.templates),load(a.strict/'train.jsonl'),load(a.strict/'validation.jsonl'),json.loads((a.strict/'audit.json').read_text()));a.output_dir.mkdir(parents=True,exist_ok=False)
    for name,rows in [('train_templates',r),('quarantine',q)]: (a.output_dir/(name+'.jsonl')).write_text(''.join(json.dumps(x,ensure_ascii=False)+'\n' for x in rows))
    summary=dict(status='STRICT_MANIFEST_VISUAL_ONLY' if r else 'REVIEW_EMPTY',accepted=len(r),quarantined=len(q),formal_labels_authorized=False);(a.output_dir/'review.json').write_text(json.dumps(summary,indent=2)+'\n');print(summary);return 0 if r else 4
if __name__=='__main__':raise SystemExit(main())
