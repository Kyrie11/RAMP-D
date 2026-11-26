#!/usr/bin/env python3
"""Bind A74 sampled occupancy to raw A73 net/actor trace, never promote it
into continuous shared-lane truth. Each row is validation-only by default.
"""
import argparse,json,hashlib
from pathlib import Path
from sumo_sampled_replay import audit

def main():
    p=argparse.ArgumentParser();p.add_argument('--work',type=Path,required=True);p.add_argument('--prior-rows',type=Path,required=True);p.add_argument('--output-dir',type=Path,required=True);a=p.parse_args();r,rows=audit(a.work);prior=[json.loads(x) for x in a.prior_rows.read_text().splitlines()]
    if r['errors'] or rows!=prior or len(rows)!=r['ticks']:raise ValueError('raw source/previous result mismatch')
    source=hashlib.sha256((a.work/'metric_actor_trace.jsonl').read_bytes()).hexdigest();a.output_dir.mkdir(parents=True,exist_ok=False)
    heads=('event','joint','occupancy','observation','viability','margin','deadline','causal')
    with (a.output_dir/'sampled_labels.jsonl').open('x') as f:
        for row in rows:
            mask={h:False for h in heads};mask['occupancy']=True
            f.write(json.dumps(dict(domain='SUMO_SAMPLED_TWO_STRIP_LOGICAL_RESOURCE',source_sha256=source,network_sha256=r['net_sha256'],split='evaluation_only',training_allowed=False,field_masks=dict(sampled_contact=True,sampled_transition=True,continuous_occupancy=False,continuous_entry_exit_time=False,physical_ack=False),heads=mask,label=row))+'\n')
    (a.output_dir/'review.json').write_text(json.dumps(dict(rows=len(rows),raw_replay=r,train_rows=0,formal_sc=False),indent=2)+'\n')
    print('sampled validation rows',len(rows))
if __name__=='__main__':main()
