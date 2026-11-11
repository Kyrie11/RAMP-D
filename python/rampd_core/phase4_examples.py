"""Small deterministic Phase 4 fixtures used by tests and validation.

These examples are deliberately finite and synthetic.  They exercise the
three-valued verifier and the real resource/agent interfaces without claiming
that a learned motion predictor or a simulator supplies a proof.
"""
from __future__ import annotations

from fractions import Fraction as Q
from .agents import OtherAgentModel, validate_agent_model
from .belief import BeliefCell, SupportAtom
from .footprint import VehicleGeometry, SweptFootprint
from .full_verifier import BranchCheck, FullSupportVerifier, FullVerifierContract, VerifyStatus
from .interval import Interval
from .model import BicycleParameters, ControlBounds, StateBounds
from .observations import ObservationModel
from .protocol import CausalStage, ClockTrace, ProtocolAutomaton, ProtocolState, ProtocolTransition, TimeWindow
from .resources import ActorFootprint, ResourceRegion, ResourceState, ResourceStatus, check_resources


def _clock(t=1):
    return ClockTrace(TimeWindow(Q(t), Q(t)))


def _atom():
    return SupportAtom("ego0", StateBounds.point([0, 0, 0, 0, 0, 0]))


def _automaton(observation="silence", *, guard="always"):
    transition = ProtocolTransition("step", "start", "terminal",
        (("external", CausalStage.EXTERNAL),), _clock(1), observation,
        silence=(observation == "silence"), guard_tag=guard)
    return ProtocolAutomaton((ProtocolState("start"), ProtocolState("terminal")),
                             "start", (transition,))


def _agent_model():
    return OtherAgentModel("other", StateBounds.point([0, 0, 0, 0, 0, 0]),
                           VehicleGeometry(2, 1, .5), BicycleParameters(2.5, .9),
                           ControlBounds(Interval(-1, 1), Interval(-.1, .1)),
                           tuple(Interval.point(0) for _ in range(6)), (1.0, 0.0))


def make_verifier(kind="certified"):
    atom = _atom()
    automaton = _automaton(guard="always" if kind != "unknown" else "unknown")
    target = BeliefCell("terminal", (atom,), policy_node_id="terminal")
    contract = FullVerifierContract(automaton, ObservationModel(("silence",)), (atom,),
                                    targets=(target,), terminal_state_ids=("terminal",),
                                    policy_digest="phase4-example-policy",
                                    model_digest=_agent_model().digest)

    def branch(task, transition, action):
        if kind == "counterexample":
            return BranchCheck(VerifyStatus.COUNTEREXAMPLE, "synthetic collision witness",
                               (atom,), {"transition_id": transition.transition_id,
                                         "state_id": task.state_id, "replayable": True})
        if kind == "unknown":
            return BranchCheck(VerifyStatus.CERTIFIED, "unused; guard remains unknown", (atom,))
        probe = resource_and_agent_probe()
        if probe["resource_status"] != ResourceStatus.SAFE.value or probe["agent_tube_status"] != "VALIDATED":
            return BranchCheck(VerifyStatus.UNKNOWN, "resource or agent tube unresolved")
        return BranchCheck(VerifyStatus.CERTIFIED, "synthetic swept tube replay", (atom,))

    def replay(task, transition, action, candidate):
        return bool(candidate.counterexample and candidate.counterexample.get("replayable"))

    def terminal(task):
        return BranchCheck(VerifyStatus.CERTIFIED, "terminal support invariant")

    return FullSupportVerifier(contract, branch_checker=branch,
                               terminal_checker=terminal, counterexample_checker=replay)


def resource_and_agent_probe():
    """Call the resource and bounded-response interfaces for acceptance logs."""
    region = ResourceRegion("lane", Interval(10, 11), Interval(-1, 1), 1)
    state = ResourceState("lane", True, True, "forward", 1)
    actor = ActorFootprint("ego", SweptFootprint(StateBounds.point([0, 0, 0, 0, 0, 0]),
                                                   VehicleGeometry(2, 1, .5), Q(0), Q(1)),
                           direction="forward")
    resource = check_resources((state,), (region,), (actor,))
    agent = _agent_model()
    valid, reason = validate_agent_model(agent)
    tube = agent.reachable(Q(1, 8), ego_control=ControlBounds(Interval.point(0), Interval.point(0)))
    return {"resource_status": resource.status.value, "resource_reason": resource.reason,
            "agent_model_valid": valid, "agent_model_reason": reason,
            "agent_tube_status": tube.status.value, "agent_tube_segments": len(tube.segments)}


def run_examples():
    out = {}
    for kind in ("certified", "counterexample", "unknown"):
        out[kind] = make_verifier(kind).verify().to_dict()
    out["interfaces"] = resource_and_agent_probe()
    return out
