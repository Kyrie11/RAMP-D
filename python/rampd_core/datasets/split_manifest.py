"""Pilot allowlist from official Scenario directories, never from label rows.
Identity audit is scoped to scanned records; it is not global log-family isolation.
"""
from __future__ import annotations
from pathlib import Path
import hashlib, json
from itertools import islice
from ..record_adapters import _iter_tfrecord

SCHEMA = 'rampd.womd.pilot_manifest.v1'
SPLITS = ('training', 'validation')

def canonical_digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()

def validate_manifest(manifest):
    if manifest.get('schema') != SCHEMA or manifest.get('scope') != 'BOUNDED_OFFICIAL_DIRECTORY_PILOT':
        raise ValueError('invalid manifest scope')
    seen, hashes, locations = set(), set(), set()
    counts = dict.fromkeys(SPLITS, 0)
    for r in manifest['records']:
        split, sid, digest = r['split'], r['scenario_id'], r['record_sha256']
        rel = Path(r['shard'])
        if (split not in SPLITS or not sid or rel.is_absolute() or '..' in rel.parts or not rel.parts or rel.parts[0] != split
                or type(r['record_index']) is not int or r['record_index'] < 0
                or len(digest) != 64 or any(c not in '0123456789abcdef' for c in digest)):
            raise ValueError('invalid record identity')
        loc = (str(rel), r['record_index'])
        if sid in seen or digest in hashes or loc in locations:
            raise ValueError('duplicate or cross-split identity/record/location')
        seen.add(sid); hashes.add(digest); locations.add(loc); counts[split] += 1
    # Previously inspected official development records are never authorized for
    # future training or refreshed validation, including across repeated refreshes.
    for r in manifest.get('excluded_validation_records',[]):
        sid,digest,rel=r['scenario_id'],r['record_sha256'],Path(r['shard']);loc=(str(rel),r['record_index'])
        if r['split']!='validation' or not sid or rel.is_absolute() or '..' in rel.parts or not rel.parts or rel.parts[0]!='validation' or type(r['record_index']) is not int or r['record_index']<0 or len(digest)!=64 or any(c not in '0123456789abcdef' for c in digest):raise ValueError('invalid prior validation exclusion')
        if sid in seen or digest in hashes or loc in locations:raise ValueError('prior validation identity reused')
        seen.add(sid);hashes.add(digest);locations.add(loc)
    if not all(counts.values()):
        raise ValueError('both official splits required')
    return counts

def _shards(root, split):
    folder = root / split
    if not folder.is_dir() or folder.is_symlink() or folder.resolve() != folder:
        raise ValueError(f'missing or aliased official split: {folder}')
    paths = sorted(p for p in folder.rglob('*') if p.is_file() and (p.name.endswith('.tfrecord') or '.tfrecord-' in p.name))
    if not paths: raise ValueError(f'no Scenario shards: {folder}')
    for p in paths:
        if not p.resolve().is_relative_to(folder.resolve()) or p.is_symlink():
            raise ValueError('shard escapes official directory')
    return paths

def decode(payload):
    from waymo_open_dataset.protos import scenario_pb2
    s = scenario_pb2.Scenario(); s.ParseFromString(payload)
    if not s.scenario_id or not s.tracks or not s.timestamps_seconds or not 0 <= s.sdc_track_index < len(s.tracks):
        raise ValueError('not a valid WOMD Scenario record')
    return s

def build_manifest(root, *, train_limit=5, validation_limit=5, max_shards=2, reader=_iter_tfrecord, decoder=decode):
    root = Path(root).resolve()
    if min(train_limit, validation_limit, max_shards) <= 0: raise ValueError('positive limits required')
    records = []
    for split, limit in zip(SPLITS, (train_limit, validation_limit)):
        files = _shards(root, split)
        k = min(max_shards, limit, len(files))
        files = [files[i*(len(files)-1)//(k-1)] for i in range(k)] if k > 1 else files[:1]
        remaining = limit
        for j, path in enumerate(files):
            quota = (remaining + len(files)-j-1)//(len(files)-j)
            for index, raw in enumerate(islice(reader(path), quota)):
                s = decoder(raw)
                records.append(dict(split=split, scenario_id=s.scenario_id, shard=path.relative_to(root).as_posix(), record_index=index, record_sha256=hashlib.sha256(raw).hexdigest()))
                remaining -= 1
        if remaining: raise ValueError(f'{split}: requested {limit}, missing {remaining}')
    manifest = dict(schema=SCHEMA, scope='BOUNDED_OFFICIAL_DIRECTORY_PILOT', root=str(root), records=records, excluded=['training_20s','testing','tf_example'], overlap_guarantee='EXACT_ID_AND_RECORD_ONLY_WITHIN_PILOT')
    validate_manifest(manifest)
    return manifest

def stream_records(manifest, *, reader=_iter_tfrecord, decoder=decode, selected_ids=None):
    from ..record_adapters import parse_womd_scenario_proto
    validate_manifest(manifest)
    root = Path(manifest['root']).resolve()
    groups = {}
    if selected_ids is not None:
        selected_ids=set(selected_ids)
        if not selected_ids or not selected_ids<={r['scenario_id'] for r in manifest['records']}:raise ValueError('selected ids absent from manifest')
    for row in manifest['records']:
        if selected_ids is not None and row['scenario_id'] not in selected_ids:continue
        groups.setdefault((row['split'],row['shard']), {})[row['record_index']] = row
    for (split, rel), wanted in groups.items():
        path = root / rel
        if (root/split).is_symlink() or (root/split).resolve()!=root/split or not path.resolve().is_relative_to(root/split) or path.is_symlink():
            raise ValueError('source escaped manifest split')
        found = set()
        for i, raw in enumerate(islice(reader(path), max(wanted)+1)):
            if i not in wanted: continue
            r = wanted[i]; digest = hashlib.sha256(raw).hexdigest(); s = decoder(raw)
            if digest != r['record_sha256'] or s.scenario_id != r['scenario_id']:
                raise ValueError('raw record changed after split audit')
            found.add(i)
            yield parse_womd_scenario_proto(s, source_file=path, record_index=i, record_sha256=digest, split=split).to_dict()
        if found != set(wanted): raise ValueError('manifest record missing')


def extend_training_manifest(base, *, train_limit, max_shards=10, reader=_iter_tfrecord, decoder=decode):
    """Grow a training pilot while preserving the validation and existing train identity.
    Original byte identities are checked again by stream_records at prepare time.
    """
    counts=validate_manifest(base)
    if type(train_limit) is not int or train_limit<counts['training'] or max_shards<1:raise ValueError('cannot shrink base training roster')
    root=Path(base['root']).resolve(); records=[dict(r) for r in base['records']]; remaining=train_limit-counts['training']
    seen_id={r['scenario_id'] for r in records};seen_hash={r['record_sha256'] for r in records};seen_loc={(r['shard'],r['record_index']) for r in records}
    if remaining:
        files=_shards(root,'training');k=min(max_shards,len(files));files=[files[i*(len(files)-1)//(k-1)] for i in range(k)] if k>1 else files[:1]
        for j,path in enumerate(files):
            if not remaining:break
            quota=(remaining+len(files)-j-1)//(len(files)-j); rel=path.relative_to(root).as_posix();added=0
            for index,raw in enumerate(reader(path)):
                if (rel,index) in seen_loc:continue
                s=decoder(raw); digest=hashlib.sha256(raw).hexdigest()
                if s.scenario_id in seen_id or digest in seen_hash:raise ValueError('duplicate or cross-split identity while extending')
                records.append(dict(split='training',scenario_id=s.scenario_id,shard=rel,record_index=index,record_sha256=digest));seen_loc.add((rel,index));seen_id.add(s.scenario_id);seen_hash.add(digest);remaining-=1;added+=1
                if added>=quota:break
        if remaining:raise ValueError(f'training extension missing {remaining} records')
    out=dict(base,records=records,base_manifest_sha256=canonical_digest(base));validate_manifest(out);return out


def replace_validation_manifest(base, *, validation_limit, max_shards=20, reader=_iter_tfrecord, decoder=decode):
    """Keep existing training identities, exclude the previously inspected
    validation identities/locations, and choose a fresh official development set.
    Exact record separation, not global geographic/log-window separation.
    """
    validate_manifest(base)
    if type(validation_limit) is not int or validation_limit<1 or max_shards<1:raise ValueError('fresh validation limits')
    root=Path(base['root']).resolve();records=[dict(r) for r in base['records'] if r['split']=='training'];old=[r for r in base['records'] if r['split']=='validation']
    # Preserve accumulated diagnostic exclusions when refreshing again.
    old+=list(base.get('excluded_validation_records',[])); byid={r['scenario_id']:r for r in old}; byloc={(r['shard'],r['record_index']):r for r in old}; oldhash={r['record_sha256'] for r in old}
    seen_id={r['scenario_id'] for r in records};seen_hash={r['record_sha256'] for r in records}
    if seen_id&byid.keys() or seen_hash&oldhash:raise ValueError('prior validation became training')
    files=_shards(root,'validation');k=min(max_shards,validation_limit,len(files));files=[files[i*(len(files)-1)//(k-1)] for i in range(k)] if k>1 else files[:1]
    remaining=validation_limit
    for j,path in enumerate(files):
        if not remaining:break
        quota=(remaining+len(files)-j-1)//(len(files)-j);rel=path.relative_to(root).as_posix();added=0
        for index,raw in enumerate(reader(path)):
            s=decoder(raw);digest=hashlib.sha256(raw).hexdigest();prior=byloc.get((rel,index))
            if prior is not None:
                if s.scenario_id!=prior['scenario_id'] or digest!=prior['record_sha256']:raise ValueError('old validation source changed')
                continue
            if s.scenario_id in byid or digest in oldhash:raise ValueError('old validation record moved or repeated')
            if s.scenario_id in seen_id or digest in seen_hash:raise ValueError('cross-split/duplicate fresh validation')
            records.append(dict(split='validation',scenario_id=s.scenario_id,shard=rel,record_index=index,record_sha256=digest));seen_id.add(s.scenario_id);seen_hash.add(digest);remaining-=1;added+=1
            if added>=quota:break
    if remaining:raise ValueError(f'fresh validation missing {remaining} records')
    out=dict(base,records=records,excluded_validation_records=old,previous_manifest_sha256=canonical_digest(base),validation_policy='FRESH_OFFICIAL_DEVELOPMENT_EXCLUDING_PREVIOUS_DIAGNOSTIC_IDS')
    validate_manifest(out);return out


def validate_external_evaluation(original,external):
    """Exact-record split gate for a frozen external validation-only evaluation.
    Excludes all prior train/validation/previously inspected records. Does not
    imply geographical or recording-family isolation.
    """
    validate_manifest(original);validate_manifest(external)
    prior=original['records']+original.get('excluded_validation_records',[])
    ids={r['scenario_id'] for r in prior};hashes={r['record_sha256'] for r in prior};loc={(r['shard'],r['record_index']) for r in prior}
    rows=[r for r in external['records'] if r['split']=='validation']
    if any(r['scenario_id'] in ids or r['record_sha256'] in hashes or (r['shard'],r['record_index']) in loc for r in rows):raise ValueError('external evaluation overlaps original/development record')
    return dict(validation_records=len(rows),scope='EXACT_RECORD_DISJOINT_NOT_GEOGRAPHIC_FAMILY_PROOF')
