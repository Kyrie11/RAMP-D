#!/usr/bin/env python3
"""Build split-scoped factual rows. Inputs are inventory files, not raw protobuf.
Source record bytes must be audited at ingestion; IDs are unique in this batch.
"""
import argparse,json,sys,types
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'python'));p=types.ModuleType('rampd_core');p.__path__=[str(ROOT/'python'/'rampd_core')];sys.modules['rampd_core']=p
from rampd_core.scoped_factual_labels import batch

def main():
    p=argparse.ArgumentParser();p.add_argument('--inventory',type=Path,nargs='+',required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--split-manifest',type=Path);a=p.parse_args()
    records=[]
    for f in a.inventory:
        d=json.loads(f.read_text())
        if d['status']!='DESCRIPTIVE_UNMODIFIED_SCENARIO_PROTO_INVENTORY':raise ValueError('inventory status')
        records.extend(d['records'])
    rows=batch(records,split_manifest=json.loads(a.split_manifest.read_text()) if a.split_manifest else None);a.output.parent.mkdir(parents=True,exist_ok=True)
    with a.output.open('x') as f:
        for r in rows:f.write(json.dumps(r,allow_nan=False)+'\n')
    print('rows',len(rows),'train',sum(r['heads']['joint']['training_allowed'] for r in rows),'sc certified',False)
if __name__=='__main__':main()
