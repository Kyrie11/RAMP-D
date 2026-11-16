"""Finite SC winning-set + rank tests. Requires built native interval backend."""
from dataclasses import replace
from fractions import Fraction as F

import pytest

from rampd_core.interval import Interval
from rampd_core.model import StateBounds
from rampd_core.belief import BeliefCell, SupportAtom
from rampd_core.invariant import (ActionWitness, AtomTransition, EvidenceVerdict,
                                  ObservationSuccessors, SafeDomain)
from rampd_core.safe_continuation import (
    SCContract, TerminalTailCertificate, TubeMarginCertificate,
    compute_sc_inner, replay_sc_inner, start_sc_execution, advance_sc_execution,
    replan_sc_execution, SCExecutionError,
)
from rampd_core.protocol import (ProtocolState, ProtocolTransition, ProtocolAutomaton,
                                 ClockTrace, TimeWindow, CausalStage,
                                 build_coverage_ledger)


def _support(name, x, mode=()):
    return SupportAtom(name, StateBounds.point([x, 0, 0, 0, 0, 0]), mode=mode)


def _act(name, observation_targets):
    # observation_targets maps each source atom id to a mapping obs->successors
    trans = []
    for atom_id, branches in observation_targets.items():
        trans.append(AtomTransition(atom_id, EvidenceVerdict.PROVED,
                                    'tube:' + name + ':' + atom_id,
                                    tuple(ObservationSuccessors(o, tuple(atoms))
                                          for o, atoms in branches.items())))
    return ActionWitness(name, (0, 0), tuple(trans))


def _domain():
    return SafeDomain(StateBounds(Interval(-10, 10), Interval(-10, 10),
                                  Interval(-10, 10), Interval(-10, 10),
                                  Interval(-10, 10), Interval(-10, 10)))


def _contract(horizon=3, protocol='protocol:p'):
    return SCContract(protocol, 'clock:c', 'model:m', 'task:F_T', F('1/10'), horizon)


def _tail(cid='G', ctx=None, margin=F('3/5')):
    ctx = ctx or _contract()
    return TerminalTailCertificate(cid, 'policy:task-acceptance', 'evidence:tail', F(2),
                                   ctx.protocol_digest, ctx.clock_digest,
                                   ctx.model_digest, ctx.task_digest, margin)


def _fixture():
    g = _support('g', 2)
    c = _support('c', 1)
    b = _support('b', 0)
    isolated = _support('isolated', 4)
    terminal = BeliefCell('G', (g,))
    intermediate = BeliefCell('C', (c,), (_act('go-G', {'c': {'seen': (g,)}}),))
    # A safe wait self-loop must not contribute to task-completion rank.
    start = BeliefCell('B', (b,),
                       (_act('a-wait', {'b': {'seen': (b,)}}),
                        _act('z-go-C', {'b': {'seen': (c,)}})))
    disconnected = BeliefCell('R', (isolated,), (_act('a-wait', {'isolated': {'seen': (isolated,)}}),))
    return (start, intermediate, terminal, disconnected)


def _replay_evidence(ctx, contract):
    return ctx.evidence_ref.startswith('tube:') and contract.protocol_digest == 'protocol:p'


def _replay_branch_cover(cell, action, ctx):
    # Synthetic fixture only: caller asserts the finite protocol has exactly
    # these observations with a verifiably disjoint observation partition.
    return bool(cell.atoms) and ctx.protocol_digest == 'protocol:p'


def _replay_terminal(cell, tail, ctx):
    return (tail.evidence_ref == 'evidence:tail' and tail.tail_policy_digest ==
            'policy:task-acceptance' and tail.bound_to(ctx) and cell.cell_id == 'G')


def _margin(cell_id, action, lower, ctx=None):
    ctx = ctx or _contract()
    return TubeMarginCertificate(cell_id, action, 'evidence:margin:' + action,
                                 ctx.digest, lower)


def _replay_margin(cell, action, certificate, ctx):
    return (certificate.cell_id == cell.cell_id and certificate.action_id == action.action_id
            and certificate.contract_digest == ctx.digest and
            certificate.evidence_ref == 'evidence:margin:' + action.action_id)


def _solve(cells=None, ctx=None, tails=None, **kw):
    ctx = ctx or _contract()
    cells = _fixture() if cells is None else cells
    tails = (_tail(ctx=ctx),) if tails is None else tails
    return compute_sc_inner(cells, _domain(), ctx, tails,
                            evidence_replayer=kw.pop('evidence_replayer', _replay_evidence),
                            branch_cover_replayer=kw.pop('branch_cover_replayer', _replay_branch_cover),
                            terminal_replayer=kw.pop('terminal_replayer', _replay_terminal), **kw)


def test_missing_coverage_ledger_export_is_restored():
    tr = ProtocolTransition('t', 's', 'z', (('change', CausalStage.EXTERNAL),),
                            ClockTrace(TimeWindow(F(0), F(0))), 'silence',
                            silence=True, guard_tag='always')
    automaton = ProtocolAutomaton((ProtocolState('s'), ProtocolState('z')),
                                 's', (tr,))
    ledger = build_coverage_ledger(automaton)
    assert ledger == automaton.coverage()
    assert ledger.missing_states == ('z',)
    with pytest.raises(TypeError):
        build_coverage_ledger('not an automaton')


def test_finite_rank_exact_time_and_noncompleting_wait_not_accepted():
    ctx = _contract()
    result = _solve(ctx=ctx)
    assert result.status == 'CONDITIONAL_FINITE_ABSTRACTION_ONLY'
    assert result.certified_full_support is False
    assert result.ranks == {'B': 2, 'C': 1, 'G': 0}
    assert 'R' not in result.ranks
    assert result.completion_upper_s == {'G': F(2), 'C': F('21/10'), 'B': F('22/10')}
    assert result.family_by_rank == (('G',), ('C', 'G'), ('B', 'C', 'G'), ('B', 'C', 'G'))
    parent = next(s for s in result.policy_steps if s.cell_id == 'B')
    assert parent.action_id == 'z-go-C'
    assert result.ranks[parent.observation_children[0][1]] == parent.rank - 1
    assert replay_sc_inner(result, _fixture(), _domain(), ctx, (_tail(ctx=ctx),),
                           evidence_replayer=_replay_evidence,
                           branch_cover_replayer=_replay_branch_cover,
                           terminal_replayer=_replay_terminal)


def test_horizon_does_not_reset_and_zero_horizon_only_tails():
    result = _solve(ctx=_contract(horizon=1))
    assert result.ranks == {'C': 1, 'G': 0}
    assert _solve(ctx=_contract(horizon=0)).ranks == {'G': 0}
    assert result.ranks['C'] != 0


def test_missing_terminal_or_evidence_prevents_winning_claim():
    assert not _solve(terminal_replayer=None).ranks
    assert not _solve(terminal_replayer=lambda *args: 1).ranks
    assert _solve(evidence_replayer=None).ranks == {'G': 0}
    assert _solve(branch_cover_replayer=None).ranks == {'G': 0}
    assert _solve(branch_cover_replayer=lambda *args: 1).ranks == {'G': 0}
    assert _solve(evidence_replayer=lambda *args: 1).ranks == {'G': 0}
    assert _solve(terminal_replayer=lambda *args: (_ for _ in ()).throw(RuntimeError())).ranks == {}
    assert _solve(tails=()).ranks == {}


def test_wrong_context_terminal_does_not_replay():
    stale = _tail(ctx=_contract(protocol='protocol:stale'))
    assert not _solve(tails=(stale,)).ranks
    ctx = _contract()
    solved = _solve(ctx=ctx)
    assert not replay_sc_inner(solved, _fixture(), _domain(), _contract(protocol='new'),
                               (_tail(ctx=_contract(protocol='new')),),
                               evidence_replayer=_replay_evidence,
                               branch_cover_replayer=_replay_branch_cover,
                               terminal_replayer=_replay_terminal)


def test_merged_observation_support_cannot_pick_hidden_atom_specific_child():
    g1, g2 = _support('g1', 3), _support('g2', 4)
    p1, p2 = _support('p1', 1), _support('p2', 2)
    parent = BeliefCell('P', (p1, p2),
                        (_act('common', {'p1': {'same_obs': (g1,)},
                                         'p2': {'same_obs': (g2,)}}),))
    g1_cell = BeliefCell('G1', (g1,))
    g2_cell = BeliefCell('G2', (g2,))
    # Even though each hidden state has a valid terminal on its own, the
    # single realized observation cannot select two different terminal laws.
    def verifier(c, tail, ctx): return True
    ctx = _contract(horizon=1)
    tails = [replace(_tail('G1', ctx=ctx), cell_id='G1'),
             replace(_tail('G2', ctx=ctx), cell_id='G2')]
    result = _solve(cells=(parent, g1_cell, g2_cell), ctx=ctx,
                    tails=tails, terminal_replayer=verifier)
    assert 'P' not in result.ranks
    # One single common-policy target covering both successors is sufficient.
    union_terminal = BeliefCell('GU', (g1, g2))
    union_result = _solve(cells=(parent, union_terminal), ctx=ctx,
                          tails=(replace(_tail(ctx=ctx), cell_id='GU'),),
                          terminal_replayer=verifier)
    assert union_result.ranks == {'GU': 0, 'P': 1}
    assert dict(union_result.policy_steps[0].observation_children) == {'same_obs': 'GU'}


def test_every_source_atom_needs_replayed_transition():
    p1, p2, g = _support('p1', 1), _support('p2', 2), _support('g', 3)
    parent = BeliefCell('P', (p1, p2), (_act('incomplete', {'p1': {'obs': (g,)}}),))
    terminal = BeliefCell('G', (g,))
    assert _solve(cells=(parent, terminal)).ranks == {'G': 0}
    full = replace(parent, actions=(_act('full', {'p1': {'obs': (g,)},
                                                   'p2': {'obs': (g,)}}),))
    assert _solve(cells=(full, terminal)).ranks == {'G': 0, 'P': 1}


def test_margin_lower_bounds_require_independent_replay_and_are_exact_rationals():
    ctx = _contract()
    margins = (_margin('C', 'go-G', F('1/2'), ctx),
               _margin('B', 'z-go-C', F('2/5'), ctx))
    unknown = _solve(ctx=ctx, margins=margins)
    assert unknown.margins_lower == {'G': F('3/5')}
    solved = _solve(ctx=ctx, margins=margins, margin_replayer=_replay_margin)
    assert solved.margins_lower == {'G': F('3/5'), 'C': F('1/2'), 'B': F('2/5')}
    stale = (_margin('C', 'go-G', F('1/2'), _contract(protocol='old')),
             margins[1])
    incomplete = _solve(ctx=ctx, margins=stale, margin_replayer=_replay_margin)
    assert incomplete.margins_lower == {'G': F('3/5')}
    assert F('2/5') not in incomplete.margins_lower.values()


def test_falsified_margin_or_unproved_action_does_not_create_positive_value():
    ctx = _contract()
    bogus = (_margin('C', 'go-G', 1, ctx),)
    result = _solve(ctx=ctx, margins=bogus, margin_replayer=lambda *args: False)
    assert 'C' not in result.margins_lower
    assert 'C' in result.ranks  # rank proof and margin proof are independent
    no_transition = _solve(ctx=ctx, evidence_replayer=lambda *args: False,
                           margins=bogus, margin_replayer=lambda *args: True)
    assert no_transition.ranks == {'G': 0}
    assert 'C' not in no_transition.margins_lower


def test_invalid_contexts_and_certificates_rejected():
    with pytest.raises(ValueError): _contract(horizon=-1)
    with pytest.raises(ValueError): SCContract('a','b','c','d', 0, 1)
    with pytest.raises(ValueError): SCContract('a','b','c','d', 1, True)
    with pytest.raises(ValueError): _tail(ctx=_contract(), margin=F('11/10'))
    with pytest.raises(ValueError): _margin('C','go-G', F('-1/10'))
    with pytest.raises(ValueError): _solve(tails=(_tail(), _tail()))
    with pytest.raises(ValueError):
        _solve(margins=(_margin('C','go-G',0), _margin('C','go-G',0)))


def test_excluded_unsafe_parent_does_not_gain_rank():
    ctx = _contract()
    g = _support('g', 2)
    unsafe = _support('unsafe', 100)
    p = BeliefCell('P', (unsafe,), (_act('magic', {'unsafe': {'seen': (g,)}}),))
    terminal = BeliefCell('G', (g,))
    result = _solve(cells=(p, terminal), ctx=ctx)
    assert result.ranks == {'G': 0}


def test_rank_budget_executes_and_replans_without_horizon_reset():
    ctx = _contract(horizon=3)
    cert = _solve(ctx=ctx)
    current = start_sc_execution(cert, 'B')
    assert current.remaining_rank == 2
    current = advance_sc_execution(cert, current, 'seen', 'C')
    assert current.remaining_rank == 1
    assert replan_sc_execution(cert, current).remaining_rank == 1
    current = advance_sc_execution(cert, current, 'seen', 'G')
    assert current.remaining_rank == 0
    with pytest.raises(SCExecutionError, match='TERMINAL_TAIL_REQUIRED'):
        advance_sc_execution(cert, current, 'seen', 'G')
    with pytest.raises(SCExecutionError, match='REPLAN_CONTEXT_CHANGED'):
        replan_sc_execution(_solve(ctx=_contract(protocol='changed')),
                            current)


def test_rank_budget_rejects_hidden_choice_and_new_horizon_stall():
    cert = _solve()
    budget = start_sc_execution(cert, 'B')
    for obs, child in (('unobserved', 'C'), ('seen', 'G')):
        with pytest.raises(SCExecutionError):
            advance_sc_execution(cert, budget, obs, child)
    with pytest.raises(SCExecutionError):
        start_sc_execution(cert, 'R')
    # At inherited rank 1, an arbitrarily fresh rank-2 policy must not be
    # accepted merely because it was generated with a new H=3 horizon.
    bad_budget = replace(budget, remaining_rank=1)
    with pytest.raises(SCExecutionError):
        replan_sc_execution(cert, bad_budget)
