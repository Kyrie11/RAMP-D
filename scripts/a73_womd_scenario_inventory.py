#!/usr/bin/env python3
import argparse,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'python'))

def main():
    p=argparse.ArgumentParser();p.add_argument('--scenario-file',type=Path,required=True);p.add_argument('--split',choices=('training','validation'),required=True);p.add_argument('--max-records',type=int,default=5);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    if a.output.exists() or not 1<=a.max_records<=50:raise SystemExit('new output and 1..50 records required')
    result=dict(status='REVIEW',records=[],formal_labels_authorized=False,counterfactual_response_proved=False)
    try:
        from rampd_core.record_adapters import iter_womd_scenario_file
        seen=set()
        for s in iter_womd_scenario_file(a.scenario_file,max_records=a.max_records,hash_source_file=False,split=a.split):
            if not s.scenario_id or s.scenario_id in seen or not s.record_sha256:raise ValueError('missing or duplicate source identity')
            seen.add(s.scenario_id);result['records'].append(s.to_dict())
        if not seen:raise ValueError('empty scenario source')
        result['status']='DESCRIPTIVE_UNMODIFIED_SCENARIO_PROTO_INVENTORY';result['split_declared']=a.split
    except Exception as e:result['reason']=f'{type(e).__name__}: {e}'
    a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(result,ensure_ascii=False,allow_nan=False)+'\n');print(result['status']);return 0 if result['status'].startswith('DESCRIPTIVE') else 4
if __name__=='__main__':raise SystemExit(main())
