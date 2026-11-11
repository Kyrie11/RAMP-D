"""Regression: proofs cannot migrate to a different current obligation.

The trusted store below is a finite-game fixture. A content digest establishes
identity only; Phase 3 additionally replays the actual continuous tube evidence.
"""
from dataclasses import replace
import json

import pytest

from rampd_core.interval import Interval
from rampd_core.model import StateBounds
from rampd_core.belief import BeliefCell, SupportAtom
from rampd_core.invariant import (
    ActionWitness, AtomTransition, EvidenceContext, EvidenceVerdict,
    ObservationSuccessors, SafeDomain, compute_information_invariant,
    evidence_context_digest, replay_invariant_certificate,
    save_invariant_certificate,
)


def fixture():
    def atom(aid, lo, hi):
        return SupportAtom(aid, StateBounds(Interval(lo, hi), *(
            Interval.point(0) for _ in range(5))))
    a, b = atom("a", 0, 1), atom("b", 2, 3)
    transitions = tuple(AtomTransition(x.atom_id, EvidenceVerdict.PROVED,
        "proof-" + x.atom_id, (ObservationSuccessors("same", (x,)),)) for x in (a, b))
    action = ActionWitness("hold", (0.0, 0.0), transitions)
    cell = BeliefCell("B", (a, b), (action,), policy_node_id="public-history")
    safe = SafeDomain(StateBounds(*(Interval(-10, 10) for _ in range(6))))
    trusted = {t.evidence_ref: evidence_context_digest(
        EvidenceContext(cell, x, action, t)) for x, t in zip(cell.atoms, transitions)}

    def verifier(context):
        return (isinstance(context, EvidenceContext)
                and trusted.get(context.evidence_ref) == evidence_context_digest(context))
    return cell, safe, verifier


def altered(cell, kind):
    action = cell.actions[0]
    if kind == "control":
        action = replace(action, control=(1000.0, 1000.0))
    elif kind == "controller":
        action = replace(action, controller_ref="different-public-feedback-law")
    elif kind == "action_id":
        action = replace(action, action_id="a-different-action")
    elif kind == "observation":
        tr = action.transitions[0]
        tr = replace(tr, branches=(replace(tr.branches[0], observation="invented-observation"),))
        action = replace(action, transitions=(tr, *action.transitions[1:]))
    elif kind == "posterior":
        tr = action.transitions[0]
        old = tr.branches[0].atoms[0]
        succ = replace(old, ego=replace(old.ego, px=Interval(0.25, 0.75)))
        tr = replace(tr, branches=(replace(tr.branches[0], atoms=(succ,)),))
        action = replace(action, transitions=(tr, *action.transitions[1:]))
    elif kind == "source_support":
        a, b = cell.atoms
        cell = replace(cell, atoms=(replace(a, ego=replace(a.ego, px=Interval(-1, 1))), b))
    elif kind == "other_source_support":
        a, b = cell.atoms
        cell = replace(cell, atoms=(a, replace(b, ego=replace(b.ego, px=Interval(2, 4)))))
    elif kind == "policy_history":
        cell = replace(cell, policy_node_id="different-public-history")
    else:
        raise AssertionError(kind)
    return replace(cell, actions=(action,))


@pytest.mark.parametrize("kind", ["control", "controller", "action_id", "observation",
    "posterior", "source_support", "other_source_support", "policy_history"])
def test_context_bound_evidence_rejects_reused_reference(kind):
    cell, safe, verifier = fixture()
    assert compute_information_invariant((cell,), safe, verifier).retained_cell_ids == ("B",)
    changed = altered(cell, kind)
    result = compute_information_invariant((changed,), safe, verifier)
    assert result.retained_cell_ids == ()
    assert "EVIDENCE_REPLAY_FAILED" in result.decisions[0].reason


def test_ref_only_callback_is_not_automatically_accepted():
    cell, safe, _ = fixture()
    old_verifier = lambda ref: ref.startswith("proof-")
    result = compute_information_invariant((cell,), safe, old_verifier)
    assert result.retained_cell_ids == ()
    assert "EVIDENCE_REPLAY_FAILED" in result.decisions[0].reason


def test_truthy_non_boolean_verifier_result_is_rejected():
    cell, safe, _ = fixture()
    result = compute_information_invariant((cell,), safe, lambda context: {"ok": False})
    assert result.retained_cell_ids == ()


def test_certificate_rejects_input_tamper_even_with_matching_claimed_control(tmp_path):
    cell, safe, verifier = fixture()
    result = compute_information_invariant((cell,), safe, verifier)
    path = tmp_path / "candidate.json"
    save_invariant_certificate(path, (cell,), safe, result)
    assert replay_invariant_certificate(path, verifier).ok
    data = json.loads(path.read_text())
    data["cells"][0]["actions"][0]["control"] = [1000.0, 1000.0]
    data["claimed_result"]["decisions"][0]["control"] = [1000.0, 1000.0]
    path.write_text(json.dumps(data))
    assert not replay_invariant_certificate(path, verifier).ok


def test_legacy_constant_control_certificate_uses_new_context_verifier(tmp_path):
    cell, safe, verifier = fixture()
    result = compute_information_invariant((cell,), safe, verifier)
    path = tmp_path / "legacy.json"
    save_invariant_certificate(path, (cell,), safe, result)
    data = json.loads(path.read_text())
    data["schema"] = "rampd.info-invariant-candidate.v1"
    for c in data["cells"]:
        for a in c["actions"]:
            a.pop("controller_ref")
    path.write_text(json.dumps(data))
    assert replay_invariant_certificate(path, verifier).ok
    assert not replay_invariant_certificate(path, lambda ref: ref.startswith("proof-")).ok


def test_public_feedback_certificate_cannot_be_downgraded_to_v1(tmp_path):
    cell, safe, _ = fixture()
    changed = altered(cell, "controller")
    result = compute_information_invariant((changed,), safe, lambda context: True)
    path = tmp_path / "downgrade.json"
    save_invariant_certificate(path, (changed,), safe, result)
    data = json.loads(path.read_text())
    data["schema"] = "rampd.info-invariant-candidate.v1"
    path.write_text(json.dumps(data))
    replay = replay_invariant_certificate(path, lambda context: True)
    assert not replay.ok
    assert "v1 certificates cannot represent" in replay.message
