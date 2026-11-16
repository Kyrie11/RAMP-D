from dataclasses import replace
from fractions import Fraction as Q
import pytest

from rampd_core.protocol import (
    CausalStage, ClockTrace, ProtocolAutomaton, ProtocolState,
    ProtocolTransition, SilenceExclusionEvidence, TimeWindow,
    silence_knowledge_status,
)


def _branch(local_time=3, *, claimed=True):
    clock = ClockTrace(TimeWindow(Q(1), Q(1)), local=TimeWindow(Q(local_time), Q(local_time)))
    return ProtocolTransition("quiet", "s0", "s1", (("external", CausalStage.EXTERNAL),),
                              clock, "silence", silence=True, guard_tag="always",
                              silence_exclusion_proved=claimed)


def _evidence(*, version="v3", publication=True, delivery=True, cutoff=Q(3), delay=Q(1)):
    return SilenceExclusionEvidence(
        "closure-update-42", version, "a" * 64,
        Q(2), delay, cutoff, publication, delivery,
        ((('rule', 'closed'),),),
    )


def test_bare_bool_is_not_replayable_silence_exclusion():
    branch = _branch()
    assert silence_knowledge_status(branch) == ("UNKNOWN", "SILENCE_DEADLINE_EVIDENCE_MISSING")
    assert silence_knowledge_status(replace(branch, silence_exclusion_proved=False))[0] == "UNKNOWN"


def test_rational_deadline_and_protocol_identity_are_version_checked():
    branch = replace(_branch(), silence_evidence=_evidence())
    assert silence_knowledge_status(branch, protocol_version="v3")[0] == "PROVED"
    assert silence_knowledge_status(branch, protocol_version="v2")[0] == "UNKNOWN"
    assert silence_knowledge_status(replace(branch, silence_evidence=_evidence(cutoff=Q(2))))[0] == "UNKNOWN"
    assert silence_knowledge_status(replace(branch, silence_evidence=_evidence(delivery=False)))[0] == "UNKNOWN"
    assert silence_knowledge_status(replace(branch, silence_evidence=_evidence(publication=False)))[0] == "UNKNOWN"
    assert silence_knowledge_status(replace(branch, silence_evidence=_evidence(delay=Q(2))))[0] == "UNKNOWN"
    assert silence_knowledge_status(replace(branch, clocks=ClockTrace(TimeWindow(Q(1), Q(1)))))[0] == "UNKNOWN"


def test_silence_proof_roundtrips_into_automaton_digest():
    branch = replace(_branch(), silence_evidence=_evidence())
    automaton = ProtocolAutomaton((ProtocolState("s0"), ProtocolState("s1")),
                                  "s0", (branch,), version="v3")
    copy = ProtocolAutomaton.from_dict(automaton.to_dict())
    assert copy.digest() == automaton.digest()
    assert copy.transitions[0].silence_evidence == branch.silence_evidence
    assert silence_knowledge_status(copy.transitions[0], protocol_version=copy.version)[0] == "PROVED"
    without_evidence = replace(branch, silence_evidence=None)
    assert ProtocolAutomaton(automaton.states, "s0", (without_evidence,), version="v3").digest() != automaton.digest()


def test_silence_evidence_rejects_invalid_digest_and_negative_time():
    with pytest.raises(ValueError, match="SHA-256"):
        replace(_evidence(), guarantee_contract_sha256="not-a-hash")
    with pytest.raises(ValueError, match="nonnegative"):
        replace(_evidence(), latest_issue_s=Q(-1))
    with pytest.raises(ValueError, match="duplicate excluded"):
        replace(_evidence(), excluded_modes=((('rule', 'closed'),), (('rule', 'closed'),)))
