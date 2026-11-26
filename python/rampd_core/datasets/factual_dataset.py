"""Bounded pilot cache, source-bound at prepare time; no giant inventory JSON.
The cache SHA is an integrity check, not a signature or independently trusted proof.
"""
from pathlib import Path
import json, hashlib
from .split_manifest import validate_manifest, stream_records, canonical_digest
from .feature_contract import build_features


def file_sha(path):
    h=hashlib.sha256()
    with open(path,'rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''): h.update(b)
    return h.hexdigest()

def prepare(manifest, output, *, horizon=10, history_steps=11, max_agents=128,max_map=256, reader=None, decoder=None):
    validate_manifest(manifest); out=Path(output); out.mkdir(parents=True,exist_ok=False)
    settings=dict(horizon=horizon,history_steps=history_steps,max_agents=max_agents,max_map=max_map)
    expected={r['scenario_id']:r for r in manifest['records']}; seen=set(); accepted=[]; rejected=[]
    paths={s:out/f'{s}.jsonl' for s in ('training','validation')}
    with paths['training'].open('x') as train, paths['validation'].open('x') as val:
        # Dependency injection is for raw-reader/protobuf unit fixtures only.
        # Even those fixtures must pass the record-byte allowlist and parser.
        kwargs={}
        if reader is not None: kwargs['reader']=reader
        if decoder is not None: kwargs['decoder']=decoder
        for record in stream_records(manifest,**kwargs):
            m=record['scene']['manifest']; sid=m['scenario_id']; e=expected.get(sid)
            if e is None or sid in seen or e['record_sha256']!=record['record_sha256'] or e['split']!=m['split'] or e['record_index']!=record['record_index'] or (Path(manifest['root'])/e['shard']).resolve()!=Path(record['source_file']).resolve(): raise ValueError('record not in audited allowlist')
            seen.add(sid)
            try: row=build_features(record,**settings)
            except ValueError as exc:
                rejected.append(dict(scenario_id=sid,split=m['split'],reason=str(exc))); continue
            row['training_allowed']=m['split']=='training'; (train if row['training_allowed'] else val).write(json.dumps(row,separators=(',',':'),allow_nan=False)+'\n')
            accepted.append(dict(scenario_id=sid,split=m['split'],record_sha256=e['record_sha256'],**row['stats'],**row['context']))
    if seen!=set(expected): raise ValueError('allowlist not fully consumed')
    summary=dict(schema='rampd.factual_cache.v1',manifest_sha256=canonical_digest(manifest),settings=settings,accepted=accepted,rejected=rejected,files={s:file_sha(p) for s,p in paths.items()},scope='BOUNDED_PILOT_NOT_GLOBAL_SPLIT')
    (out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n'); (out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    if not all(any(r['split']==s for r in accepted) for s in paths): raise ValueError('one split has no eligible scenes')
    return summary

def load_cache(directory, *, max_rows=1000):
    directory=Path(directory); manifest=json.loads((directory/'manifest.json').read_text()); summary=json.loads((directory/'summary.json').read_text()); validate_manifest(manifest)
    if summary['schema']!='rampd.factual_cache.v1' or summary['manifest_sha256']!=canonical_digest(manifest): raise ValueError('cache manifest binding')
    allow={r['scenario_id']:r for r in manifest['records']}; expected={r['scenario_id'] for r in summary['accepted']}; seen=set(); sets={}
    for split in ('training','validation'):
        path=directory/f'{split}.jsonl'
        if file_sha(path)!=summary['files'][split]: raise ValueError('cache bytes mismatch')
        rows=[]
        with path.open() as f:
            for line in f:
                if len(rows)>=max_rows: raise ValueError('pilot cache too large; use bounded pilot')
                r=json.loads(line); sid=r['scenario_id']; e=allow.get(sid)
                if (e is None or sid in seen or sid not in expected or e['record_sha256']!=r['source_digest'] or e['split']!=split or r['split']!=split or r['training_allowed'] is not (split=='training')): raise ValueError('cache split authorization failure')
                seen.add(sid); rows.append(r)
        if not rows: raise ValueError('empty split')
        sets[split]=rows
    if seen!=expected: raise ValueError('cache accepted roster mismatch')
    return sets,summary
