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

def stream_records(manifest, *, reader=_iter_tfrecord, decoder=decode):
    from ..record_adapters import parse_womd_scenario_proto
    validate_manifest(manifest)
    root = Path(manifest['root']).resolve()
    groups = {}
    for row in manifest['records']:
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
