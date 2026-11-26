#!/usr/bin/env python3
"""Bounded official-directory audit and streaming feature preparation."""
import argparse,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'python'))
from rampd_core.datasets.split_manifest import build_manifest,extend_training_manifest
from rampd_core.datasets.factual_dataset import prepare

def main():
    p=argparse.ArgumentParser(); p.add_argument('--scenario-root',required=True);p.add_argument('--base-manifest');p.add_argument('--output',required=True);p.add_argument('--train-limit',type=int,default=5);p.add_argument('--validation-limit',type=int,default=5);p.add_argument('--max-shards',type=int,default=2);p.add_argument('--horizon',type=int,default=10);p.add_argument('--history-steps',type=int,default=11);p.add_argument('--max-agents',type=int,default=128);p.add_argument('--max-map',type=int,default=256);a=p.parse_args()
    if max(a.train_limit,a.validation_limit)>1000: p.error('pilot maximum 1000 scenes per split')
    if a.base_manifest:
        base=json.loads(Path(a.base_manifest).read_text())
        if Path(base['root']).resolve()!=Path(a.scenario_root).resolve():p.error('base manifest root mismatch')
        if sum(r['split']=='validation' for r in base['records'])!=a.validation_limit:p.error('validation-limit must equal base validation roster')
        m=extend_training_manifest(base,train_limit=a.train_limit,max_shards=a.max_shards)
    else:m=build_manifest(a.scenario_root,train_limit=a.train_limit,validation_limit=a.validation_limit,max_shards=a.max_shards)
    s=prepare(m,a.output,horizon=a.horizon,history_steps=a.history_steps,max_agents=a.max_agents,max_map=a.max_map)
    print(json.dumps(dict(status='PILOT_FEATURES_READY',accepted=len(s['accepted']),rejected=len(s['rejected']),scope=s['scope'])))
if __name__=='__main__': main()
