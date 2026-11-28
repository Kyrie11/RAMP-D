#!/usr/bin/env python3
"""Bounded family/protocol holdout, independently trained heads and typed query ablation."""
import argparse,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'python'))
from rampd_core.datasets.shared_resource_scenario import simulate
from rampd_core.datasets.shared_resource_labels import relation_rows
from rampd_core.learning.resource_pilot import fit_relation_head

def main():
    p=argparse.ArgumentParser();p.add_argument('--output',default='reports/phase7bc_relation/relation_pilot');p.add_argument('--epochs',type=int,default=15);p.add_argument('--seed',type=int,default=7);p.add_argument('--variants',nargs='+',choices=['flat','uniform','gated'],default=['flat','uniform','gated']);p.add_argument('--heads',nargs='+',choices=['event','occupancy','observation','start'],default=['event','occupancy','observation','start']);p.add_argument('--hide-protocol',action='store_true');p.add_argument('--drop-source',choices=['neighbor','resource','rule','information']);a=p.parse_args()
    if not 1<=a.epochs<=100:p.error('epochs')
    import torch
    torch.set_num_threads(2);out=Path(a.output);out.mkdir(parents=True,exist_ok=False);train=[];ev={'matched':[],'shift':[]};runs=[]
    for family in range(9):
        for green,clear in ((12,2),(16,3),(20,2)) if family<6 else ((12,2),(16,3),(20,2),(24,4)):
            for wait,ack,delay in [(0,1,None),(12,3,{'e':3,'a':0,'b':2,'c':1})]:
                run=simulate(seed=family,green_ticks=green,clearance_ticks=clear,ego_wait_ticks=wait,ack_delay_ticks=ack,release_delays=delay)
                target=train if family<6 else ev['shift' if green==24 else 'matched'];split='training' if family<6 else 'validation';rows=relation_rows(run,split=split,public_protocol=not a.hide_protocol)
                if a.drop_source:
                    from rampd_core.learning.relation_context import SOURCES
                    from rampd_core.datasets.split_manifest import canonical_digest
                    j=SOURCES.index(a.drop_source)
                    for row in rows:
                        for t,m in zip(row['tokens'],row['available']):t[j]=[0.]*6;m[j]=False
                        row['digest']=canonical_digest({k:v for k,v in row.items() if k!='digest'})
                target.extend(rows);runs.append(run)
    with (out/'runs.jsonl').open('w') as f:
        for r in runs:f.write(json.dumps(r,allow_nan=False)+'\n')
    with (out/'labels.jsonl').open('w') as f:
        for r in train+ev['matched']+ev['shift']:f.write(json.dumps(r,allow_nan=False)+'\n')
    reports=[]
    for head in a.heads:
        for variant in a.variants:
            model,r=fit_relation_head(train,ev,head,variant=variant,epochs=a.epochs,seed=a.seed);torch.save(model.state_dict(),out/f'{head}_{variant}.pt');reports.append(r);print(head,variant,{k:(v['loss'],v.get('change_AP',v.get('positive_AP'))) for k,v in r['evaluations'].items()},flush=True)
    (out/'summary.json').write_text(json.dumps(dict(scope='DECLARED_RELATION_NOT_REAL_OR_FORMAL',runs=len(runs),public_protocol=not a.hide_protocol,drop_source=a.drop_source,training_rows=len(train),evaluation_rows={k:len(v) for k,v in ev.items()},training_families=list(range(6)),evaluation_families=list(range(6,9)),heads=reports),indent=2,allow_nan=False)+'\n')
if __name__=='__main__':main()
