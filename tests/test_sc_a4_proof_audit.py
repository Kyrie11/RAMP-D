"""A4 mathematical hardening, executed against the real MPFR core on server."""
from dataclasses import replace
from fractions import Fraction as Q
import pytest

from rampd_core import (Interval, StateBounds, SupportAtom, BeliefCell,
    SafeDomain, EvidenceVerdict, AtomTransition, ObservationSuccessors,
    ActionWitness, SCContract, TerminalTailCertificate, compute_sc_inner,
    start_sc_execution, advance_sc_execution, replan_sc_execution,
    SCExecutionError, audit_sc_proof)


def fixture(*, parent_x=0, tail_time=Q(1)):
    ctx=SCContract('protocol-v1','clock-v1','vehicle-v1','task-v1',Q(1,10),1)
    g=SupportAtom('g',StateBounds.point([1,0,0,0,0,0]))
    a=SupportAtom('a',StateBounds.point([parent_x,0,0,0,0,0]))
    tr=AtomTransition('a',EvidenceVerdict.PROVED,'tube:1',
                      (ObservationSuccessors('visible',(g,)),))
    action=ActionWitness('move',(0.,0.),(tr,))
    cells=(BeliefCell('A',(a,),(action,)), BeliefCell('G',(g,)))
    d=SafeDomain(StateBounds(*(Interval(-10,10) for _ in range(6))))
    tail=TerminalTailCertificate('G','finishing-law','tail:1',tail_time,
                                 ctx.protocol_digest,ctx.clock_digest,
                                 ctx.model_digest,ctx.task_digest)
    callbacks={'evidence_replayer':lambda ev,c: ev.evidence_ref=='tube:1',
               'branch_cover_replayer':lambda cell,act,c: act.action_id=='move',
               'terminal_replayer':lambda cell,ta,c: ta.evidence_ref=='tail:1'}
    proof=compute_sc_inner(cells,d,ctx,(tail,),**callbacks)
    return proof,cells,d,ctx,tail,callbacks


def audit(values, **override):
    proof,cells,d,ctx,tail,callbacks=values
    callbacks={**callbacks,**override}
    return audit_sc_proof(proof,cells,d,ctx,(tail,),**callbacks)


def test_independent_structural_checker_and_exact_times():
    values=fixture()
    proof=values[0]
    result=audit(values)
    assert result.ok and result.conditional_only and not result.full_support_certified
    assert result.checked_actions==1 and result.checked_cells==2
    assert proof.ranks=={'A':1,'G':0}
    assert proof.completion_upper_s['A']==Q(11,10)
    assert proof.step_s==Q(1,10)


def test_independent_checker_rejects_forged_ranks_and_completion():
    v=fixture(); proof=v[0]
    for altered in (
        replace(proof, rank_pairs=(('A',0),('G',0))),
        replace(proof, completion_upper_pairs=(('A',Q(1)),('G',Q(1)))),
        replace(proof, step_s=Q(1,5)),
        replace(proof, family_by_rank=(('G',),('G',))),
    ):
        assert not audit((altered,*v[1:])).ok


def test_independent_checker_rejects_forged_branch_and_support():
    v=fixture(); proof=v[0]; step=proof.policy_steps[0]
    cases=(replace(proof, policy_steps=(replace(step,observation_children=(('other','G'),)),)),
           replace(proof, policy_steps=(replace(step,action_id='unknown'),)),
           replace(proof, support_digest_pairs=(('A','fake'),('G','fake'))))
    for altered in cases:
        assert not audit((altered,*v[1:])).ok
    assert not audit(v,evidence_replayer=None).ok
    assert not audit(v,branch_cover_replayer=None).ok
    assert not audit(v,terminal_replayer=None).ok


def test_replan_rejects_different_physical_support_same_cell_id():
    old=fixture()
    new=fixture(parent_x=Q(1,10))
    assert old[0].contract_digest==new[0].contract_digest
    assert old[0].support_digests['A']!=new[0].support_digests['A']
    inherited=start_sc_execution(old[0],'A')
    with pytest.raises(SCExecutionError,match='INFORMATION_SUPPORT_CHANGED'):
        replan_sc_execution(new[0],inherited)
    with pytest.raises(SCExecutionError,match='SUPPORT_CONTEXT_CHANGED'):
        advance_sc_execution(new[0],inherited,'visible','G')


def test_replan_cannot_silently_extend_promised_completion_time():
    old=fixture(tail_time=Q(1))
    new=fixture(tail_time=Q(100))
    inherited=start_sc_execution(old[0],'A')
    assert old[0].support_digests==new[0].support_digests
    with pytest.raises(SCExecutionError, match='COMPLETION_BOUND_EXCEEDS'):
        replan_sc_execution(new[0],inherited)
    normal=replan_sc_execution(old[0],inherited)
    after=advance_sc_execution(old[0],normal,'visible','G')
    assert after.remaining_rank==0
    assert after.remaining_completion_s==Q(1)


def test_missing_rank_budget_must_not_be_interpreted_as_certificate():
    v=fixture(); proof=v[0]
    budget=start_sc_execution(proof,'A')
    with pytest.raises(SCExecutionError):
        advance_sc_execution(proof,replace(budget,remaining_completion_s=None),'visible','G')


def test_certified_rational_inputs_reject_implicit_float_conversion():
    with pytest.raises(TypeError):
        SCContract('a','b','c','d',0.1,1)
    old=fixture()
    tail=old[4]
    with pytest.raises(TypeError):
        replace(tail,max_tail_s=0.1)
