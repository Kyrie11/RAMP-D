from fractions import Fraction as Q

from rampd_core.protocol import (
    CausalStage, ClockTrace, EffectiveInterval, MessageSpec,
    ProtocolAutomaton, ProtocolState, ProtocolTransition, TimeWindow,
    branch_temporal_status, public_observation_window,
)


def _message_transition(receipt_time):
    clocks = ClockTrace(
        change=TimeWindow(Q(1), Q(1)),
        issue=TimeWindow(Q(2), Q(2)),
        receipt=TimeWindow(Q(receipt_time), Q(receipt_time)),
        local=None,
        declared_relations=(("issue", "receipt"),),
    )
    message = MessageSpec(
        "rule-v2", 2, "authority", "sha256:rule-v2",
        EffectiveInterval(Q(1), Q(20)), clocks, delivery_guaranteed=True,
    )
    return ProtocolTransition(
        f"change-receipt-{receipt_time}", "known-v1", "known-v2",
        (("external", CausalStage.EXTERNAL),
         ("message", CausalStage.MESSAGE_OBSERVATION)),
        clocks, "message_received", message, guard_tag="always",
    )


def test_hidden_rule_change_before_current_time_remains_possible_until_receipt():
    delayed = _message_transition(5)
    already_observed = _message_transition(2)
    automaton = ProtocolAutomaton(
        (ProtocolState("known-v1"), ProtocolState("known-v2")),
        "known-v1", (delayed, already_observed),
    )
    # Both physical changes happened at t=1, before the current public time t=3.
    # The t=5 message is still pending and must remain in hidden support; the
    # t=2 receipt is already public and must not be re-enumerated.
    remaining = automaton.enumerate_successors("known-v1", at_time=Q(3))
    assert tuple(x.transition_id for x in remaining) == (delayed.transition_id,)


def test_local_detection_and_message_receipt_are_independent_observation_clocks():
    clocks = ClockTrace(
        change=TimeWindow(Q(1), Q(1)),
        issue=TimeWindow(Q(4), Q(4)),
        receipt=TimeWindow(Q(6), Q(6)),
        local=TimeWindow(Q(2), Q(2)),
        declared_relations=(("issue", "receipt"),),
    )
    message = MessageSpec(
        "late-report", 1, "authority", "sha256:late",
        EffectiveInterval(Q(1), Q(10)), clocks,
    )
    message_branch = ProtocolTransition(
        "message", "s0", "s1", (("message", CausalStage.MESSAGE_OBSERVATION),),
        clocks, "message_receipt", message, guard_tag="always",
    )
    assert branch_temporal_status(message_branch)[0] == "PROVED"
    assert public_observation_window(message_branch) == clocks.receipt

    local_branch = ProtocolTransition(
        "local", "s0", "s2", (("external", CausalStage.EXTERNAL),),
        clocks, "local_detection", message=None, guard_tag="always",
    )
    assert public_observation_window(local_branch) == clocks.local
    automaton = ProtocolAutomaton(
        (ProtocolState("s0"), ProtocolState("s1"), ProtocolState("s2")),
        "s0", (message_branch, local_branch),
    )
    # At t=3, the local observation at t=2 is already public, but the message
    # receipt at t=6 is still pending. They are not forced into one max-clock.
    remaining = automaton.enumerate_successors("s0", at_time=Q(3))
    assert tuple(x.transition_id for x in remaining) == ("message",)
