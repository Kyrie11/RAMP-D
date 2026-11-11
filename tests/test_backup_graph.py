"""Closed public backup graphs and execution guards, with real local proofs.

The declared finite observations are a synthetic model. These tests do not
pretend to prove a real sensor/protocol observation relation (Phase 4).
"""
from dataclasses import replace
from fractions import Fraction as Q
import json
import math

import pytest

from rampd_core.backup import (BackupContract, LocalEvidenceStore,
                              synthesize_backup, validate_feedback_step)
from rampd_core.backup_graph import (
    BackupExecutionError, BackupExecutor, build_backup_graph,
    load_backup_graph, save_backup_graph,
)
from rampd_core.belief import BeliefCell, SupportAtom
from rampd_core.control import RecoveryKind, SampledFeedbackLaw, ZERO_GAIN
from rampd_core.footprint import VehicleGeometry
from rampd_core.interval import Interval
from rampd_core.invariant import EvidenceContext, SafeDomain, support_subset_cell
from rampd_core.model import BicycleParameters, ControlBounds, StateBounds
from rampd_core.reachability import PicardOptions


@pytest.fixture
def graph_fixture():
    state = StateBounds.point([0, 0, 0, 0, 0, 0])
    domain = SafeDomain(StateBounds(Interval(-10, 10), Interval(-2, 2),
        Interval(-0.4, 0.4), Interval(0, 4), Interval(-3, 3), Interval(-0.3, 0.3)),
        allowed_modes=(("rule", ("open", "closed")),), required_mode_fields=("rule",))
    limits = ControlBounds(Interval(-2, 2), Interval(-0.5, 0.5))
    contract = BackupContract("graph-static-two-mode-test", domain,
        BicycleParameters(2.5789128, 0.9), limits, VehicleGeometry(2, 1, 0.5),
        0.125, Interval(-20, 20), Interval(-4, 4), gate_front_x=8,
        options=PicardOptions(max_step_s=0.03125))
    controller = SampledFeedbackLaw("common-hold", RecoveryKind.HOLD_BEFORE_GATE,
        (0.0, 0.0), ZERO_GAIN, (0.0,) * 6, limits)
    open_atom = SupportAtom("hidden-open", state, mode=(("rule", "open"),))
    closed_atom = SupportAtom("hidden-closed", state, mode=(("rule", "closed"),))
    # The lexical IDs intentionally route distinguishing observations to
    # singleton cells, while silence must retain the joint support.
    open_cell = BeliefCell("A_open", (open_atom,))
    closed_cell = BeliefCell("B_closed", (closed_atom,))
    joint = BeliefCell("Z_joint", (open_atom, closed_atom))
    skeletons = (open_cell, closed_cell, joint)
    store = LocalEvidenceStore(contract)
    cells = []
    for cell in skeletons:
        if cell.cell_id == "Z_joint":
            cover = {"hidden-open": ("silence", "seen_open"),
                     "hidden-closed": ("silence", "seen_closed")}
        else:
            cover = {cell.atoms[0].atom_id: ("silence",)}
        result = synthesize_backup(cell, (controller,), skeletons, store, cover)
        assert result.status == "SYNTHESIZED_LOCAL", result.attempts
        cells.append(replace(cell, actions=result.actions))
    graph = build_backup_graph(cells, store)
    return graph, joint, open_cell, closed_cell


def executor(fixture, **kwargs):
    graph, joint, _, _ = fixture
    return BackupExecutor(graph, "Z_joint", joint,
                          expected_contract_digest=graph.contract_digest, **kwargs)


def test_real_proof_fixed_point_is_closed_and_silence_does_not_split_hidden_modes(graph_fixture):
    graph, _, _, _ = graph_fixture
    assert graph.invariant.retained_cell_ids == ("A_open", "B_closed", "Z_joint")
    assert graph.full_support_certified is False
    assert graph.invariant.certified is False
    assert dict(graph.node_map["Z_joint"].observation_children) == {
        "seen_closed": "B_closed", "seen_open": "A_open", "silence": "Z_joint"}
    for node in graph.nodes:
        posterior = {}
        sources = {a.atom_id: a for a in node.cell.atoms}
        for tr in node.action.transitions:
            assert graph.evidence.verify(EvidenceContext(node.cell, sources[tr.source_atom_id], node.action, tr))
            record = graph.evidence.records[tr.evidence_ref]
            assert record["proof"]["segments"]
            assert record["proof"]["status"] == "VALIDATED"
            for branch in tr.branches:
                posterior.setdefault(branch.observation, []).extend(branch.atoms)
        for observation, child_id in node.observation_children:
            assert child_id in graph.node_map
            assert support_subset_cell(posterior[observation], graph.node_map[child_id].cell)
    silence = [branch.atoms[0] for tr in graph.node_map["Z_joint"].action.transitions
               for branch in tr.branches if branch.observation == "silence"]
    assert {a.mode_dict["rule"] for a in silence} == {"open", "closed"}
    assert not support_subset_cell(silence, graph.node_map["A_open"].cell)
    assert not support_subset_cell(silence, graph.node_map["B_closed"].cell)


def test_save_load_replays_real_proofs_and_requires_trusted_contract_for_execution(graph_fixture, tmp_path):
    graph, joint, _, _ = graph_fixture
    path = tmp_path / "backup.json"
    save_backup_graph(graph, path)
    restored = load_backup_graph(path, expected_contract_digest=graph.contract_digest)
    assert restored.invariant.retained_cell_ids == graph.invariant.retained_cell_ids
    assert restored.contract_digest == graph.contract_digest
    assert len(restored.evidence.records) == 4
    run = BackupExecutor(restored, "Z_joint", joint,
                         expected_contract_digest=graph.contract_digest)
    assert run.command((0,) * 6, at_time=0) == (0.0, 0.0)
    assert run.advance("silence", joint, at_time=Q(1, 8)) == "Z_joint"
    with pytest.raises(ValueError, match="current contract"):
        load_backup_graph(path, expected_contract_digest="another-scene")


@pytest.mark.parametrize("change", ["law", "node_child", "action_control", "source", "proof", "contract", "assurance"])
def test_serialized_graph_tampering_is_rejected_by_replay(graph_fixture, tmp_path, change):
    graph, _, _, _ = graph_fixture
    path = tmp_path / "backup.json"
    save_backup_graph(graph, path)
    data = json.loads(path.read_text())
    if change == "law":
        next(iter(data["evidence"]["laws"].values()))["bias"][0] = 1
    elif change == "node_child":
        joint_node = next(n for n in data["nodes"] if n["cell_id"] == "Z_joint")
        joint_node["observation_children"] = [["silence", "A_open"]]
    elif change == "action_control":
        data["cells"][0]["actions"][0]["control"][0] = 1
    elif change == "source":
        data["cells"][0]["atoms"][0]["ego"][0] = [1, 1]
    elif change == "proof":
        record = next(iter(data["evidence"]["records"].values()))
        record["proof"]["endpoint"][3] = [4, 4]
    elif change == "contract":
        data["evidence"]["contract"]["gate_front_x"] = 7
    else:
        data["full_support_certified"] = True
    with pytest.raises(ValueError):
        load_backup_graph(data, expected_contract_digest=graph.contract_digest)


def test_execution_branches_only_after_received_observation_then_repeats_hold(graph_fixture):
    graph, joint, open_cell, _ = graph_fixture
    run = executor(graph_fixture)
    assert run.cell_id == "Z_joint" and run.time == 0
    assert run.command((0,) * 6, at_time=0) == (0.0, 0.0)
    assert run.cell_id == "Z_joint"
    assert run.advance("silence", joint, at_time=Q(1, 8)) == "Z_joint"
    assert run.command((0,) * 6, at_time=Q(1, 8)) == (0.0, 0.0)
    assert run.advance("seen_open", open_cell, at_time=Q(1, 4)) == "A_open"
    assert run.command((0,) * 6, at_time=Q(1, 4)) == (0.0, 0.0)
    assert run.advance("silence", open_cell, at_time=Q(3, 8)) == "A_open"
    assert run.time == Q(3, 8) and run.next_time == Q(1, 2)
    assert run.lost is False


def test_public_law_is_identical_for_different_hidden_support_modes(graph_fixture):
    graph, _, open_cell, closed_cell = graph_fixture
    commands = []
    for support in (open_cell, closed_cell):
        run = BackupExecutor(graph, "Z_joint", support,
                             expected_contract_digest=graph.contract_digest)
        commands.append(run.command((0,) * 6, at_time=0))
    assert commands == [(0.0, 0.0), (0.0, 0.0)]


@pytest.mark.parametrize("observation", ["unexpected_report", "", None, []])
def test_unknown_or_invalid_observation_loses_evidence_without_default_child(graph_fixture, observation):
    _, joint, _, _ = graph_fixture
    run = executor(graph_fixture)
    run.command((0,) * 6, at_time=0)
    with pytest.raises(BackupExecutionError):
        run.advance(observation, joint, at_time=Q(1, 8))
    assert run.lost is True
    with pytest.raises(BackupExecutionError, match="already lost"):
        run.command((0,) * 6, at_time=run.time)


def test_posterior_must_fit_both_observation_branch_and_retained_child(graph_fixture):
    _, joint, _, closed_cell = graph_fixture
    run = executor(graph_fixture)
    run.command((0,) * 6, at_time=0)
    # 'seen_open' stored branch contains only open mode, even though closed
    # mode is in the source joint support and has its own valid graph node.
    with pytest.raises(BackupExecutionError, match="outside"):
        run.advance("seen_open", closed_cell, at_time=Q(1, 8))
    assert run.lost
    assert run.cell_id == "Z_joint"


def test_posterior_geometry_outside_propagated_support_is_rejected(graph_fixture):
    _, joint, _, _ = graph_fixture
    run = executor(graph_fixture)
    run.command((0,) * 6, at_time=0)
    displaced = replace(joint, atoms=tuple(replace(a, ego=replace(a.ego, px=Interval.point(0.5)))
                                          for a in joint.atoms))
    with pytest.raises(BackupExecutionError, match="outside"):
        run.advance("silence", displaced, at_time=Q(1, 8))
    assert run.lost


@pytest.mark.parametrize("measurement", [(1, 0, 0, 0, 0, 0), (0,) * 5, (math.nan, 0, 0, 0, 0, 0)])
def test_out_of_domain_or_invalid_measurements_latch_loss(graph_fixture, measurement):
    run = executor(graph_fixture)
    with pytest.raises(BackupExecutionError):
        run.command(measurement, at_time=0)
    assert run.lost
    with pytest.raises(BackupExecutionError, match="already lost"):
        run.command((0,) * 6, at_time=0)


@pytest.mark.parametrize("bad_time", [Q(1, 16), -1, math.inf, math.nan])
def test_wrong_or_invalid_command_time_latches_loss(graph_fixture, bad_time):
    run = executor(graph_fixture)
    with pytest.raises(BackupExecutionError):
        run.command((0,) * 6, at_time=bad_time)
    assert run.lost


def test_repeated_command_before_observation_is_rejected(graph_fixture):
    run = executor(graph_fixture)
    run.command((0,) * 6, at_time=0)
    with pytest.raises(BackupExecutionError, match="repeated"):
        run.command((0,) * 6, at_time=0)
    assert run.lost


@pytest.mark.parametrize("bad_time", [0, Q(1, 16), Q(1, 4), math.nan])
def test_early_late_or_invalid_observation_time_latches_loss(graph_fixture, bad_time):
    _, joint, _, _ = graph_fixture
    run = executor(graph_fixture)
    run.command((0,) * 6, at_time=0)
    with pytest.raises(BackupExecutionError):
        run.advance("silence", joint, at_time=bad_time)
    assert run.lost


def test_observation_before_command_is_rejected(graph_fixture):
    _, joint, _, _ = graph_fixture
    run = executor(graph_fixture)
    with pytest.raises(BackupExecutionError):
        run.advance("silence", joint, at_time=Q(1, 8))
    assert run.lost


def test_initial_contract_mismatch_unretained_node_and_support_escape_are_rejected(graph_fixture):
    graph, joint, open_cell, closed_cell = graph_fixture
    with pytest.raises(BackupExecutionError, match="contract"):
        BackupExecutor(graph, "Z_joint", joint, expected_contract_digest="unrelated")
    with pytest.raises(BackupExecutionError, match="not retained"):
        BackupExecutor(graph, "absent", joint, expected_contract_digest=graph.contract_digest)
    with pytest.raises(BackupExecutionError, match="outside"):
        BackupExecutor(graph, "A_open", closed_cell, expected_contract_digest=graph.contract_digest)


@pytest.mark.parametrize("change", ["record", "law_removed", "law_value", "contract"])
def test_mutated_cached_evidence_or_law_fails_before_command(graph_fixture, change):
    graph, _, _, _ = graph_fixture
    run = executor(graph_fixture)
    node = graph.node_map["Z_joint"]
    if change == "record":
        graph.evidence.records[node.action.transitions[0].evidence_ref]["reserve_lower"] += 0.5
    elif change == "law_removed":
        graph.evidence.laws.pop(node.controller_ref)
    elif change == "law_value":
        graph.evidence.laws[node.controller_ref] = replace(graph.evidence.laws[node.controller_ref], bias=(1, 0))
    else:
        graph.evidence.contract = replace(graph.evidence.contract, gate_front_x=7)
    with pytest.raises(BackupExecutionError):
        run.command((0,) * 6, at_time=0)
    assert run.lost


def test_contract_change_between_command_and_observation_is_rejected(graph_fixture):
    graph, joint, _, _ = graph_fixture
    run = executor(graph_fixture)
    run.command((0,) * 6, at_time=0)
    graph.evidence.contract = replace(graph.evidence.contract, gate_front_x=7)
    with pytest.raises(BackupExecutionError, match="contract changed"):
        run.advance("silence", joint, at_time=Q(1, 8))
    assert run.lost


def test_forged_node_law_cannot_execute_under_different_action_proof(graph_fixture):
    graph, joint, _, _ = graph_fixture
    original = graph.node_map["Z_joint"]
    rogue = replace(graph.evidence.laws[original.controller_ref], name="different-command", bias=(1, 0))
    graph.evidence.laws[rogue.digest] = rogue
    forged = replace(graph, nodes=tuple(replace(n, controller_ref=rogue.digest)
                                       if n.cell.cell_id == "Z_joint" else n for n in graph.nodes))
    with pytest.raises(BackupExecutionError):
        run = BackupExecutor(forged, "Z_joint", joint, expected_contract_digest=graph.contract_digest)
        run.command((0,) * 6, at_time=0)


def test_forged_in_memory_child_table_is_rejected_by_graph_rebuild(graph_fixture):
    graph, joint, _, _ = graph_fixture
    forged = replace(graph, nodes=tuple(replace(n, observation_children=(("silence", "A_open"),))
                                       if n.cell.cell_id == "Z_joint" else n for n in graph.nodes))
    with pytest.raises(BackupExecutionError, match="graph replay"):
        BackupExecutor(forged, "Z_joint", joint, expected_contract_digest=graph.contract_digest)


def test_physical_brake_to_zero_then_stationary_self_loop_is_a_closed_two_node_graph(graph_fixture):
    old_graph, _, _, _ = graph_fixture
    limits = ControlBounds(Interval(-4, 4), Interval(-0.5, 0.5))
    contract = replace(old_graph.evidence.contract, decision_period_s=0.25,
                       control_limits=limits)
    brake = SampledFeedbackLaw("finish-brake", RecoveryKind.BRAKE_TO_STOP,
        (4.0, 0.0), ZERO_GAIN, (0.0,) * 6, limits)
    hold = SampledFeedbackLaw("stationary-hold", RecoveryKind.HOLD_BEFORE_GATE,
        (0.0, 0.0), ZERO_GAIN, (0.0,) * 6, limits)
    source = SupportAtom("braking", StateBounds.point([0, 0, 0, 0.125, -1, 0]),
                         mode=(("rule", "closed"),))
    checked = validate_feedback_step(source, brake, contract)
    assert checked.status == "VALIDATED_LOCAL", checked.reason
    assert checked.endpoint.v == checked.endpoint.a == Interval.point(0)
    # This exact trajectory has v(t)=2*(t-.25)^2 >= 0. No velocity clamp,
    # nonzero stopping tolerance, or automatic standstill mode is involved.
    terminal = SupportAtom("stopped", checked.endpoint, mode=source.mode)
    stop_cell = BeliefCell("A_stopped", (terminal,))
    brake_cell = BeliefCell("Z_braking", (source,))
    store = LocalEvidenceStore(contract)
    stop_result = synthesize_backup(stop_cell, (hold,), (stop_cell,), store,
                                    {"stopped": ("hold",)})
    brake_result = synthesize_backup(brake_cell, (brake,), (stop_cell,), store,
                                     {"braking": ("stopped",)})
    assert stop_result.status == brake_result.status == "SYNTHESIZED_LOCAL"
    graph = build_backup_graph((replace(stop_cell, actions=stop_result.actions),
                                replace(brake_cell, actions=brake_result.actions)), store)
    assert graph.invariant.retained_cell_ids == ("A_stopped", "Z_braking")
    run = BackupExecutor(graph, "Z_braking", brake_cell,
                         expected_contract_digest=contract.digest)
    assert run.command((0, 0, 0, 0.125, -1, 0), at_time=0) == (4.0, 0.0)
    assert run.advance("stopped", stop_cell, at_time=Q(1, 4)) == "A_stopped"
    measured_px = terminal.ego.px.lo
    assert run.command((measured_px, 0, 0, 0, 0, 0), at_time=Q(1, 4)) == (0.0, 0.0)
    assert run.advance("hold", stop_cell, at_time=Q(1, 2)) == "A_stopped"
    assert run.lost is False
