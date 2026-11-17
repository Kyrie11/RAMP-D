"""A5 finite-tail mathematics tests without a compiled/native interval library."""
import importlib.util
from pathlib import Path
from fractions import Fraction as Q
from dataclasses import replace

PATH = Path(__file__).resolve().parents[1] / 'python/rampd_core/a5_finite_contract.py'
spec = importlib.util.spec_from_file_location('rampd_a5_finite', PATH)
import sys
mod = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = mod
spec.loader.exec_module(mod)
E, M, P = mod.FiniteTaskEdge, mod.FiniteTaskModel, mod.FiniteTailPolicy


def fixture():
    model = M(('pending','continue','accepted','stuck'), frozenset({'accepted'}),
              (E('pending','move','seen','accepted'),
               E('pending','move','silence','continue'),
               E('continue','finish','seen','accepted'),
               E('continue','wait','silence','continue')),
              Q(1,8), 'task:model:2026')
    policy = P(model.digest, ('pending',),
               (('pending','move'), ('continue','finish')),
               Q(1,4), 2)
    return model, policy


def test_all_branches_accept_in_exact_worst_case():
    model, policy = fixture()
    r = mod.audit_finite_tail(model, policy)
    assert r.ok and r.exact_worst_s == Q(1,4)
    assert r.model_relative_only is True


def test_missing_long_branch_rejected():
    model, policy = fixture()
    broken = replace(model, edges=model.edges[:1])
    # Hash changes when an allowed branch is removed. Existing certificates
    # cannot replay against a different declared model.
    assert not mod.audit_finite_tail(broken, policy).ok


def test_infinite_safe_wait_is_not_task_acceptance():
    model, policy = fixture()
    bad = replace(policy, actions=(('pending','move'), ('continue','wait')))
    r = mod.audit_finite_tail(model, bad)
    assert not r.ok and r.reason == 'NONACCEPTING_AT_DEPTH_LIMIT'


def test_unmerged_same_observation_is_rejected():
    model, policy = fixture()
    changed = replace(model, edges=model.edges +
                      (E('pending','move','seen','continue'),))
    wrong = replace(policy, model_digest=changed.digest)
    assert mod.audit_finite_tail(changed, wrong).reason == 'UNMERGED_SAME_OBSERVATION'


def test_model_context_mutation_rejected():
    model, policy = fixture()
    assert not mod.audit_finite_tail(model, replace(policy, model_digest='stale')).ok
    assert not mod.audit_finite_tail(replace(model, version='revised'), policy).ok


def test_exact_duration_mismatch_fails_closed():
    model, policy = fixture()
    r = mod.audit_finite_tail(model, replace(policy, claimed_max_s='0.249'))
    assert r.reason == 'WORST_CASE_DURATION_MISMATCH'


def test_decimal_and_floats_are_not_interchangeable_for_proof_time():
    import pytest
    model, policy = fixture()
    with pytest.raises(TypeError):
        replace(policy, claimed_max_s=0.25)
    with pytest.raises(TypeError):
        replace(model, step_s=0.125)


def test_empty_or_unsafe_task_graph_fails():
    import pytest
    with pytest.raises(ValueError):
        M(('pending',), frozenset({'ghost'}), (), Q(1,8), 'a')
    with pytest.raises(ValueError):
        M(('pending',), frozenset(), (E('pending','a','o','ghost'),), Q(1,8), 'a')
