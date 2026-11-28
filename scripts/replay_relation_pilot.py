#!/usr/bin/env python3
"""Re-evaluate saved weights with training-only baselines; no optimization."""
import argparse,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'python'))
from rampd_core.learning.resource_pilot import fit_relation_head
import torch

def main():
    p=argparse.ArgumentParser();p.add_argument('--run',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();torch.set_num_threads(2)
    report=json.loads((a.run/'summary.json').read_text());rows=[json.loads(l) for l in (a.run/'labels.jsonl').read_text().splitlines()];train=[r for r in rows if r['split']=='training'];v=[r for r in rows if r['split']=='validation'];n=report['evaluation_rows']['matched'];ev={'matched':v[:n],'shift':v[n:]}
    from rampd_core.datasets.shared_resource_labels import relation_rows
    from rampd_core.datasets.split_manifest import canonical_digest
    from rampd_core.learning.relation_context import SOURCES
    # Rebuild each labeled row from its own source run, not self-hashed labels.
    key=lambda r:(r['run_digest'],r['tick']);lookup={key(r):r for r in rows}
    if len(lookup)!=len(rows):raise ValueError('duplicate label key')
    seen=set()
    for run in map(json.loads,(a.run/'runs.jsonl').read_text().splitlines()):
        for row in relation_rows(run,split='training' if run['seed'] in report['training_families'] else 'validation',public_protocol=report.get('public_protocol',True)):
            if report.get('drop_source'):
                j=SOURCES.index(report['drop_source'])
                for t,m in zip(row['tokens'],row['available']):t[j]=[0.]*6;m[j]=False
                row['digest']=canonical_digest({k:v for k,v in row.items() if k!='digest'})
            k=key(row)
            if k in seen or lookup.get(k)!=row:raise ValueError('relation source label mismatch')
            seen.add(k)
    if seen!=set(lookup):raise ValueError('unbound relation labels')
    report['source_labels_rebuilt']=len(seen)
    for r in report['heads']:
        w=torch.load(a.run/f"{r['head']}_{r['variant']}.pt",map_location='cpu',weights_only=True)
        _,q=fit_relation_head(train,ev,r['head'],variant=r['variant'],seed=r['seed'],epochs=0,frozen_weights=w)
        for name,x in q['evaluations'].items():
            for key in ('loss','change_AP','positive_AP'):
                if key in x and abs(x[key]-r['evaluations'][name][key])>1e-6:raise ValueError('weight replay mismatch')
        r['initial']=q['initial'];r['evaluations']=q['evaluations'];r['weight_replay_match']=True
    a.output.parent.mkdir(parents=True,exist_ok=True)
    with a.output.open('x') as f:json.dump(report,f,indent=2,allow_nan=False)
if __name__=='__main__':main()
