from fractions import Fraction as Q
from dataclasses import replace

import pytest

from rampd_core.protocol import (
    CausalStage, ClockTrace, EffectiveInterval, MessageSpec, ProtocolAutomaton,
    ProtocolState, ProtocolTransition, TimeWindow, branch_temporal_status,
    silence_knowledge_status,
)
from rampd_core.resources import (
    ActorFootprint, ResourceRegion, ResourceState, ResourceStatus, OccupancyStatus,
    occupancy, check_resources,
)
from rampd_core.agents import OtherAgentModel
from rampd_core.model import BicycleParameters, ControlBounds, StateBounds
from rampd_core.interval import Interval
from rampd_core.footprint import VehicleGeometry, SweptFootprint
from rampd_core.reachability import PicardOptions
from rampd_core.belief import SupportAtom
from rampd_core.observations import ObservationModel
from rampd_core.full_verifier import (
    BranchCheck, FullSupportVerifier, FullVerifierContract, VerifyStatus,
)


def clocks(t, *, received=False):
    if not received:
        window = TimeWindow(Q(t), Q(t))
        # A silence branch is publicly routable in this synthetic fixture only
        # because local sensing is explicitly declared at the same instant.
        return ClockTrace(window, local=window)
    return ClockTrace(TimeWindow(Q(t), Q(t)), TimeWindow(Q(t), Q(t)),
                      TimeWindow(Q(t) + Q(1, 10), Q(t) + Q(1, 10)),
                      TimeWindow(Q(t) + Q(1, 5), Q(t) + Q(1, 5)),
                      (("issue", "receipt"), ("receipt", "local")))


def make_message(t=1):
    return MessageSpec("rule-change", 1, "controller", "sha256:rule",
                       EffectiveInterval(Q(t), Q(t + 2)), clocks(t, received=True), True)


def test_four_clocks_and_silence_do_not_create_knowledge():
    silence = ProtocolTransition("quiet", "s0", "s1",
                                 (("external", CausalStage.EXTERNAL),), clocks(0),
                                 "silence", silence=True, guard_tag="always")
    assert branch_temporal_status(silence)[0] == "PROVED"
    assert silence_knowledge_status(silence)[0] == "UNKNOWN"
    explicit = ProtocolTransition("quiet-guaranteed", "s0", "s1",
                                  (("external", CausalStage.EXTERNAL),), clocks(0),
                                  "silence", silence=True, guard_tag="always",
                                  silence_exclusion_proved=True)
    assert silence_knowledge_status(explicit)[0] == "PROVED"


def test_message_clock_order_requires_explicit_relation():
    branch = ProtocolTransition("m", "s0", "s1",
                                (("external", CausalStage.EXTERNAL),
                                 ("message", CausalStage.MESSAGE_OBSERVATION)),
                                clocks(1, received=True), "received", make_message(),
                                guard_tag="always")
    assert branch_temporal_status(branch) == ("PROVED", "CLOCK_RELATIONS_PROVED")
    bad = ClockTrace(TimeWindow(Q(1), Q(1)), TimeWindow(Q(2), Q(2)),
                     TimeWindow(Q(1), Q(1)), None, ())
    bad_branch = ProtocolTransition("bad", "s0", "s1",
                                    (("message", CausalStage.MESSAGE_OBSERVATION),), bad,
                                    "received", replace(make_message(), clocks=bad), guard_tag="always")
    assert branch_temporal_status(bad_branch)[0] == "UNKNOWN"


def _actor(x0=0.0):
    state = StateBounds.point([x0, 0, 0, 0, 0, 0])
    return ActorFootprint("ego", SweptFootprint(state, VehicleGeometry(2, 1, .5), Q(0), Q(1)))


def test_resource_boundary_contact_is_not_proved_free():
    region = ResourceRegion("r", Interval(1, 2), Interval(-1, 1), capacity=1)
    item = occupancy(_actor(0), region)
    assert item.status is OccupancyStatus.MAYBE_OCCUPIED
    state = ResourceState("r", True, True, "forward", 1)
    assert check_resources((state,), (region,), (_actor(0),)).status is ResourceStatus.UNKNOWN


def test_declared_inside_cannot_be_discharged_by_disjoint_geometry():
    region = ResourceRegion("r", Interval(10, 11), Interval(-1, 1), capacity=1)
    state = ResourceState("r", True, True, "forward", 1)
    actor = ActorFootprint("ego", SweptFootprint(
        StateBounds.point([0, 0, 0, 0, 0, 0]), VehicleGeometry(2, 1, .5), Q(0), Q(1)),
        direction="forward", already_inside=("r",))
    item = occupancy(actor, region)
    assert item.status is OccupancyStatus.MAYBE_OCCUPIED
    assert "DECLARED_INSIDE" in item.reason
    result = check_resources((state,), (region,), (actor,))
    assert result.status is ResourceStatus.UNKNOWN
    assert any("GEOMETRY_INCONSISTENT" in x for x in result.unresolved)


def test_possible_occupancy_cannot_be_reported_as_a_proven_direction_or_capacity_violation():
    region = ResourceRegion("r", Interval(-1, 2), Interval(-1, 1), capacity=1)
    # The swept outer AABB overlaps, but it is not a proof that every concrete
    # trajectory occupies the resource.  A bad direction or a closed entry
    # therefore remains UNKNOWN rather than becoming a concrete violation.
    actor = ActorFootprint("ego", SweptFootprint(StateBounds.point([0, 0, 0, 0, 0, 0]),
                                                  VehicleGeometry(2, 1, .5), Q(0), Q(1)),
                           direction="backward")
    state = ResourceState("r", False, True, "forward", 1)
    result = check_resources((state,), (region,), (actor,))
    assert result.status is ResourceStatus.UNKNOWN
    assert "POSSIBLE" in "|".join(result.unresolved)


def test_resource_conflict_checks_cross_resource_occupancy():
    left = ResourceRegion("left", Interval(-2, -1), Interval(-1, 1), capacity=1)
    right = ResourceRegion("right", Interval(1, 2), Interval(-1, 1), capacity=1)
    states = (ResourceState("left", True, True, "forward", 1),
              ResourceState("right", True, True, "forward", 1))
    i = ActorFootprint("i", SweptFootprint(StateBounds.point([-1.5, 0, 0, 0, 0, 0]),
                                            VehicleGeometry(.5, .5, .25), Q(0), Q(1)),
                       direction="forward")
    j = ActorFootprint("j", SweptFootprint(StateBounds.point([1.5, 0, 0, 0, 0, 0]),
                                            VehicleGeometry(.5, .5, .25), Q(0), Q(1)),
                       direction="forward")
    result = check_resources(states, (left, right), (i, j), (("left", "right"),))
    assert result.status is ResourceStatus.UNKNOWN
    assert any("CONFLICT_MAY_OCCUR" in x for x in result.unresolved)


def test_other_agent_response_envelope_expands_with_ego_control():
    model = OtherAgentModel("other", StateBounds.point([0, 0, 0, 0, 0, 0]),
        VehicleGeometry(2, 1, .5), BicycleParameters(2.5, .9),
        ControlBounds(Interval.point(0), Interval.point(0)),
        tuple(Interval.point(0) for _ in range(6)), (1.0, 0.0))
    base = model.response_control(ControlBounds(Interval.point(0), Interval.point(0)))
    widened = model.response_control(ControlBounds(Interval(-1, 1), Interval.point(0)))
    assert base.jerk.lo == base.jerk.hi == 0
    assert widened.jerk.lo < 0 < widened.jerk.hi


def test_full_verifier_certifies_only_with_explicit_branch_and_terminal_evidence():
    atom = SupportAtom("a", StateBounds.point([0, 0, 0, 0, 0, 0]))
    branch = ProtocolTransition("go", "s0", "terminal",
                               (("external", CausalStage.EXTERNAL),), clocks(1),
                               "silence", silence=True, guard_tag="always")
    automaton = ProtocolAutomaton((ProtocolState("s0"), ProtocolState("terminal")),
                                  "s0", (branch,))
    contract = FullVerifierContract(automaton, ObservationModel(("silence",)), (atom,),
                                   terminal_state_ids=("terminal",),
                                   model_digest="synthetic-model-sha256:fixture")
    def check(task, transition, action):
        return BranchCheck(VerifyStatus.CERTIFIED, "tube replay", (atom,))
    verifier = FullSupportVerifier(contract, branch_checker=check,
        terminal_checker=lambda task: BranchCheck(VerifyStatus.CERTIFIED, "terminal invariant"))
    result = verifier.verify()
    assert result.status == VerifyStatus.CERTIFIED


def test_full_verifier_returns_unknown_without_continuous_evidence():
    atom = SupportAtom("a", StateBounds.point([0, 0, 0, 0, 0, 0]))
    branch = ProtocolTransition("go", "s0", "terminal",
                               (("external", CausalStage.EXTERNAL),), clocks(1),
                               "silence", silence=True, guard_tag="always")
    automaton = ProtocolAutomaton((ProtocolState("s0"), ProtocolState("terminal")),
                                  "s0", (branch,))
    result = FullSupportVerifier(FullVerifierContract(automaton, ObservationModel(("silence",)),
        (atom,), terminal_state_ids=("terminal",))).verify()
    assert result.status == VerifyStatus.UNKNOWN
