from __future__ import annotations
import json
from pathlib import Path
import pytest

from rampd_core.interval import Interval
from rampd_core.model import StateBounds
from rampd_core.belief import BeliefCell, SupportAtom
from rampd_core.invariant import (
    EvidenceVerdict, ObservationSuccessors, AtomTransition, ActionWitness,
    SafeDomain, compute_information_invariant, support_subset_cell,
    save_invariant_certificate, replay_invariant_certificate,
)
from rampd_core.refinement import split_support_atom


def state(px=(0.0, 0.0), py=(0.0, 0.0), v=(0.0, 5.0)):
    return StateBounds(Interval(*px), Interval(*py), Interval(-0.1, 0.1),
                       Interval(*v), Interval(-1.0, 1.0), Interval(-0.1, 0.1))


def atom(aid, px=(0.0, 0.0), mode=(('protocol', 'open'), ('monitor', 'ok'))):
    return SupportAtom(aid, state(px=px), (), mode)


def domain():
    return SafeDomain(
        ego_bounds=StateBounds(Interval(-20, 20), Interval(-20, 20), Interval(-1, 1),
            Interval(0, 20), Interval(-5, 5), Interval(-0.5, 0.5)),
        allowed_modes=(('protocol', ('open',)), ('monitor', ('ok',))),
        required_mode_fields=('protocol', 'monitor'),
    )


def transition(src, obs, successors, evidence=None, verdict=EvidenceVerdict.PROVED):
    return AtomTransition(src, verdict, evidence or ('ev-' + src),
                          (ObservationSuccessors(obs, tuple(successors)),))


def action(action_id, transitions, control=(0.0, 0.0)):
    return ActionWitness(action_id, control, tuple(transitions))


def test_belief_cell_is_joint_support_not_independent_hidden_state():
    c = BeliefCell('B', (atom('a', (0, 1)), atom('b', (2, 3))))
    assert len(c.atoms) == 2
    assert c.policy_node_id == 'B'


def test_fixed_point_keeps_cells_with_common_action_and_all_observation_posteriors():
    l0, l1 = atom('l0', (0.0, 0.5)), atom('l1', (0.5, 1.0))
    L = BeliefCell('L', (l0, l1), (
        action('hold', [transition('l0', 'stay', [l0]), transition('l1', 'stay', [l1])]),
    ))
    a0, a1 = atom('a0', (2.0, 2.5)), atom('a1', (2.5, 3.0))
    A = BeliefCell('A', (a0, a1), (
        action('yield', [transition('a0', 'yielded', [l0]),
                         transition('a1', 'yielded', [l1])], control=(-1.0, 0.0)),
    ))
    result = compute_information_invariant((A, L), domain(), lambda ref: ref.startswith('ev-'))
    assert result.retained_cell_ids == ('A', 'L')
    da = next(x for x in result.decisions if x.cell_id == 'A')
    assert da.selected_action_id == 'yield'
    assert da.control == (-1.0, 0.0)
    assert da.observation_children == (('yielded', 'L'),)
    assert result.removals_per_iteration == (0,)
    assert result.certified is False


def test_fixed_point_removes_unsafe_cell_then_propagates_removal_backward():
    safe = atom('safe')
    C = BeliefCell('C', (safe,), (action('stay', [transition('safe', 'same', [safe])]),))
    x = atom('x', (2, 2))
    B = BeliefCell('B', (x,), ())
    y = atom('y', (3, 3))
    A = BeliefCell('A', (y,), (action('go_to_B', [transition('y', 'go', [x])]),))
    result = compute_information_invariant((A, B, C), domain(), lambda _: True)
    assert result.retained_cell_ids == ('C',)
    assert result.removals_per_iteration == (1, 1, 0)
    assert next(d for d in result.decisions if d.cell_id == 'B').retained is False
    assert next(d for d in result.decisions if d.cell_id == 'A').retained is False


def test_one_unresolved_atom_transition_rejects_the_common_action():
    a0, a1 = atom('a0'), atom('a1', (1, 1))
    A = BeliefCell('A', (a0, a1), (action('candidate', [
        transition('a0', 'obs', [a0]),
        transition('a1', 'obs', [a1], verdict=EvidenceVerdict.UNKNOWN),
    ]),))
    result = compute_information_invariant((A,), domain(), lambda _: True)
    assert result.retained_cell_ids == ()
    assert 'TRANSITION_UNKNOWN' in next(d for d in result.decisions if d.cell_id == 'A').reason


def test_no_evidence_verifier_fails_closed():
    a = atom('a')
    A = BeliefCell('A', (a,), (action('hold', [transition('a', 'same', [a])]),))
    result = compute_information_invariant((A,), domain(), evidence_verifier=None)
    assert result.retained_cell_ids == ()
    assert 'NO_EVIDENCE_VERIFIER' in result.decisions[0].reason


def test_missing_source_transition_is_rejected():
    a0, a1 = atom('a0'), atom('a1', (1, 1))
    A = BeliefCell('A', (a0, a1), (action('incomplete', [transition('a0', 'obs', [a0])]),))
    result = compute_information_invariant((A,), domain(), lambda _: True)
    assert result.retained_cell_ids == ()
    assert 'INCOMPLETE_SOURCE_COVERAGE' in result.decisions[0].reason


def test_each_observation_posterior_must_be_covered_by_one_retained_belief_cell():
    a = atom('a')
    b = atom('b', (1, 1))
    A = BeliefCell('A', (a,), (action('branch', [AtomTransition('a', EvidenceVerdict.PROVED, 'ev-a', (
        ObservationSuccessors('seen_A', (a,)),
        ObservationSuccessors('seen_B', (b,)),
    ))]),))
    # B is safe but not invariant; after it is removed, the B observation branch
    # is no longer routed to a retained support.
    B = BeliefCell('B', (b,), ())
    result = compute_information_invariant((A, B), domain(), lambda _: True)
    assert result.retained_cell_ids == ()
    assert 'POSTERIOR_NOT_COVERED:seen_B' in next(d for d in result.decisions if d.cell_id == 'A').reason


def test_union_support_coverage_requires_same_mode_and_full_box_containment():
    t0 = atom('t0', (0, 1))
    t1 = atom('t1', (1, 2))
    target = BeliefCell('T', (t0, t1))
    # Each posterior atom is covered by one atom of the union.
    assert support_subset_cell((atom('s0', (0.2, 0.4)), atom('s1', (1.2, 1.8))), target)
    # A single box spanning two target boxes is not contained in either one.
    assert not support_subset_cell((atom('wide', (0.5, 1.5)),), target)
    wrong_mode = atom('wrong', (0.2, 0.4), mode=(('protocol', 'closed'), ('monitor', 'ok')))
    assert not support_subset_cell((wrong_mode,), target)


def test_unsafe_initial_support_is_removed_even_if_transition_looks_good():
    bad = atom('bad', (30, 31))
    B = BeliefCell('B', (bad,), (action('stay', [transition('bad', 'same', [bad])]),))
    result = compute_information_invariant((B,), domain(), lambda _: True)
    assert result.retained_cell_ids == ()
    assert result.decisions[0].reason.startswith('INITIAL_EGO_STATE_OUTSIDE')


def test_policy_node_must_be_unique_per_complete_belief_support():
    a, b = atom('a'), atom('b', (1, 1))
    A = BeliefCell('A', (a,), policy_node_id='same-history')
    B = BeliefCell('B', (b,), policy_node_id='same-history')
    with pytest.raises(ValueError, match='unique policy node'):
        compute_information_invariant((A, B), domain())


def test_action_control_is_two_dimensional_ego_control():
    with pytest.raises(ValueError, match='jerk, steering_rate'):
        ActionWitness('bad', (0.0,), (transition('a', 'obs', [atom('a')]),))


def test_refinement_splits_support_box_without_splitting_information_node():
    a = atom('a', (0.0, 2.0))
    c = BeliefCell('B', (a,), actions=(action('old', [transition('a', 'same', [a])]),),
                   policy_node_id='obs-history-7')
    refined = split_support_atom(c, 'a', 'px')
    assert refined.cell_id == 'B'
    assert refined.policy_node_id == 'obs-history-7'
    assert refined.actions == ()  # source partition changed; old evidence invalid
    assert len(refined.atoms) == 2
    left, right = sorted(refined.atoms, key=lambda x: x.ego.px.lo)
    assert left.ego.px.hi == right.ego.px.lo
    assert left.ego.px.lo == 0.0 and right.ego.px.hi == 2.0


def test_refinement_rejects_unrepresentable_midpoint():
    import math
    a = atom('a', (1.0, math.nextafter(1.0, math.inf)))
    c = BeliefCell('B', (a,))
    with pytest.raises(ValueError, match='no representable'):
        split_support_atom(c, 'a', 'px')


def test_certificate_replay_and_tamper_rejection(tmp_path):
    a = atom('a')
    A = BeliefCell('A', (a,), (action('hold', [transition('a', 'same', [a])]),))
    verifier = lambda ref: ref == 'ev-a'
    result = compute_information_invariant((A,), domain(), verifier)
    path = tmp_path / 'invariant.json'
    save_invariant_certificate(path, (A,), domain(), result)
    replay = replay_invariant_certificate(path, verifier)
    assert replay.ok
    data = json.loads(path.read_text())
    data['claimed_result']['retained_cell_ids'] = []
    path.write_text(json.dumps(data))
    assert not replay_invariant_certificate(path, verifier).ok


def test_certificate_cannot_claim_concrete_safety_certification(tmp_path):
    a = atom('a')
    A = BeliefCell('A', (a,), (action('hold', [transition('a', 'same', [a])]),))
    result = compute_information_invariant((A,), domain(), lambda _: True)
    path = tmp_path / 'invariant.json'
    save_invariant_certificate(path, (A,), domain(), result)
    data = json.loads(path.read_text())
    data['certified'] = True
    path.write_text(json.dumps(data))
    assert not replay_invariant_certificate(path, lambda _: True).ok


def test_invalid_evidence_ref_is_rejected():
    a = atom('a')
    A = BeliefCell('A', (a,), (action('hold', [transition('a', 'same', [a])]),))
    result = compute_information_invariant((A,), domain(), lambda _: False)
    assert result.retained_cell_ids == ()
    assert 'EVIDENCE_REPLAY_FAILED' in result.decisions[0].reason


def test_friction_domain_singularity_fails_closed_as_unresolved():
    from rampd_core import BicycleParameters
    a = SupportAtom('singular', StateBounds(Interval(0,0),Interval(0,0),
        Interval(0,0),Interval(0,1),Interval(0,0),Interval(1.5,1.6)), (),
        (('protocol','open'),('monitor','ok')))
    B = BeliefCell('B',(a,))
    d = SafeDomain(StateBounds(Interval(-10,10),Interval(-10,10),Interval(-1,1),
        Interval(0,2),Interval(-1,1),Interval(1.5,1.6)),
        allowed_modes=domain().allowed_modes,
        required_mode_fields=domain().required_mode_fields,
        friction=BicycleParameters(2.5,0.9))
    result=compute_information_invariant((B,),d,lambda _:True)
    assert result.retained_cell_ids == ()
    assert result.decisions[0].reason.startswith('INITIAL_FRICTION_ENCLOSURE_UNRESOLVED')
