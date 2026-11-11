#!/usr/bin/env python3
"""Small finite information-state game demo; not a vehicle safety experiment."""
import argparse, json
from pathlib import Path
from rampd_core import (Interval, StateBounds, SupportAtom, BeliefCell,
    SafeDomain, ActionWitness, AtomTransition, ObservationSuccessors,
    EvidenceVerdict, compute_information_invariant,
    save_invariant_certificate, replay_invariant_certificate)


def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--output',type=Path,default=Path('reports/phase2_demo.json'))
    ap.add_argument('--certificate',type=Path,default=Path('reports/phase2_demo_certificate.json'))
    a=ap.parse_args()
    def state(px):
        return StateBounds(Interval(*px),Interval(-1,1),Interval(-.1,.1),
            Interval(0,10),Interval(-2,2),Interval(-.2,.2))
    def atom(i,px): return SupportAtom(i,state(px),(),(('protocol','open'),('monitor','ok')))
    l0,l1=atom('l0',(0,.5)),atom('l1',(.5,1))
    L=BeliefCell('L',(l0,l1),(
        ActionWitness('hold',(0.,0.),(
            AtomTransition('l0',EvidenceVerdict.PROVED,'demo-l0',(ObservationSuccessors('stay',(l0,)),)),
            AtomTransition('l1',EvidenceVerdict.PROVED,'demo-l1',(ObservationSuccessors('stay',(l1,)),)))),))
    a0,a1=atom('a0',(2,2.5)),atom('a1',(2.5,3))
    A=BeliefCell('A',(a0,a1),(
        ActionWitness('yield',(-1.,0.),(
            AtomTransition('a0',EvidenceVerdict.PROVED,'demo-a0',(ObservationSuccessors('yielded',(l0,)),)),
            AtomTransition('a1',EvidenceVerdict.PROVED,'demo-a1',(ObservationSuccessors('yielded',(l1,)),)))),))
    safe=SafeDomain(StateBounds(Interval(-10,10),Interval(-10,10),Interval(-1,1),
        Interval(0,20),Interval(-5,5),Interval(-.5,.5)),
        allowed_modes=(('protocol',('open',)),('monitor',('ok',))),
        required_mode_fields=('protocol','monitor'))
    # Explicit finite fixture verifier. Production must replace this with the
    # Phase 4 evidence verifier for full protocol/tube/resource proof artifacts.
    verifier=lambda context: bool(context.evidence_ref and context.evidence_ref.startswith('demo-'))
    result=compute_information_invariant((A,L),safe,verifier)
    save_invariant_certificate(a.certificate,(A,L),safe,result)
    replay=replay_invariant_certificate(a.certificate,verifier)
    payload={'classification':'finite_abstract_game_demo_not_vehicle_safety_experiment',
        'status':result.status,'retained_cell_ids':list(result.retained_cell_ids),
        'iterations':result.iterations,'removals_per_iteration':list(result.removals_per_iteration),
        'certificate_replay':replay.ok,'assurance_scope':result.assurance_scope,
        'certified':result.certified,'certificate':str(a.certificate)}
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(payload,indent=2)+'\n')
    print(json.dumps(payload,indent=2))
    if not replay.ok or result.retained_cell_ids != ('A','L'): raise SystemExit(2)
if __name__=='__main__': main()
