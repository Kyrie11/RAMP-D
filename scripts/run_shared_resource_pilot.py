#!/usr/bin/env python3
"""Run a bounded declared 2-D benchmark and optional isolated head experiments."""
import argparse,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'python'))
from rampd_core.datasets.shared_resource_scenario import simulate,audit
from rampd_core.datasets.shared_resource_labels import release

def main():
    p=argparse.ArgumentParser();p.add_argument('--output',required=True);p.add_argument('--families',type=int,default=8);p.add_argument('--train-heads',action='store_true');a=p.parse_args()
    if not 4<=a.families<=9:p.error('4–9 distinct spacing families')
    out=Path(a.output);out.mkdir(parents=True,exist_ok=False);train=[];val=[];summary=[]
    with (out/'runs.jsonl').open('w') as f:
        for seed in range(a.families):
            # Two separate interventions: same initial state, ego wait or command ACK delay.
            base=simulate(seed=seed);aa=simulate(seed=seed);b=simulate(seed=seed,ego_wait_ticks=12);delayed=simulate(seed=seed,ack_delay_ticks=3)
            for name,r in [('A',base),('B',b),('DELAYED_ACK',delayed)]:
                c=audit(r);assert c['ok'],c
                target=train if seed<a.families-2 else val;target.extend(release(r,split='training' if seed<a.families-2 else 'validation'))
                summary.append(dict(family=r['family_id'],variant=name,aa_equal=base==aa,audit=c,ego_entry_tick=next(fr['tick'] for fr in r['frames'] if fr['contact_spans']['e'] is not None),other_entry_tick=next(fr['tick'] for fr in r['frames'] if fr['contact_spans']['b'] is not None)))
                f.write(json.dumps(r,allow_nan=False)+'\n')
    with (out/'labels.jsonl').open('w') as f:
        for r in train+val:f.write(json.dumps(r,allow_nan=False)+'\n')
    report=dict(scope='DECLARED_AFFINE_SHARED_RESOURCE_NOT_PHYSICAL_SIMULATOR',families=a.families,training_families=a.families-2,validation_families=2,runs=summary,heads=[])
    if a.train_heads:
        import torch
        from rampd_core.learning.resource_pilot import fit_head
        torch.set_num_threads(2)
        for h in ('event','occupancy','observation'):
            m,r=fit_head(train,val,h);torch.save(m.state_dict(),out/(h+'.pt'));report['heads'].append(r)
    (out/'summary.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n');print(json.dumps({k:v for k,v in report.items() if k!='runs'}))
if __name__=='__main__':main()
