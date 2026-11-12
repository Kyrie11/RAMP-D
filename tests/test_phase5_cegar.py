from dataclasses import replace
from fractions import Fraction as Q

import pytest

from rampd_core.belief import BeliefCell, SupportAtom
from rampd_core.cegar import (
    CegarEngine, ContractVersion, CounterexampleKind, EvidenceRegistry,
    MasterProblem,
    QueueItem, RefinementAction, RefinementKind, ResumableVerificationQueue,
    apply_refinement, classify_counterexample, refine_automaton_transition,
    split_observation_cell, split_time_window, default_refinement_selector,
)
from rampd_core.full_verifier import (BranchCheck, FullSupportVerifier, FullVerifierContract,
                                      VerificationResult, VerifyStatus, _public_observation_time)
from rampd_core.observations import ObservationModel
from rampd_core.interval import Interval
from rampd_core.model import StateBounds
from rampd_core.phase4_examples import make_verifier
from rampd_core.protocol import (
    CausalStage, ClockTrace, EffectiveInterval, MessageSpec, ProtocolAutomaton,
    ProtocolState, ProtocolTransition, TimeWindow,
)


def _atom(atom_id="a", px=(0.0, 2.0)):
    return SupportAtom(atom_id, StateBounds(
        Interval(*px), Interval.point(0), Interval.point(0),
        Interval.point(0), Interval.point(0), Interval.point(0)))


def test_replay_separates_concrete_spurious_and_unknown():
    branch = BranchCheck(VerifyStatus.COUNTEREXAMPLE, "candidate", (_atom(),), {"x": 1})
    concrete = classify_counterexample("task", "transition", "action", branch, lambda *args: True)
    spurious = classify_counterexample("task", "transition", "action", branch, lambda *args: False)
    missing = classify_counterexample("task", "transition", "action", branch, None)
    assert concrete.kind is CounterexampleKind.CONCRETE
    assert spurious.kind is CounterexampleKind.SPURIOUS
    assert missing.kind is CounterexampleKind.UNKNOWN


def test_time_split_preserves_closed_union_and_message_clock_binding():
    left, right = split_time_window(TimeWindow(Q(1), Q(3)))
    assert left.lo == Q(1) and left.hi == Q(2)
    assert right.lo == Q(2) and right.hi == Q(3)
    clocks = ClockTrace(TimeWindow(Q(1), Q(3)), TimeWindow(Q(2), Q(4)),
                        TimeWindow(Q(3), Q(5)), TimeWindow(Q(3), Q(5)),
                        (("issue", "receipt"), ("receipt", "local")))
    msg = MessageSpec("m", 1, "rule", "digest", EffectiveInterval(Q(1), Q(6)), clocks)
    tr = ProtocolTransition("t", "s", "z", (("e", CausalStage.EXTERNAL),),
                            clocks, "received", msg, guard_tag="always")
    auto = ProtocolAutomaton((ProtocolState("s"), ProtocolState("z")), "s", (tr,))
    refined = refine_automaton_transition(auto, "t", "change")
    assert {x.transition_id for x in refined.transitions} == {"t.L", "t.R"}
    assert all(x.message is not None and x.message.clocks == x.clocks for x in refined.transitions)
    assert refined.digest() != auto.digest()


def test_support_and_observation_refinement_preserve_nonanticipativity():
    atom = _atom("a", (0.0, 2.0))
    cell = BeliefCell("B", (atom,), actions=(object(),), policy_node_id="history")
    action = RefinementAction(RefinementKind.SUPPORT, "a", "px", "B", "wide tube", atom_id="a", role="master")
    out = apply_refinement(action, automaton=make_verifier("certified").contract.automaton,
                           initial_support=(atom,), targets=(cell,), master_cells=(cell,))
    assert len(out.master_cells) == 1
    assert len(out.master_cells[0].atoms) == 2
    assert out.master_cells[0].policy_node_id == "history"
    assert out.master_cells[0].actions == ()
    obs_children = split_observation_cell(cell, "a", "px", ("left", "right"),
                                          distinguishability_proved=False)
    assert len(obs_children) == 1
    assert obs_children[0].policy_node_id == "history"
    assert obs_children[0].actions == ()


def test_distinguishable_observation_split_creates_explicit_nodes():
    cell = BeliefCell("B", (_atom("a", (0.0, 2.0)),), policy_node_id="history")
    children = split_observation_cell(cell, "a", "px", ("left", "right"),
                                      distinguishability_proved=True)
    assert [c.cell_id for c in children] == ["B|left", "B|right"]
    assert len({c.policy_node_id for c in children}) == 2
    assert all(not c.actions for c in children)


def test_evidence_registry_invalidates_any_semantic_digest_change():
    v1 = ContractVersion("c1", "p1", resource_digest="r1", observation_digest="o1", model_digest="m1")
    registry = EvidenceRegistry(v1)
    ref = registry.register({"support": "a"})
    assert registry.valid(ref)
    invalidated = registry.synchronize(ContractVersion("c1", "p1", resource_digest="r2",
                                                        observation_digest="o1", model_digest="m1"))
    assert invalidated == 1
    assert not registry.valid(ref)
    assert registry.reason(ref) == "CONTRACT_CHANGED"


def test_master_revision_replaces_refined_cells_and_contract():
    cell = BeliefCell("B", (_atom("a", (0.0, 1.0)),), policy_node_id="history")
    master = MasterProblem((cell,), "contract-a")
    refined = BeliefCell("B", (_atom("a.L", (0.0, 0.5)), _atom("a.R", (0.5, 1.0))),
                         policy_node_id="history")
    updated = master.update((refined,), "contract-b")
    assert updated.revision == master.revision + 1
    assert updated.contract_digest == "contract-b"
    assert len(updated.cells[0].atoms) == 2


def test_queue_checkpoint_is_resumable_and_bound_to_contract():
    q = ResumableVerificationQueue("c", generation=2)
    q.push(QueueItem("a", {"state": "s"}, responsibility="time"))
    checkpoint = q.checkpoint()
    restored = ResumableVerificationQueue.from_checkpoint(checkpoint, expected_contract_digest="c",
                                                           expected_generation=2)
    assert restored.pop().task_id == "a"
    with pytest.raises(ValueError, match="digest mismatch"):
        ResumableVerificationQueue.from_checkpoint(checkpoint, expected_contract_digest="different")
    bad = dict(checkpoint)
    bad["pending"] = list(checkpoint["pending"]) * 2
    with pytest.raises(ValueError, match="duplicate pending"):
        ResumableVerificationQueue.from_checkpoint(bad, expected_contract_digest="c")


def test_cegar_engine_refines_support_then_reaches_certified():
    base = make_verifier("certified")
    atom = _atom("ego0", (0.0, 2.0))
    target = BeliefCell("terminal", (atom,), policy_node_id="terminal")
    contract = replace(base.contract, initial_support=(atom,), targets=(target,))

    def factory(current):
        def branch(task, transition, action):
            if any(a.ego.px.hi - a.ego.px.lo > 1.0 for a in task.support):
                return BranchCheck(VerifyStatus.UNKNOWN, "support too wide")
            return BranchCheck(VerifyStatus.CERTIFIED, "refined support", task.support)
        return FullSupportVerifier(current, branch_checker=branch,
                                   terminal_checker=lambda task: BranchCheck(
                                       VerifyStatus.CERTIFIED, "terminal"))

    selector = lambda result: RefinementAction(
        RefinementKind.SUPPORT, "support:ego0", "px", "initial", "spurious tube", atom_id="ego0")
    engine = CegarEngine(contract, factory, refinement_selector=selector, max_iterations=3)
    result = engine.run()
    assert result.status == VerifyStatus.CERTIFIED
    assert result.iterations == 2
    assert len(result.refinements) == 1
    assert result.refinements[0].evidence_invalidated == 0
    assert result.queue_checkpoint["contract_digest"] == result.contract_digest


def test_received_branch_routes_after_receipt_and_local_observation():
    atom = _atom("a", (0.0, 0.0))
    clocks = ClockTrace(TimeWindow(Q(1), Q(1)), TimeWindow(Q(1), Q(1)),
                        TimeWindow(Q(2), Q(2)), TimeWindow(Q(3), Q(3)),
                        (("issue", "receipt"), ("receipt", "local")))
    msg = MessageSpec("m", 1, "rule", "digest", EffectiveInterval(Q(1), Q(5)), clocks)
    transition = ProtocolTransition("receive", "start", "terminal",
                                    (("external", CausalStage.EXTERNAL),
                                     ("message", CausalStage.MESSAGE_OBSERVATION)),
                                    clocks, "received", msg, guard_tag="always")
    automaton = ProtocolAutomaton((ProtocolState("start"), ProtocolState("terminal")),
                                  "start", (transition,))
    target = BeliefCell("terminal", (atom,), policy_node_id="terminal")
    contract = FullVerifierContract(automaton, ObservationModel(("received", "silence")),
                                    (atom,), targets=(target,), terminal_state_ids=("terminal",),
                                    model_digest="synthetic-model")
    observed = []
    verifier = FullSupportVerifier(
        contract,
        branch_checker=lambda task, tr, action: BranchCheck(VerifyStatus.CERTIFIED, "ok", (atom,)),
        terminal_checker=lambda task: (observed.append(task.time) or
                                       BranchCheck(VerifyStatus.CERTIFIED, "terminal")),
    )
    assert verifier.verify().status == VerifyStatus.CERTIFIED
    assert observed == [Q(3)]


def test_nonpoint_public_observation_time_stays_unknown():
    atom = _atom("a", (0.0, 0.0))
    clocks = ClockTrace(TimeWindow(Q(1), Q(1)), TimeWindow(Q(1), Q(1)),
                        TimeWindow(Q(2), Q(2)), TimeWindow(Q(3), Q(4)),
                        (("issue", "receipt"), ("receipt", "local")))
    msg = MessageSpec("m", 1, "rule", "digest", EffectiveInterval(Q(1), Q(5)), clocks)
    transition = ProtocolTransition("receive", "start", "terminal",
                                    (("external", CausalStage.EXTERNAL),
                                     ("message", CausalStage.MESSAGE_OBSERVATION)),
                                    clocks, "received", msg, guard_tag="always")
    automaton = ProtocolAutomaton((ProtocolState("start"), ProtocolState("terminal")),
                                  "start", (transition,))
    contract = FullVerifierContract(automaton, ObservationModel(("received", "silence")),
                                    (atom,), terminal_state_ids=("terminal",),
                                    model_digest="synthetic-model")
    result = FullSupportVerifier(
        contract,
        branch_checker=lambda task, tr, action: BranchCheck(VerifyStatus.CERTIFIED, "ok", (atom,)),
    ).verify()
    assert result.status == VerifyStatus.UNKNOWN
    assert any("PUBLIC_OBSERVATION_TIME_INTERVAL_REQUIRES_REFINEMENT" in x
               for x in result.unresolved)


def test_received_branch_uses_receipt_local_time_when_change_is_interval():
    atom = _atom("a", (0.0, 0.0))
    clocks = ClockTrace(TimeWindow(Q(1), Q(3)), TimeWindow(Q(1), Q(1)),
                        TimeWindow(Q(2), Q(2)), TimeWindow(Q(3), Q(3)),
                        (("issue", "receipt"), ("receipt", "local")))
    msg = MessageSpec("m", 1, "rule", "digest", EffectiveInterval(Q(1), Q(5)), clocks)
    transition = ProtocolTransition("receive", "start", "terminal",
                                    (("external", CausalStage.EXTERNAL),
                                     ("message", CausalStage.MESSAGE_OBSERVATION)),
                                    clocks, "received", msg, guard_tag="always")
    automaton = ProtocolAutomaton((ProtocolState("start"), ProtocolState("terminal")),
                                  "start", (transition,))
    target = BeliefCell("terminal", (atom,), policy_node_id="terminal")
    contract = FullVerifierContract(
        automaton, ObservationModel(("received",)), (atom,), targets=(target,),
        terminal_state_ids=("terminal",), model_digest="synthetic-model")
    verifier = FullSupportVerifier(
        contract,
        interval_branch_checker=lambda *_args: BranchCheck(VerifyStatus.CERTIFIED, "whole-window", (atom,)),
        terminal_checker=lambda task: BranchCheck(VerifyStatus.CERTIFIED, "terminal"),
    )
    result = verifier.verify()
    assert result.status == VerifyStatus.CERTIFIED


def test_default_selector_refines_nonpoint_public_clock():
    result = type("Result", (), {
        "unresolved": (
            "receive:PUBLIC_OBSERVATION_TIME_INTERVAL_REQUIRES_REFINEMENT:receipt",
        )
    })()
    action = default_refinement_selector(result)
    assert action is not None
    assert action.kind is RefinementKind.EVENT_TIME
    assert action.target_id == "receive"
    assert action.clock_name == "receipt"


def test_public_clock_responsibility_uses_name_not_equal_window_value():
    clocks = ClockTrace(TimeWindow(Q(1), Q(3)), TimeWindow(Q(1), Q(3)),
                        TimeWindow(Q(1), Q(3)), None,
                        (("issue", "receipt"),))
    msg = MessageSpec("m", 1, "rule", "digest", EffectiveInterval(Q(1), Q(5)), clocks)
    transition = ProtocolTransition("receive", "start", "terminal",
                                    (("external", CausalStage.EXTERNAL),
                                     ("message", CausalStage.MESSAGE_OBSERVATION)),
                                    clocks, "received", msg, guard_tag="always")
    assert _public_observation_time(transition) == (
        None, "PUBLIC_OBSERVATION_TIME_INTERVAL_REQUIRES_REFINEMENT:receipt")


def test_verifier_callback_exception_is_fail_closed_unknown():
    base = make_verifier("certified")

    def exploding_branch(*_args):
        raise RuntimeError("synthetic evidence failure")

    result = FullSupportVerifier(base.contract, branch_checker=exploding_branch,
                                 terminal_checker=base.terminal_checker).verify()
    assert result.status == VerifyStatus.UNKNOWN
    assert any("BRANCH_CHECKER_EXCEPTION:RuntimeError" in x for x in result.unresolved)


def test_verifier_rejects_malformed_support_fail_closed():
    base = make_verifier("certified")
    result = FullSupportVerifier(
        base.contract,
        branch_checker=lambda *_args: BranchCheck(VerifyStatus.CERTIFIED, "bad support", (object(),)),
        terminal_checker=base.terminal_checker,
    ).verify()
    assert result.status == VerifyStatus.UNKNOWN
    assert any("BRANCH_CHECKER_INVALID_SUPPORT" in x for x in result.unresolved)


def test_counterexample_replay_exception_is_fail_closed_unknown():
    base = make_verifier("counterexample")

    def exploding_replay(*_args):
        raise RuntimeError("synthetic replay failure")

    result = FullSupportVerifier(
        base.contract,
        branch_checker=base.branch_checker,
        terminal_checker=base.terminal_checker,
        counterexample_checker=exploding_replay,
    ).verify()
    assert result.status == VerifyStatus.UNKNOWN
    assert any("COUNTEREXAMPLE_REPLAY_ERROR:RuntimeError" in x
               for x in result.unresolved)


def test_cegar_verifier_exception_requeues_outer_task():
    base = make_verifier("certified")

    def exploding_factory(_contract):
        raise RuntimeError("synthetic verifier failure")

    engine = CegarEngine(base.contract, exploding_factory, max_iterations=1)
    result = engine.run()
    assert result.status == VerifyStatus.UNKNOWN
    assert result.reason == "VERIFIER_EXCEPTION:RuntimeError"
    checkpoint = result.queue_checkpoint
    assert checkpoint["inflight"] is None
    assert [row["task_id"] for row in checkpoint["pending"]] == ["root"]


def test_cegar_rejects_invalid_verifier_status_fail_closed():
    base = make_verifier("certified")

    class InvalidVerifier:
        def verify(self):
            return VerificationResult("NOT_A_STATUS", "scope", "bad", 0, 0)

    engine = CegarEngine(base.contract, lambda _contract: InvalidVerifier(), max_iterations=1)
    result = engine.run()
    assert result.status == VerifyStatus.UNKNOWN
    assert result.reason == "VERIFIER_INVALID_STATUS"
    assert result.queue_checkpoint["inflight"] is None


def test_verification_budget_changes_contract_digest():
    base = make_verifier("certified")
    changed = replace(base.contract, max_tasks=base.contract.max_tasks + 1)
    assert changed.digest != base.contract.digest


def test_cegar_rejects_queue_generation_mismatch():
    base = make_verifier("certified")
    registry = EvidenceRegistry(ContractVersion(base.contract.digest, "p", generation=2))
    queue = ResumableVerificationQueue(base.contract.digest, generation=1)
    with pytest.raises(ValueError, match="generation mismatch"):
        CegarEngine(base.contract, lambda _contract: base, registry=registry, queue=queue)
