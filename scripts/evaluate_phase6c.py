#!/usr/bin/env python3
"""Phase 6C bounded real data gate (train+validation; no training yet)."""
import argparse
import json
from pathlib import Path

from rampd_core.record_adapters import (iter_womd_split, iter_av2_split,
                                        OptionalDependencyError)
from rampd_core.supervision_inventory import supervision_inventory
from rampd_core.phase6c import (ForecastJob, constant_velocity_proposals,
                                offline_forecast_metrics, stable_split_fingerprint)


def one_split(dataset, split, iterator):
    """Evaluate a bounded sample without losing earlier rows on one failure.

    A successfully parsed scene is recorded even when a later one fails. Such
    failures always make the split ERROR, not a deceptively partial PASS.
    """
    rows, keys, failures = [], [], []
    try:
        for parsed in iterator:
            scene = parsed.scene
            key = (scene.manifest.dataset, scene.manifest.split, parsed.scenario_id)
            keys.append(key)
            try:
                job = ForecastJob.from_scene(scene)
                # The model is history-only, hence horizon length is an
                # experiment config (not read from future state contents).
                # For this bounded dataset gate the known benchmark horizon
                # is requested explicitly; no future positions are inputs.
                future_steps = len(scene.manifest.timestamps)-1-scene.manifest.current_time_index
                sets = constant_velocity_proposals(job, horizon_steps=future_steps,
                                                  include_sdc=True) if future_steps > 0 else ()
                target_ids = {t.track_id for t in scene.tracks if t.to_predict}
                scored = tuple(p for p in sets if p.actor_id in target_ids)
                metrics = (offline_forecast_metrics(scene, scored)
                           if split in ("validation", "training", "train") else None)
                rows.append({"scenario_id":parsed.scenario_id,
                             "source_file":parsed.source_file,
                             "record_index":parsed.record_index,
                             "content_sha256":parsed.content_sha256,
                             "record_sha256":parsed.record_sha256,
                             "source_file_sha256":parsed.source_file_sha256,
                             "scenario_content_sha256":parsed.scenario_content_sha256,
                             "source_schema":parsed.source_schema,
                             "parser_version":parsed.parser_version,
                             "map_file":parsed.map_file,
                             "map_content_sha256":parsed.map_content_sha256,
                             "supervision_inventory":supervision_inventory(scene),
                             "num_tracks":len(scene.tracks),
                             "to_predict_count":len(target_ids),
                             "sdc_ids":[t.track_id for t in scene.tracks if t.is_sdc],
                             "prediction_proposals":sum(len(x.proposals) for x in scored),
                             "scoreable_future_rows":0 if metrics is None else metrics["count"],
                             "logged_action_metrics":None if metrics is None else metrics["rows"][:10],
                             "mean_ade_m":(None if metrics is None or not metrics["rows"]
                                           else sum(x["ade_m"] for x in metrics["rows"])
                                                /len(metrics["rows"])),
                             "max_slot_offset_s":(None if metrics is None or not metrics["rows"]
                                                 else max(x["max_slot_offset_s"] for x in metrics["rows"]))})
            except Exception as exc:
                failures.append({"scenario_id": parsed.scenario_id,
                                 "source_file": parsed.source_file,
                                 "failure_type": type(exc).__name__,
                                 "reason": str(exc), "stage":"forecast_or_metric"})
    except (FileNotFoundError, OptionalDependencyError) as exc:
        if rows or failures:
            failures.append({"failure_type": type(exc).__name__,
                             "reason": str(exc), "stage": "dataset_iterator"})
        else:
            return {"status":"SKIP", "reason":f"{type(exc).__name__}: {exc}",
                    "samples":[], "failure_cases":[]}, set()
    except Exception as exc:
        failures.append({"failure_type": type(exc).__name__,
                         "reason": str(exc), "stage":"dataset_iterator"})
    ids=set(x[2] for x in keys)
    if len(keys) != len(ids):
        failures.append({"failure_type":"DuplicateScenarioID",
                         "reason":"repeated (dataset,split,scenario_id) in bounded sample",
                         "stage":"identity"})
    sample_ids=sorted(ids)
    if failures:
        return {"status":"ERROR", "reason":"SCENE_OR_ITERATOR_FAILURE",
                "samples":rows, "failure_cases":failures,
                "sample_ids":sample_ids},ids
    if not rows:
        return {"status":"SKIP", "reason":"NO_ROWS", "samples":[],
                "failure_cases":[]},ids
    if not any(row["scoreable_future_rows"] > 0 for row in rows):
        return {"status":"SKIP", "reason":"NO_SCOREABLE_FUTURE_TARGETS",
                "samples":rows, "failure_cases":[]},ids
    return {"status":"PASS", "reason":None, "samples":rows,
            "failure_cases":[],
            "sample_fingerprint":stable_split_fingerprint(keys)},ids


def main():
    arg = argparse.ArgumentParser()
    arg.add_argument('--womd-root',type=Path,required=True)
    arg.add_argument('--av2-root',type=Path,required=True)
    arg.add_argument('--max-records',type=int,default=2)
    arg.add_argument('--output',type=Path,required=True)
    a=arg.parse_args()
    if not 1<=a.max_records<=100: arg.error('max-records must be 1..100')
    result={"schema":"rampd.phase6c.dataset-gate.v1", "phase":"6C",
            "supervision":"logged_action_motion_only", "full_support_certified":False,
            "untrained_prediction_baseline":True, "split_overlap_check":"bounded_sample_only",
            "dataset_root_womd":str(a.womd_root), "dataset_root_av2":str(a.av2_root)}
    all_keys={}
    for dataset,reader,root,train_split in (
            ('womd', iter_womd_split,a.womd_root,'training'),
            ('av2',iter_av2_split,a.av2_root,'train')):
        for split in ('validation',train_split):
            status, ids = one_split(dataset,split,reader(root,split=split,max_records=a.max_records))
            key=f'{dataset}_{split}'
            result[key]=status
            all_keys[key]=ids
    overlap={name:sorted(all_keys.get(f'{name}_validation',set()) & all_keys.get(f'{name}_{train}',set()))
             for name,train in [('womd','training'),('av2','train')]}
    result['sample_split_id_overlap']=overlap
    statuses=[result[k]['status'] for k in ('womd_validation','womd_training','av2_validation','av2_train')]
    if any(overlap.values()) or 'ERROR' in statuses:
        result['status']='ERROR'
    elif all(s=='PASS' for s in statuses):
        result['status']='PASS'
    else:
        result['status']='SKIP'
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
    print(json.dumps({k:v if k=='status' else (v.get('status') if isinstance(v,dict) else v)
                      for k,v in result.items() if k in ('status','womd_validation','womd_training','av2_validation','av2_train')}, indent=2))
    return 0 if result['status']=='PASS' else 2


if __name__=='__main__':
    raise SystemExit(main())
