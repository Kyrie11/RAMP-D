import json
import pytest

from rampd_core import (
    Interval, StateBounds, SupportAtom, BeliefCell, SafeDomain,
    ActionWitness, AtomTransition, ObservationSuccessors, EvidenceVerdict,
    compute_information_invariant, BackupMode, BackupControllerError,
    BackupControlLimits, BackupTemplate, default_backup_limits,
    synthesize_public_backup, save_backup_graph, replay_backup_graph,
)


def _state(px):
    return StateBounds(Interval(*px), Interval(-1, 1), Interval(-.1, .1),
                       Interval(0, 10), Interval(-2, 2), Interval(-.3, .3))


def _atom(aid, px=(0, .5)):
    return SupportAtom(aid, _state(px), (),
                       (("monitor", "ok"), ("protocol", "open")))


def _domain():
    return SafeDomain(
        StateBounds(Interval(-10, 10), Interval(-10, 10), Interval(-1, 1),
                    Interval(0, 20), Interval(-5, 5), Interval(-.5, .5)),
        allowed_modes=(("monitor", ("ok",)), ("protocol", ("open",))),
        required_mode_fields=("monitor", "protocol"),
    )


def _transition(src, obs, atoms, ref):
    return AtomTransition(src, EvidenceVerdict.PROVED, ref,
                          (ObservationSuccessors(obs, tuple(atoms)),))


def _fixture():
    l0, l1 = _atom("l0", (0, .5)), _atom("l1", (.5, 1))
    L = BeliefCell("L", (l0, l1), (
        ActionWitness("hold", (0., 0.), (
            _transition("l0", "stay", (l0,), "ev-l0"),
            _transition("l1", "stay", (l1,), "ev-l1"),)),))
    a0, a1 = _atom("a0", (2, 2.5)), _atom("a1", (2.5, 3))
    A = BeliefCell("A", (a0, a1), (
        ActionWitness("yield", (-1., 0.), (
            _transition("a0", "yielded", (l0,), "ev-a0"),
            _transition("a1", "yielded", (l1,), "ev-a1"),)),))
    result = compute_information_invariant((A, L), _domain(),
                                           lambda ref: ref.startswith("ev-"))
    return (A, L), result


def test_phase3_synthesizes_one_public_node_per_retained_cell():
    cells, invariant = _fixture()
    limits = default_backup_limits()
    result = synthesize_public_backup(cells, invariant, control_limits=limits)
    assert result.status == "BACKUP_GRAPH_SYNTHESIZED"
    assert result.graph is not None
    assert result.executable_nodes == 2
    assert result.all_children_retained
    assert result.common_control_violations == 0
    assert {n.cell_id for n in result.graph.nodes} == {"A", "L"}
    a = result.graph.node_for_cell("A")
    assert a.template.mode is BackupMode.YIELD
    assert result.graph.control(a.node_id) == (-1.0, 0.0)
    assert result.graph.route(a.node_id, "yielded") == "backup:L"
    assert result.graph.step(a.node_id).child_node_id is None


def test_phase3_does_not_branch_on_hidden_atom():
    cells, invariant = _fixture()
    graph = synthesize_public_backup(cells, invariant).graph
    assert graph is not None
    node = graph.node_for_cell("A")
    # The public API accepts only a node id. There is no atom_id parameter.
    assert graph.control(node.node_id) == (-1.0, 0.0)
    with pytest.raises(BackupControllerError, match="UNKNOWN_OBSERVATION"):
        graph.route(node.node_id, "hidden_atom_a0")


def test_phase3_rejects_control_outside_actuator_limits():
    cells, invariant = _fixture()
    limits = BackupControlLimits(-.5, .5, -.6, .6, .1)
    result = synthesize_public_backup(cells, invariant, control_limits=limits)
    assert result.status == "UNKNOWN"
    assert any("CONTROL_OUTSIDE_LIMITS:A" in x for x in result.reasons)
    assert result.common_control_violations == 1


def test_phase3_rejects_missing_action_or_child_outside_retained():
    cells, invariant = _fixture()
    bad = invariant.decisions[0]
    # Forge a result whose retained node has no selected witness.
    from rampd_core.invariant import InvariantResult, CellDecision
    decisions = tuple(CellDecision(d.cell_id, d.retained, d.reason,
                                   None if d.cell_id == "A" else d.selected_action_id,
                                   None if d.cell_id == "A" else d.control,
                                   d.observation_children, d.iteration)
                      for d in invariant.decisions)
    forged = InvariantResult(invariant.status, invariant.retained_cell_ids,
                             decisions, invariant.iterations,
                             invariant.removals_per_iteration)
    result = synthesize_public_backup(cells, forged)
    assert result.status == "UNKNOWN"
    assert any("MISSING_SELECTED_WITNESS:A" in x for x in result.reasons)


def test_phase3_template_library_must_match_phase2_control():
    cells, invariant = _fixture()
    library = {"hold": BackupTemplate(BackupMode.HOLD_BEFORE_GATE, (1., 0.))}
    result = synthesize_public_backup(cells, invariant, template_library=library)
    assert result.status == "UNKNOWN"
    assert any("TEMPLATE_ERROR:L" in x for x in result.reasons)


def test_phase3_graph_certificate_replay_and_tamper_rejection(tmp_path):
    cells, invariant = _fixture()
    result = synthesize_public_backup(cells, invariant,
                                      control_limits=default_backup_limits())
    path = tmp_path / "backup.json"
    save_backup_graph(path, result.graph)
    ok, message = replay_backup_graph(path, default_backup_limits())
    assert ok and "uncertified" in message
    data = json.loads(path.read_text())
    data["certified"] = True
    path.write_text(json.dumps(data))
    ok, _ = replay_backup_graph(path, default_backup_limits())
    assert not ok


def test_phase3_graph_replay_rejects_tampered_control(tmp_path):
    cells, invariant = _fixture()
    result = synthesize_public_backup(cells, invariant)
    path = tmp_path / "backup.json"
    save_backup_graph(path, result.graph)
    data = json.loads(path.read_text())
    data["nodes"][0]["control"][0] = 99.0
    path.write_text(json.dumps(data))
    ok, message = replay_backup_graph(path, default_backup_limits())
    assert not ok and "outside limits" in message


def test_phase3_limits_validate_parameters_and_clamp():
    with pytest.raises(BackupControllerError):
        BackupControlLimits(1, -1, -.5, .5, .1)
    limits = default_backup_limits()
    assert limits.clamp_control((99, -99)) == (limits.jerk_max, limits.steering_rate_min)


def test_phase3_nonzero_feedback_gain_is_explicitly_deferred():
    with pytest.raises(BackupControllerError, match="nonzero public feedback gain"):
        BackupTemplate(BackupMode.YIELD, (-1., 0.), feedback_gain=(
            (1., 0., 0., 0., 0., 0.), (0., 0., 0., 0., 0., 0.)))

