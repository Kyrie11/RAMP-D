#!/usr/bin/env python3
"""Finite abstract predecessor/fixed-point microbenchmark (not physical validation)."""
import argparse, json, time
from pathlib import Path
from rampd_core import (Interval, StateBounds, SupportAtom, BeliefCell, SafeDomain,
    ActionWitness, AtomTransition, ObservationSuccessors, EvidenceVerdict,
    compute_information_invariant)


def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--sizes',default='50,100,250,500')
    ap.add_argument('--output',type=Path,default=Path('reports/phase2_benchmark.json'))
    args=ap.parse_args(); rows=[]
    safe=SafeDomain(StateBounds(Interval(-1,10000),Interval(-1,1),Interval(-.2,.2),
        Interval(0,10),Interval(-2,2),Interval(-.3,.3)),
        allowed_modes=(('protocol',('open',)),('monitor',('ok',))),
        required_mode_fields=('protocol','monitor'))
    for n in map(int,args.sizes.split(',')):
        cells=[]
        for i in range(n):
            atom=SupportAtom(f'a{i}',StateBounds(Interval(i,i+.01),Interval(0,0),
                Interval(0,0),Interval(1,1),Interval(0,0),Interval(0,0)),(),
                (('protocol','open'),('monitor','ok')))
            action=ActionWitness('hold',(0.,0.),(AtomTransition(atom.atom_id,
                EvidenceVerdict.PROVED,f'e{i}',(ObservationSuccessors('same',(atom,)),)),))
            cells.append(BeliefCell(f'B{i}',(atom,),(action,)))
        t=time.perf_counter()
        result=compute_information_invariant(cells,safe,
            lambda context: bool(context.evidence_ref and context.evidence_ref.startswith('e')))
        elapsed=time.perf_counter()-t
        rows.append({'cells':n,'retained':len(result.retained_cell_ids),
            'iterations':result.iterations,'removals':list(result.removals_per_iteration),
            'seconds':elapsed,'status':result.status,
            'classification':'finite_abstract_game_microbenchmark_not_vehicle_experiment'})
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps({'benchmark':'phase2_finite_information_invariant',
        'rows':rows},indent=2)+'\n')
    print(json.dumps({'rows':rows},indent=2))
    if any(r['retained']!=r['cells'] or r['status']!='FIXPOINT_CONVERGED' for r in rows): raise SystemExit(2)
if __name__=='__main__': main()
