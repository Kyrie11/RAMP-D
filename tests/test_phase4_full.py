from fractions import Fraction as Q

from rampd_core.belief import BeliefCell, SupportAtom
from rampd_core.full_verifier import BranchCheck, FullSupportVerifier, FullVerifierContract, VerifyStatus
from rampd_core.phase4_examples import make_verifier, resource_and_agent_probe, run_examples
from rampd_core.model import StateBounds


def test_three_valued_examples_are_distinct_and_replayed():
    result = run_examples()
    assert result["certified"]["status"] == "CERTIFIED"
    assert result["counterexample"]["status"] == "COUNTEREXAMPLE"
    assert result["unknown"]["status"] == "UNKNOWN"
    assert result["interfaces"]["resource_status"] == "SAFE"
    assert result["interfaces"]["agent_model_valid"] is True
    assert result["certified"]["model_digest"].startswith("agent-model-sha256:")


def test_counterexample_without_independent_replay_stays_unknown():
    verifier = make_verifier("counterexample")
    no_replay = FullSupportVerifier(verifier.contract,
        branch_checker=verifier.branch_checker, terminal_checker=verifier.terminal_checker)
    result = no_replay.verify()
    assert result.status == VerifyStatus.UNKNOWN
    assert any("COUNTEREXAMPLE_REPLAY_MISSING" in x for x in result.unresolved)


def test_target_protocol_context_is_bound_to_public_child_state():
    # Reuse the certified fixture, then make the target cell claim a different
    # policy node.  Atom containment alone must not certify it.
    v = make_verifier("certified")
    atom = v.contract.initial_support[0]
    bad_target = BeliefCell("terminal", (atom,), policy_node_id="wrong-context")
    c = FullVerifierContract(v.contract.automaton, v.contract.observations,
                             (atom,), targets=(bad_target,), terminal_state_ids=("terminal",),
                             model_digest=v.contract.model_digest)
    result = FullSupportVerifier(c, branch_checker=v.branch_checker,
        terminal_checker=v.terminal_checker, counterexample_checker=v.counterexample_checker).verify()
    assert result.status == VerifyStatus.UNKNOWN
    assert any("TARGET_PROTOCOL_CONTEXT_MISMATCH" in x for x in result.unresolved)


def test_missing_branch_guard_is_not_a_certified_transition():
    v = make_verifier("certified")
    # The fixture is already strict; changing the callback cannot turn an
    # unknown protocol guard into a proof.
    from dataclasses import replace
    from rampd_core.protocol import ProtocolAutomaton
    bad_transitions = tuple(replace(t, guard_tag="unknown") for t in v.contract.automaton.transitions)
    auto = ProtocolAutomaton(v.contract.automaton.states, v.contract.automaton.initial_state_id,
                             bad_transitions)
    c = replace(v.contract, automaton=auto)
    result = FullSupportVerifier(c, branch_checker=v.branch_checker,
        terminal_checker=v.terminal_checker, counterexample_checker=v.counterexample_checker).verify()
    assert result.status == VerifyStatus.UNKNOWN


def test_silence_cannot_drop_hidden_mode_without_deadline_proof():
    from dataclasses import replace
    from rampd_core.protocol import ProtocolAutomaton
    v = make_verifier("certified")
    source = v.contract.initial_support[0]
    hidden = replace(source, atom_id="hidden", mode=(("rule", "closed"),))
    contract = replace(v.contract, initial_support=(source, hidden))
    # The callback incorrectly keeps only one hidden mode.  FullVerifier must
    # reject it because this silence branch has no publication/delivery proof.
    def bad_branch(task, transition, action):
        return BranchCheck(VerifyStatus.CERTIFIED, "forged", (source,))
    result = FullSupportVerifier(contract, branch_checker=bad_branch,
        terminal_checker=v.terminal_checker,
        counterexample_checker=v.counterexample_checker).verify()
    assert result.status == VerifyStatus.UNKNOWN
    assert any("SILENCE_REMOVES_HIDDEN_HISTORY" in x for x in result.unresolved)


def test_interval_event_cannot_produce_a_concrete_counterexample_at_lower_endpoint():
    from dataclasses import replace
    from rampd_core.protocol import ClockTrace, TimeWindow, ProtocolAutomaton
    v = make_verifier("certified")
    tr = v.contract.automaton.transitions[0]
    interval_tr = replace(tr, clocks=ClockTrace(TimeWindow(Q(1), Q(2))))
    auto = ProtocolAutomaton(v.contract.automaton.states,
                             v.contract.automaton.initial_state_id, (interval_tr,))
    contract = replace(v.contract, automaton=auto)
    def forged_ce(task, transition, action):
        return BranchCheck(VerifyStatus.COUNTEREXAMPLE, "not time-specific", (source,), {"replayable": True})
    source = contract.initial_support[0]
    result = FullSupportVerifier(contract, branch_checker=forged_ce,
        terminal_checker=v.terminal_checker, counterexample_checker=lambda *args: True).verify()
    assert result.status == VerifyStatus.UNKNOWN
    assert any("EVENT_TIME_INTERVAL_REQUIRES_REFINEMENT" in x for x in result.unresolved)


def test_silence_cannot_drop_a_hidden_mode_from_the_posterior():
    v = make_verifier("certified")
    first = v.contract.initial_support[0]
    hidden = SupportAtom("hidden", StateBounds.point([0, 0, 0, 0, 0, 0]), mode=(("rule", "closed"),))
    # Put two hidden modes in the initial support, then return only one mode
    # from the silence branch.  No deadline contract allows this pruning.
    from dataclasses import replace
    c = replace(v.contract, initial_support=(first, hidden))
    result = FullSupportVerifier(c, branch_checker=lambda task, tr, action:
        BranchCheck(VerifyStatus.CERTIFIED, "dropped hidden mode", (first,)),
        terminal_checker=v.terminal_checker).verify()
    assert result.status == VerifyStatus.UNKNOWN
    assert any("SILENCE_REMOVES_HIDDEN_HISTORY" in x for x in result.unresolved)


def test_silence_without_local_observation_clock_stays_unknown():
    """A physical event clock cannot be used as an information clock."""
    from rampd_core.protocol import (CausalStage, ClockTrace, ProtocolAutomaton,
                                     ProtocolState, ProtocolTransition, TimeWindow)
    from rampd_core.observations import ObservationModel
    atom = SupportAtom("a", StateBounds.point([0, 0, 0, 0, 0, 0]))
    transition = ProtocolTransition(
        "quiet", "s0", "terminal", (("external", CausalStage.EXTERNAL),),
        ClockTrace(TimeWindow(Q(1), Q(1))), "silence", silence=True,
        guard_tag="always")
    automaton = ProtocolAutomaton((ProtocolState("s0"), ProtocolState("terminal")),
                                  "s0", (transition,))
    contract = FullVerifierContract(automaton, ObservationModel(("silence",)),
                                   (atom,), terminal_state_ids=("terminal",),
                                   model_digest="synthetic-model-sha256:clock-test")
    result = FullSupportVerifier(
        contract,
        branch_checker=lambda task, tr, action: BranchCheck(
            VerifyStatus.CERTIFIED, "branch", (atom,)),
        terminal_checker=lambda task: BranchCheck(VerifyStatus.CERTIFIED, "terminal"),
    ).verify()
    assert result.status == VerifyStatus.UNKNOWN
    assert any("PUBLIC_OBSERVATION_CLOCK_MISSING" in x for x in result.unresolved)


def test_resource_and_agent_probe_has_no_hidden_data_dependency():
    probe = resource_and_agent_probe()
    assert probe["resource_status"] == "SAFE"
    assert probe["agent_model_reason"] == "MODEL_DECLARED"
