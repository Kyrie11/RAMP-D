#!/usr/bin/env python3
"""Bounded, read-only label coverage audit on the real train/validation splits.

Does not generate simulator/proof labels, choose legal resource polygons, or
train a model. Unavailable readers and empty/missing data do not count as PASS.
"""
from __future__ import annotations
import argparse
from collections import Counter
import importlib
import json
import platform
from importlib.metadata import version, PackageNotFoundError
from pathlib import Path
import sys
import types
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'python'))
pkg=types.ModuleType('rampd_core');pkg.__path__=[str(ROOT/'python/rampd_core')];sys.modules['rampd_core']=pkg
for name in ('map_context','scene_schema','protocol','record_adapters','forecast','phase6c','a5_logged_labels'):
    importlib.import_module('rampd_core.'+name)
from rampd_core.record_adapters import iter_womd_split,iter_av2_split,OptionalDependencyError
from rampd_core.phase6c import build_scene_forecast_sample
from rampd_core.a5_logged_labels import factual_joint_labels,sampled_signal_changes


def probe(root, dataset, split, n, nfiles, prefix_steps):
    out={'dataset':dataset,'split':split,'status':'ERROR','records':[],'root':str(root)}
    try:
        iterator=(iter_womd_split(root,split=split,max_records=n,max_files=nfiles,spread_shards=True) if dataset=='WOMD'
                  else iter_av2_split(root,split=split,max_records=n,hash_source_files=True))
        for p in iterator:
            s=build_scene_forecast_sample(p.scene)
            label=factual_joint_labels(s,prefix_steps); signals=sampled_signal_changes(s)
            out['records'].append({'scenario_id':s.scenario_id,'record_sha256':p.record_sha256,
              'source_file':p.source_file,'source_digest':s.source_digest,
              'raw_record_or_file_sha256':p.record_sha256 or p.source_file_sha256,'coordinate_frame':s.coordinate_frame,
              'position_reference':s.position_reference,'time_axis_source':p.scene.manifest.metadata.get('time_axis_source'),
              'source_endpoint_precision':p.scene.manifest.metadata.get('source_endpoint_precision'),
              'status':label.status,'ego_id':label.ego_id,
              'prefix_digest':label.ego_prefix_digest,'actor_count':len(label.actor_ids),
              'valid_actor_time_knots':sum(sum(x) for x in label.valid_mask),
              'auxiliary_signal_change_brackets':len(signals),
              'target_knots_with_box_dimensions':sum(1 for a in s.future_targets for state,mask in zip(a.states,a.valid_future_mask)
                  if mask and state.length is not None and state.width is not None and state.length>0 and state.width>0),
              'joint_target_knots_with_box_dimensions':sum(1 for a in s.future_targets if a.track_id in label.actor_ids for state,mask in zip(a.states,a.valid_future_mask)
                  if mask and state.length is not None and state.width is not None and state.length>0 and state.width>0),
              'polygon_count':0 if s.map_context_history is None else sum(p.geometry_type=='polygon' for p in s.map_context_history.primitives)})
        ids=[r['scenario_id'] for r in out['records']]
        if len(ids)!=n or len(ids)!=len(set(ids)):
            raise ValueError(f'expected {n} distinct records, got {len(ids)}')
        counts=Counter(r['status'] for r in out['records']);out['label_status_counts']=dict(counts)
        out['distinct_source_files']=len(set(r['source_file'] for r in out['records']))
        out['status']='PASS' if counts['LOGGED_EGO_PATH_SURROGATE']==n else 'NO_USABLE_LABELS'
    except (FileNotFoundError,ImportError,ModuleNotFoundError,OptionalDependencyError) as exc:
        out.update(status='SKIP',reason=f'{type(exc).__name__}: {exc}')
    except Exception as exc:
        out.update(status='ERROR',reason=f'{type(exc).__name__}: {exc}')
    return out


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--womd-root',type=Path,required=True);ap.add_argument('--av2-root',type=Path,required=True)
    ap.add_argument('--max-records',type=int,default=20);ap.add_argument('--max-files',type=int,default=3)
    ap.add_argument('--prefix-steps',type=int,default=10);ap.add_argument('--output',type=Path,required=True)
    a=ap.parse_args()
    if min(a.max_records,a.max_files,a.prefix_steps)<=0:ap.error('positive limits required')
    groups=[probe(root,data,split,a.max_records,a.max_files,a.prefix_steps) for data,root,splits in
            [('WOMD',a.womd_root,('training','validation')),('AV2',a.av2_root,('train','validation'))] for split in splits]
    overlaps={}
    for n in (0,2):
        r1,r2=groups[n]['records'],groups[n+1]['records']
        ids=set(x['scenario_id'] for x in r1)&set(x['scenario_id'] for x in r2)
        hashes=set(x['raw_record_or_file_sha256'] for x in r1 if x['raw_record_or_file_sha256'])&set(x['raw_record_or_file_sha256'] for x in r2 if x['raw_record_or_file_sha256'])
        comparable=bool(r1 and r2 and all(x['raw_record_or_file_sha256'] for x in (*r1,*r2)))
        overlaps[groups[n]['dataset']]={'scenario_ids':sorted(ids),'record_hashes':sorted(hashes),'raw_hash_comparison_available':comparable}
    ok=all(g['status']=='PASS' for g in groups) and not any(x['scenario_ids'] or x['record_hashes'] or not x['raw_hash_comparison_available'] for x in overlaps.values())
    def installed(name):
        try: return version(name)
        except PackageNotFoundError: return None
    summary={'environment':{'python':sys.executable,'version':platform.python_version(),'pyarrow':installed('pyarrow'),'pandas':installed('pandas')},
             'sampling':'DETERMINISTIC_SPREAD_WOMD_SHARDS_FIRST_RECORDS_NOT_RANDOM',
             'status':'BOUNDED_LABEL_SMOKE_PASS' if ok else 'NOT_PASSED','scope':'FACTUAL_PATH_SURROGATE_AND_AUX_SIGNAL_ONLY',
             'records_requested_per_split':a.max_records,'prefix_steps':a.prefix_steps,'groups':groups,'sample_overlap_only':overlaps,
             'full_dataset_deduplication':False,'geometry_occupancy_generated':False,'proof_labels_generated':False,'training_complete':False}
    a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(summary,indent=2,ensure_ascii=False)+'\n')
    print(summary['status'],a.output)
    return 0 if ok else 3 if any(g['status']=='SKIP' for g in groups) and not any(g['status']=='ERROR' for g in groups) else 4

if __name__=='__main__':raise SystemExit(main())
