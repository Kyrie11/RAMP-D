#!/usr/bin/env python3
"""Run a bounded declared 2-D benchmark and optional isolated head experiments."""
import argparse,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'python'))
from rampd_core.datasets.shared_resource_scenario import simulate,audit
from rampd_core.datasets.shared_resource_labels import release

def main():
    p=argparse.ArgumentParser();p.add_argument('--output',required=True);p.add_argument('--families',type=int,default=8);p.add_argument('--train-heads',action='store_true');p.add_argument('--transition-heads',action='store_true');p.add_argument('--horizon',type=int,default=8);p.add_argument('--finite-teacher',action='store_true');p.add_argument('--protocol-shift',action='store_true',help='holdout green/clearance/ACK parameters; no model update');p.add_argument('--heterogeneous',action='store_true',help='additional declared delayed-release variants');a=p.parse_args()
    if not 4<=a.families<=9:p.error('4–9 distinct spacing families')
    if a.protocol_shift and not a.transition_heads:p.error('protocol shift requires transition heads')
    out=Path(a.output);out.mkdir(parents=True,exist_ok=False);train=[];val=[];summary=[];tr_transition=[];va_transition=[]
    with (out/'runs.jsonl').open('w') as f:
        for seed in range(a.families):
            # Two separate interventions: same initial state, ego wait or command ACK delay.
            base=simulate(seed=seed);aa=simulate(seed=seed);b=simulate(seed=seed,ego_wait_ticks=12);delayed=simulate(seed=seed,ack_delay_ticks=3)
            variants=[('A',base),('B',b),('DELAYED_ACK',delayed)]
            if a.heterogeneous:variants.append(('HETEROGENEOUS_RELEASE',simulate(seed=seed,release_delays={'e':3,'a':0,'b':2,'c':1})))
            for name,r in variants:
                c=audit(r);assert c['ok'],c
                target=train if seed<a.families-2 else val;target.extend(release(r,split='training' if seed<a.families-2 else 'validation'))
                if a.transition_heads:
                    from rampd_core.datasets.shared_resource_labels import transition_rows
                    (tr_transition if seed<a.families-2 else va_transition).extend(transition_rows(r,split='training' if seed<a.families-2 else 'validation',horizon=a.horizon))
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
    if a.transition_heads:
        import torch
        from rampd_core.learning.resource_pilot import fit_transition_head
        torch.set_num_threads(2);report['transition_heads']=[]
        with (out/'transition_labels.jsonl').open('w') as f:
            for row in tr_transition+va_transition:f.write(json.dumps(row,allow_nan=False)+'\n')
        shifted=[]
        if a.protocol_shift:
            from rampd_core.datasets.shared_resource_labels import transition_rows
            with (out/'protocol_shift_runs.jsonl').open('w') as f:
                for seed in range(a.families-2,a.families):
                    for green in (12,24):
                        run=simulate(seed=seed,green_ticks=green,clearance_ticks=3,ack_delay_ticks=2,release_delays={'e':3,'a':0,'b':2,'c':1});shifted.extend(transition_rows(run,split='validation',horizon=a.horizon));f.write(json.dumps(run,allow_nan=False)+'\n')
            report['protocol_shift_heads']=[]
        for h in ('event','occupancy','observation'):
            for context in (False,True):
                m,r=fit_transition_head(tr_transition,va_transition,h,context=context);torch.save(m.state_dict(),out/(h+'_transition_'+str(context)+'.pt'));report['transition_heads'].append(r)
                if shifted:
                    _,q=fit_transition_head(tr_transition,shifted,h,context=context,epochs=0,frozen_model=m);report['protocol_shift_heads'].append(q)
    if a.finite_teacher:
        from rampd_core.finite_wait_reference import finite_teacher
        teacher=[finite_teacher(o,14) for o in ((4,6),(5,7),(6,8))]
        (out/'finite_teacher.json').write_text(json.dumps(teacher,indent=2,allow_nan=False)+'\n');report['finite_teacher_scope']='FINITE_WAIT_GO_ONLY'
    (out/'summary.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n');print(json.dumps({k:v for k,v in report.items() if k!='runs'}))
if __name__=='__main__':main()
