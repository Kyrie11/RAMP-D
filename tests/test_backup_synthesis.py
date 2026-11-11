"""Physical local-evidence and information-flow regressions for Phase 3.

These tests use the real MPFR/Picard backend. Fixtures are synthetic bounded
bicycle/static-scene contracts, never a full protocol or vehicle guarantee.
"""
from copy import deepcopy
from dataclasses import replace
import hashlib
import json
from types import SimpleNamespace

import pytest

from rampd_core.interval import Interval
from rampd_core.model import StateBounds, ControlBounds, BicycleParameters
from rampd_core.belief import BeliefCell, SupportAtom
from rampd_core.control import SampledFeedbackLaw, RecoveryKind, ZERO_GAIN, ZERO_ERROR
from rampd_core.footprint import VehicleGeometry
from rampd_core.invariant import EvidenceContext, SafeDomain, ObservationSuccessors
from rampd_core.reachability import PicardOptions
from rampd_core.backup import (
    BackupContract, LocalEvidenceStore, StaticObstacle, StepCheck,
    inspect_step_proof, synthesize_backup, validate_feedback_step,
)


def state(px=0.0, py=0.0, psi=0.0, v=0.0, a=0.0, delta=0.0):
    return StateBounds(*(x if isinstance(x, Interval) else Interval.point(x)
                         for x in (px, py, psi, v, a, delta)))


def contract(**changes):
    safe = SafeDomain(StateBounds(Interval(-20, 20), Interval(-5, 5),
        Interval(-0.5, 0.5), Interval(0, 5), Interval(-4, 4), Interval(-0.4, 0.4)))
    limits = ControlBounds(Interval(-4, 4), Interval(-0.5, 0.5))
    result = BackupContract("synthetic-local-test", safe, BicycleParameters(2.5, 0.8),
        limits, VehicleGeometry(2.0, 1.0, 0.5), 0.125,
        Interval(-30, 30), Interval(-5, 5),
        options=PicardOptions(max_step_s=0.03125))
    return replace(result, **changes)


def law(c=None, *, name="hold", bias=(0.0, 0.0), gain=ZERO_GAIN,
        reference=(0.0,) * 6, kind=RecoveryKind.HOLD_BEFORE_GATE):
    c = contract() if c is None else c
    return SampledFeedbackLaw(name, kind, bias, gain, reference, c.control_limits)


def broad_target(cid="T", mode=()):
    target = SupportAtom("target", StateBounds(Interval(-10, 10), Interval(-1, 1),
        Interval(-0.2, 0.2), Interval(0, 3), Interval(-2, 2), Interval(-0.2, 0.2)), mode=mode)
    return BeliefCell(cid, (target,))


def contexts(cell, action):
    source = {a.atom_id: a for a in cell.atoms}
    return tuple(EvidenceContext(cell, source[t.source_atom_id], action, t)
                 for t in action.transitions)


def registered_fixture():
    c = contract()
    source = SupportAtom("a", state(v=1.0))
    cell = BeliefCell("B", (source,))
    controller = law(c)
    check = validate_feedback_step(source, controller, c)
    assert check.status == "VALIDATED_LOCAL", check.reason
    store = LocalEvidenceStore(c)
    action = store.register(cell, controller, {"a": check}, {"a": ("silence",)}, "hold-public")
    return c, cell, controller, check, store, action, contexts(cell, action)[0]


def test_finite_search_ranks_verified_margin_and_retains_alternative_common_laws():
    c = contract(gate_front_x=1.8)
    cell = BeliefCell("B", (SupportAtom("a", state(v=1.0)),))
    fast = law(c, name="accelerate", bias=(4.0, 0.0))
    coast = law(c, name="coast")
    store = LocalEvidenceStore(c)
    result = synthesize_backup(cell, (fast, coast), (broad_target(),), store)
    assert result.status == "SYNTHESIZED_LOCAL", result.attempts
    assert len(result.choices) == 2
    assert result.selected.law.digest == coast.digest
    assert result.choices[0].reserve_lower > result.choices[1].reserve_lower
    assert result.full_support_certified is False
    for choice in result.choices:
        assert choice.action.controller_ref == choice.law.digest
        assert choice.action.control == choice.law.bias
        assert all(store.verify(ctx) for ctx in contexts(cell, choice.action))


def test_one_unsafe_source_rejects_a_law_for_the_entire_belief_support():
    c = contract(gate_front_x=10.0)
    cell = BeliefCell("B", (SupportAtom("safe", state()), SupportAtom("unsafe", state(px=9.0))))
    assert validate_feedback_step(cell.atoms[0], law(c), c).status == "VALIDATED_LOCAL"
    store = LocalEvidenceStore(c)
    result = synthesize_backup(cell, (law(c),), (broad_target(),), store)
    assert result.status == "UNKNOWN_NO_VALIDATED_CANDIDATE"
    assert result.choices == ()
    assert "SPATIAL_CLEARANCE_NOT_PROVED" in result.attempts[0]["reason"]
    assert store.records == {}


def test_same_observation_aggregates_all_sources_into_one_target_information_cell():
    c = contract()
    controller = law(c)
    a, b = SupportAtom("a", state(px=0.0, v=1.0)), SupportAtom("b", state(px=2.0, v=1.0))
    cell = BeliefCell("B", (a, b))
    targets = []
    for source, target_id in ((a, "Ta"), (b, "Tb")):
        check = validate_feedback_step(source, controller, c)
        assert check.status == "VALIDATED_LOCAL"
        targets.append(BeliefCell(target_id, (SupportAtom(target_id, check.endpoint),)))

    unresolved = synthesize_backup(cell, (controller,), targets, LocalEvidenceStore(c),
        {"a": ("same",), "b": ("same",)})
    assert unresolved.status == "UNKNOWN_NO_VALIDATED_CANDIDATE"
    assert "POSTERIOR_NOT_IN_SINGLE_TARGET:same" in unresolved.attempts[0]["reason"]

    union_target = BeliefCell("T_union", tuple(t.atoms[0] for t in targets))
    store = LocalEvidenceStore(c)
    resolved = synthesize_backup(cell, (controller,), (union_target,), store,
        {"a": ("same",), "b": ("same",)})
    assert resolved.status == "SYNTHESIZED_LOCAL", resolved.attempts
    assert resolved.selected.observation_children == (("same", "T_union"),)
    assert len(resolved.selected.action.transitions) == 2
    assert all(store.verify(ctx) for ctx in contexts(cell, resolved.selected.action))

    distinguishable = synthesize_backup(cell, (controller,), targets, LocalEvidenceStore(c),
        {"a": ("observed_a",), "b": ("observed_b",)})
    assert distinguishable.status == "SYNTHESIZED_LOCAL", distinguishable.attempts
    assert distinguishable.selected.observation_children == (("observed_a", "Ta"), ("observed_b", "Tb"))


def test_nonzero_public_gain_propagates_measurement_error_and_replays_all_sources():
    error = list(ZERO_ERROR)
    error[3] = Interval(-0.1, 0.1)
    c = contract(measurement_error=tuple(error))
    gain = ((0.0, 0.0, 0.0, -1.0, -2.0, 0.0), ZERO_GAIN[1])
    controller = law(c, gain=gain, reference=(0.0, 0.0, 0.0, 1.0, 0.0, 0.0))
    a = SupportAtom("a", state(v=Interval(0.95, 1.05)))
    b = SupportAtom("b", state(px=2.0, v=Interval(0.95, 1.05)))
    cell = BeliefCell("B", (a, b))
    noisy = controller.image(a.ego, c.measurement_error)
    exact_measurement = controller.image(a.ego)
    assert noisy.jerk.lo <= -0.15 and noisy.jerk.hi >= 0.15
    assert noisy.jerk.width_upper() > exact_measurement.jerk.width_upper()
    store = LocalEvidenceStore(c)
    result = synthesize_backup(cell, (controller,), (broad_target(),), store)
    assert result.status == "SYNTHESIZED_LOCAL", result.attempts
    assert result.selected.law.gain == gain
    assert all(store.verify(ctx) for ctx in contexts(cell, result.selected.action))


def test_gate_constraint_uses_front_footprint_and_rear_axle_offset():
    source = SupportAtom("a", state())
    shifted = contract(geometry=VehicleGeometry(4.0, 1.0, 1.5), gate_front_x=3.25)
    assert source.ego.px.hi < shifted.gate_front_x
    check = validate_feedback_step(source, law(shifted), shifted)
    assert check.status == "UNKNOWN"
    assert check.reason == "SPATIAL_CLEARANCE_NOT_PROVED"
    centered = replace(shifted, geometry=VehicleGeometry(4.0, 1.0, 0.0))
    center_check = validate_feedback_step(source, law(centered), centered)
    assert center_check.status == "VALIDATED_LOCAL", center_check.reason


@pytest.mark.parametrize("period", [0.1, 0.125])
def test_stationary_boundary_does_not_inherit_picard_search_inflation(period):
    c = contract(decision_period_s=period)
    source = SupportAtom("stopped", state())
    check = validate_feedback_step(source, law(c), c)
    assert check.status == "VALIDATED_LOCAL", check.reason
    assert check.endpoint.v == Interval.point(0.0)
    assert check.endpoint.a == Interval.point(0.0)
    assert check.endpoint.delta == Interval.point(0.0)


def test_stop_polynomial_remains_nonnegative_at_the_terminal_zero_velocity_boundary():
    c = contract(decision_period_s=0.25)
    source = SupportAtom("braking", state(v=0.125, a=-1.0))
    controller = law(c, name="release-brake-to-stop", bias=(4.0, 0.0),
                     kind=RecoveryKind.BRAKE_TO_STOP)
    # Exact dyadic fixture: v(t)=2*(t-.25)^2 >= 0, a(t)=-1+4*t.
    # A sound range should prove the nonnegative speed without clipping it.
    check = validate_feedback_step(source, controller, c)
    assert check.status == "VALIDATED_LOCAL", check.reason
    assert check.endpoint.v == Interval.point(0.0)
    assert check.endpoint.a == Interval.point(0.0)


def test_low_friction_is_rejected_despite_state_box_being_in_domain():
    c = contract(params=BicycleParameters(2.5, 0.1))
    source = SupportAtom("a", state(v=1.0, a=2.0))
    assert c.domain.contains_atom(source)[0]
    check = validate_feedback_step(source, law(c), c)
    assert check.status == "UNKNOWN"
    assert check.reason == "FRICTION_NOT_PROVED"


def test_collision_between_safe_endpoints_is_not_missed_by_static_scene_check():
    geometry = VehicleGeometry(0.2, 0.2)
    obstacle = StaticObstacle("wall", state(px=2.0), geometry)
    c = contract(geometry=geometry, decision_period_s=1.0, obstacles=(obstacle,),
        options=PicardOptions(max_step_s=0.0625))
    source = SupportAtom("a", state(v=4.0))
    # Start x=0 and exact endpoint x=4 both clear the obstacle at x=2.
    assert abs(0.0 - 2.0) > geometry.length_m
    assert abs(4.0 - 2.0) > geometry.length_m
    check = validate_feedback_step(source, law(c), c)
    assert check.status == "UNKNOWN"
    # The configured positive clearance can fail just before the outer swept
    # footprints overlap; both outcomes correctly withhold local validation.
    assert check.reason in ("STATIC_OBSTACLE_SEPARATION_UNKNOWN:wall", "SPATIAL_CLEARANCE_NOT_PROVED")
    clear = replace(c, obstacles=(replace(obstacle, state=state(px=2.0, py=2.0)),))
    check_clear = validate_feedback_step(source, law(clear), clear)
    assert check_clear.status == "VALIDATED_LOCAL", check_clear.reason
    assert check_clear.endpoint.px.contains(4.0)
    assert dict(check_clear.margins_m)["obstacle:wall"] > 1.79


def test_unknown_other_agent_dynamics_cannot_be_frozen_silently():
    c = contract()
    source = SupportAtom("a", state(), other=(("other_x", Interval(10.0, 11.0)),))
    check = validate_feedback_step(source, law(c), c)
    assert check.status == "UNKNOWN"
    assert check.reason == "OTHER_AGENT_DYNAMICS_REQUIRE_PHASE4"


def test_incomplete_picard_budget_returns_unknown_without_registering_evidence():
    c = contract(options=PicardOptions(max_step_s=0.03125, max_steps=1))
    cell = BeliefCell("B", (SupportAtom("a", state(v=1.0)),))
    store = LocalEvidenceStore(c)
    result = synthesize_backup(cell, (law(c),), (broad_target(),), store)
    assert result.status == "UNKNOWN_NO_VALIDATED_CANDIDATE"
    assert result.choices == ()
    assert "DYNAMICS_" in result.attempts[0]["reason"]
    assert store.records == {}


def test_candidate_budget_distinguishes_validated_partial_search_from_no_evidence():
    c = contract()
    cell = BeliefCell("B", (SupportAtom("a", state()),))
    good, bad = law(c), law(c, name="reverse-from-zero", bias=(-1.0, 0.0))
    partial = synthesize_backup(cell, (good, bad), (broad_target(),), LocalEvidenceStore(c), max_candidates=1)
    assert partial.status == "PARTIAL_SEARCH"
    assert len(partial.choices) == 1 and len(partial.attempts) == 1
    unknown = synthesize_backup(cell, (bad, good), (broad_target(),), LocalEvidenceStore(c), max_candidates=1)
    assert unknown.status == "UNKNOWN_BUDGET"
    assert unknown.choices == () and len(unknown.attempts) == 1


@pytest.mark.parametrize("valid_candidate", [True, False])
def test_deadline_exceeded_inside_last_candidate_is_reported(monkeypatch, valid_candidate):
    import rampd_core.backup as backup_module
    c = contract()
    cell = BeliefCell("B", (SupportAtom("a", state()),))
    controller = law(c, bias=(0.0, 0.0) if valid_candidate else (-1.0, 0.0))
    # Replace only the search module's clock object. The real Picard engine and
    # independent evidence replay still execute, using their actual clocks.
    clock = iter((0.0, 0.0, 0.02, 0.03))
    monkeypatch.setattr(backup_module, "time", SimpleNamespace(perf_counter=lambda: next(clock)))
    result = synthesize_backup(cell, (controller,), (broad_target(),), LocalEvidenceStore(c),
        time_limit_s=0.01)
    assert result.status == ("PARTIAL_SEARCH" if valid_candidate else "UNKNOWN_BUDGET")
    assert len(result.choices) == int(valid_candidate)
    assert len(result.attempts) == 1


def test_missing_source_observation_cover_is_rejected():
    c = contract()
    cell = BeliefCell("B", (SupportAtom("a", state()), SupportAtom("b", state(px=1.0))))
    with pytest.raises(ValueError, match="every source atom"):
        synthesize_backup(cell, (law(c),), (broad_target(),), LocalEvidenceStore(c), {"a": ("seen",)})


def test_register_requires_complete_source_checks():
    c, cell, controller, check, store, _, _ = registered_fixture()
    expanded = replace(cell, atoms=(*cell.atoms, SupportAtom("b", state(px=1.0))))
    with pytest.raises(ValueError, match="complete source evidence"):
        store.register(expanded, controller, {"a": check}, {"a": ("same",), "b": ("same",)}, "bad")


@pytest.mark.parametrize("change", ["law", "gain", "period", "disturbance", "measurement_error", "branch", "source", "record"])
def test_registered_evidence_rejects_changed_physical_or_information_context(change):
    c, cell, controller, _, store, action, context = registered_fixture()
    assert store.verify(context)
    if change == "law":
        action = replace(action, controller_ref="law-sha256:unregistered")
        context = replace(context, action=action)
    elif change == "gain":
        gain = ((0.0, 0.0, 0.0, -1.0, 0.0, 0.0), ZERO_GAIN[1])
        store.laws[controller.digest] = replace(controller, gain=gain)
    elif change == "period":
        store.contract = replace(c, decision_period_s=0.25)
    elif change == "disturbance":
        store.contract = replace(c, derivative_disturbance=(Interval(-0.1, 0.1), *ZERO_ERROR[1:]))
    elif change == "measurement_error":
        store.contract = replace(c, measurement_error=(Interval(-0.1, 0.1), *ZERO_ERROR[1:]))
    elif change == "branch":
        old = context.transition
        new = replace(old, branches=(ObservationSuccessors("invented-observation", old.branches[0].atoms),))
        context = replace(context, transition=new, action=replace(action, transitions=(new,)))
    elif change == "source":
        source = replace(context.source_atom, ego=state(px=1.0, v=1.0))
        context = replace(context, source_atom=source, cell=replace(cell, atoms=(source,)))
    elif change == "record":
        store.records[context.evidence_ref]["reserve_lower"] += 0.25
    assert store.verify(context) is False


def test_rehashing_tampered_tube_record_does_not_replace_independent_replay():
    _, _, _, _, store, action, context = registered_fixture()
    record = deepcopy(store.records[context.evidence_ref])
    record["proof"]["initial"][0] = [8.0, 8.0]
    encoded = json.dumps(record, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    reference = "backup-evidence-sha256:" + hashlib.sha256(encoded).hexdigest()
    store.records[reference] = record
    transition = replace(context.transition, evidence_ref=reference)
    changed = replace(context, transition=transition, action=replace(action, transitions=(transition,)))
    assert store.verify(changed) is False


def test_status_label_alone_cannot_register_replayable_physical_evidence():
    c = contract()
    controller = law(c)
    source = SupportAtom("a", state(v=1.0))
    cell = BeliefCell("B", (source,))
    fake = StepCheck("VALIDATED_LOCAL", "invented success label", endpoint=source.ego,
                    control_image=controller.image(source.ego), reserve_lower=1.0, proof={})
    store = LocalEvidenceStore(c)
    action = store.register(cell, controller, {"a": fake}, {"a": ("silence",)}, "fake")
    assert all(not store.verify(ctx) for ctx in contexts(cell, action))


def test_evidence_round_trip_replays_and_rejects_unmatched_law_digest():
    _, _, _, _, store, _, context = registered_fixture()
    data = json.loads(json.dumps(store.to_dict()))
    restored = LocalEvidenceStore.from_dict(data)
    assert restored.verify(context)
    bad = deepcopy(data)
    first = next(iter(bad["laws"].values()))
    first["gain"][0][3] = -1.0
    with pytest.raises(ValueError, match="law digest mismatch"):
        LocalEvidenceStore.from_dict(bad)


def test_step_replay_rejects_period_and_disturbance_even_without_store_hashes():
    c, cell, controller, check, _, _, _ = registered_fixture()
    source = cell.atoms[0]
    changed_period = inspect_step_proof(source, controller, replace(c, decision_period_s=0.25), check.proof)
    assert changed_period.status == "UNKNOWN" and changed_period.reason == "DYNAMICS_CONTEXT_MISMATCH"
    disturbed = replace(c, derivative_disturbance=(Interval(-0.1, 0.1), *ZERO_ERROR[1:]))
    changed_disturbance = inspect_step_proof(source, controller, disturbed, check.proof)
    assert changed_disturbance.status == "UNKNOWN" and changed_disturbance.reason == "DYNAMICS_CONTEXT_MISMATCH"
