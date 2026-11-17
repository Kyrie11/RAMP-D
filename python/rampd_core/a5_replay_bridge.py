"""A5/1 soundness gate: tie finite protocol branches to replayed physical tubes.

This is a deliberately narrow adapter for constant *open-loop* public controls,
complete finite point-time protocol events, static resources and explicitly
specified physical actor sets. It fails CLOSED on feedback, unknown guard,
time-varying permissions, uncertain observation instants, incomplete branch
support, unproven physical tubes, or unknown swept-footprint separation.

Results remain conditional on declared model/envelope completeness. They are
not full paper RAMP-D certificates, and never assert that callback True alone
establishes safety.
"""
from __future__ import annotations
from dataclasses import dataclass
import hashlib
import json
from fractions import Fraction
from .belief import BeliefCell, SupportAtom
from .invariant import ActionWitness, EvidenceContext, SafeDomain, EvidenceVerdict
from .protocol import (ProtocolAutomaton, branch_temporal_status,
                       public_observation_window)
from .observations import ObservationModel
from .safe_continuation import SCContract, sc_support_digest
from .model import BicycleParameters, ControlBounds, StateBounds
from .interval import Interval
from .exact_time import binary64_bracket
from .reachability import TubeResult, TubeStatus
from .certificate import to_dict as tube_as_dict, replay_certificate
from .footprint import VehicleGeometry, SweptFootprint, separate_tube_results, SeparationStatus
from .resources import ActorFootprint, ResourceState, ResourceRegion, check_resources, ResourceStatus, OccupancyStatus


@dataclass(frozen=True)
class A5ProtocolOutcome:
    """Explicit successor box for one declared protocol transition.

    Must be derived from protocol+physical observation semantics, not from
    the ActionWitness under inspection. One transition may produce multiple
    posterior atoms (but only one public observation label in Phase4 API).
    """
    cell_id: str
    action_id: str
    source_atom_id: str
    transition_id: str
    successors: tuple[SupportAtom, ...]


@dataclass(frozen=True)
class A5World:
    """Explicit declared complete actor/resource lists for a synthetic world.

    The completeness flags are ASSUMPTIONS and must be separately justified
    before applying this bridge to a real scene. Static resource states only.
    """
    model_digest: str
    ego_geometry: VehicleGeometry
    other_actors: tuple[tuple[str, TubeResult, VehicleGeometry], ...]
    regions: tuple[ResourceRegion, ...]
    resource_states: tuple[ResourceState, ...]
    complete_actors_assumed: bool
    complete_resources_assumed: bool
    conflicts: tuple[tuple[str, str], ...] = ()
    model_version: str = 'a5-toy-v3'
    # Explicit problem assumptions, not inferred from the candidate tube.
    ego_params: BicycleParameters | None = None
    ego_disturbance: tuple[Interval, ...] | None = None
    ego_control_bounds: ControlBounds | None = None
    safe_domain: SafeDomain | None = None
    # Independent forward axes in the same world frame as dx/dt, dy/dt.
    resource_forward_axes: tuple[tuple[str, float, float], ...] = ()

    def __post_init__(self):
        for name in ('other_actors', 'regions', 'resource_states', 'conflicts'):
            value = getattr(self, name)
            object.__setattr__(self, name, tuple(tuple(x) for x in value) if name in ('other_actors', 'conflicts') else tuple(value))
        import math
        axes = tuple((rid,float(x),float(y)) for rid,x,y in self.resource_forward_axes)
        if len({rid for rid,_,_ in axes}) != len(axes) or any(
            not rid or not math.isfinite(x) or not math.isfinite(y) or (x==0 and y==0)
            for rid,x,y in axes):
            raise ValueError('invalid or duplicate resource forward axes')
        object.__setattr__(self,'resource_forward_axes',axes)
        if self.ego_disturbance is not None:
            object.__setattr__(self, 'ego_disturbance', tuple(self.ego_disturbance))
        if not self.model_version or len({item[0] for item in self.other_actors}) != len(self.other_actors):
            raise ValueError('valid model digest and unique actor ids required')
        if 'ego' in {item[0] for item in self.other_actors}:
            raise ValueError('ego cannot occur in other actors')
        if not isinstance(self.complete_actors_assumed, bool) or not isinstance(self.complete_resources_assumed, bool):
            raise TypeError('explicit model completeness flags required')


def _canonical_hash(prefix: str, body) -> str:
    return prefix + hashlib.sha256(json.dumps(
        body, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def a5_clock_digest(protocol: ProtocolAutomaton, observations: ObservationModel,
                    step_s: Fraction) -> str:
    """Bind a point-time protocol/observation contract and its step clock."""
    if type(step_s) is not Fraction or step_s <= 0:
        raise ValueError('exact positive fraction step required')
    return _canonical_hash('a5-clock-sha256:', {
        'protocol': protocol.digest(), 'observation': observations.digest(),
        'step': [step_s.numerator, step_s.denominator]})


def a5_world_digest(world: A5World) -> str:
    """Content hash of the declared physical model, not an assurance claim."""
    from dataclasses import asdict
    body = {'model_version':world.model_version,
            'ego_geometry': asdict(world.ego_geometry),
            'other_actors': [(name, tube_as_dict(tube), asdict(geom))
                             for name,tube,geom in sorted(world.other_actors, key=lambda r:r[0])],
            'regions':[(r.resource_id, [r.x.lo.hex(),r.x.hi.hex()],
                         [r.y.lo.hex(),r.y.hi.hex()],r.capacity,r.demand_unit)
                        for r in sorted(world.regions,key=lambda x:x.resource_id)],
            'resource_states':[asdict(s) for s in sorted(world.resource_states,key=lambda x:x.resource_id)],
            'conflicts':sorted(world.conflicts),
            'complete_actors_assumed':world.complete_actors_assumed,
            'complete_resources_assumed':world.complete_resources_assumed,
            'ego_params': None if world.ego_params is None else asdict(world.ego_params),
            'ego_disturbance': None if world.ego_disturbance is None else
                [[v.lo, v.hi] for v in world.ego_disturbance],
            'ego_control_bounds': None if world.ego_control_bounds is None else
                asdict(world.ego_control_bounds),
            'safe_domain': None if world.safe_domain is None else asdict(world.safe_domain),
            'resource_forward_axes':sorted(world.resource_forward_axes)}
    return _canonical_hash('a5-world-sha256:',body)


@dataclass(frozen=True)
class A5PhysicalObligation:
    cell_id: str
    action_id: str
    source_atom_id: str
    evidence_ref: str
    tube: TubeResult

    @classmethod
    def seal(cls, cell_id: str, action_id: str, source_atom_id: str,
             tube: TubeResult, contract: SCContract):
        """Bind the exact tube witness bytes and the finite SC context."""
        ref = _physical_digest(cell_id, action_id, source_atom_id, tube, contract)
        return cls(cell_id, action_id, source_atom_id, ref, tube)


def _physical_digest(cell_id, action_id, source_atom_id, tube, contract):
    body = {'cell': cell_id, 'action': action_id, 'source': source_atom_id,
            'contract': contract.digest, 'tube': tube_as_dict(tube)}
    return 'a5-physical-sha256:' + hashlib.sha256(json.dumps(
        body, sort_keys=True, separators=(',', ':'), allow_nan=False
    ).encode()).hexdigest()


def _state_covered_by_atom(tube_state, atom):
    return atom.ego.contains(tube_state)


def exact_step_endpoint(tube: TubeResult, step_s: Fraction) -> StateBounds:
    """After native replay, enclose x(step_s), not x(round_up(step_s)).

    The complete witness goes to ceil64(step_s). For a non-dyadic time in
    a substep, integrate the already verified derivative enclosure over an
    outward binary64 bracket of the exact elapsed time. The caller must
    replay the tube first. Static constraints are checked over the entire
    (possibly slightly longer) tube; no protocol time is advanced by rounding.
    """
    if step_s <= 0 or tube.requested_horizon_s != binary64_bracket(step_s)[1]:
        raise ValueError('wrong enclosing horizon')
    for seg in tube.segments:
        if seg.start_time <= step_s <= seg.end_time:
            if step_s == seg.end_time:
                return seg.witness.endpoint
            if step_s == seg.start_time:
                return seg.witness.initial
            elapsed = Interval(*binary64_bracket(step_s - seg.start_time))
            box = StateBounds(*(z + elapsed * f for z, f in zip(
                seg.witness.initial.as_tuple(), seg.witness.field)))
            # Both enclosures contain the exact-time state; intersect safely.
            return StateBounds(*(Interval(max(a.lo,b.lo), min(a.hi,b.hi))
                    for a,b in zip(box.as_tuple(), seg.witness.tube.as_tuple())))
    raise ValueError('rational instant not covered')


def replay_a5_physical(ctx: EvidenceContext, contract: SCContract,
                       obligation: A5PhysicalObligation, world: A5World,
                       safe_domain: SafeDomain) -> bool:
    """Replay physical part of one transition, with all assumptions explicit.

    This is NOT sufficient for SC; also use audit_a5_protocol on the *same*
    public action, plus independently verified accepting terminal tails.
    """
    try:
        if (not world.complete_actors_assumed or not world.complete_resources_assumed or
                world.model_digest != contract.model_digest or
                world.model_digest != a5_world_digest(world) or
                ctx.evidence_ref != obligation.evidence_ref or
                obligation.evidence_ref != _physical_digest(
                    obligation.cell_id, obligation.action_id,
                    obligation.source_atom_id, obligation.tube, contract) or
                (ctx.cell.cell_id, ctx.action.action_id, ctx.source_atom.atom_id) !=
                (obligation.cell_id, obligation.action_id, obligation.source_atom_id) or
                ctx.action.controller_ref is not None or
                ctx.source_atom not in ctx.cell.atoms or ctx.action not in ctx.cell.actions or
                ctx.transition not in ctx.action.transitions or
                ctx.transition.source_atom_id != ctx.source_atom.atom_id or
                world.safe_domain is None or safe_domain != world.safe_domain or
                not isinstance(world.ego_params, BicycleParameters) or
                not isinstance(world.ego_control_bounds, ControlBounds) or
                world.ego_disturbance is None or len(world.ego_disturbance) != 6 or
                not all(isinstance(w, Interval) for w in world.ego_disturbance) or
                safe_domain.friction != world.ego_params):
            return False
        tube = obligation.tube
        if (not isinstance(tube, TubeResult) or tube.status is not TubeStatus.VALIDATED or
                tube.endpoint is None or not tube.segments or
                tube.initial != ctx.source_atom.ego or
                tube.requested_horizon_s != binary64_bracket(contract.step_s)[1] or
                tube.validated_until != Fraction.from_float(tube.requested_horizon_s) or
                ctx.source_atom.other or tube.params != world.ego_params or
                len(tube.disturbance) != 6 or
                not all(witness.contains(declared) for witness, declared in
                        zip(tube.disturbance, world.ego_disturbance))):
            return False
        # EXACT held constant control. A wider control box might still be safe
        # physically but would not identify the prescribed public action.
        if tube.control != ControlBounds(Interval.point(ctx.action.control[0]),
                                         Interval.point(ctx.action.control[1])):
            return False
        if not all(bound.contains(value) for bound, value in
                   zip(world.ego_control_bounds.as_tuple(), tube.control.as_tuple())):
            return False
        if not replay_certificate(tube_as_dict(tube)).ok:
            return False
        exact_endpoint = exact_step_endpoint(tube, contract.step_s)
        # Continuous constraint across every piece, not merely at endpoints.
        from dataclasses import replace
        for seg in tube.segments:
            test_atom = replace(ctx.source_atom, ego=seg.witness.tube)
            if not safe_domain.contains_atom(test_atom)[0]:
                return False
        # With no conditional physical propagator in A5/1, each declared
        # successor must conservatively contain the entire endpoint. Checking
        # just one atom per observation can silently lose another hidden mode.
        # This sufficient condition deliberately rejects unproved partitions.
        if ctx.transition.verdict is not EvidenceVerdict.PROVED or not ctx.transition.branches:
            return False
        for branch in ctx.transition.branches:
            if not all(_state_covered_by_atom(exact_endpoint, a) and not a.other
                       and safe_domain.contains_atom(a)[0] for a in branch.atoms):
                return False
        for actor_id, actor_tube, geometry in world.other_actors:
            separation = separate_tube_results(tube, world.ego_geometry,
                                               actor_tube, geometry, 'ego', actor_id)
            if separation.status is not SeparationStatus.SEPARATED:
                return False
        # Full-interval resource occupancy: each state tube is the complete
        # swept footprint over its local time interval, not a sampled point.
        # This initial bridge uses ONLY ego and static regions. If other actors
        # might occupy resources, the full world/resource checker must follow.
        if world.other_actors and world.regions:
            return False
        for seg in tube.segments:
            # A possible occupancy must satisfy a declared world-frame
            # direction, not a direction inferred just from nonnegative speed.
            fp = ActorFootprint('ego', SweptFootprint.from_segment(
                seg, world.ego_geometry, 'ego'), direction='forward')
            res = check_resources(world.resource_states, world.regions, (fp,), world.conflicts)
            if res.status is not ResourceStatus.SAFE:
                return False
            # No entry-versus-stay classification is proved in A5. Any
            # possible occupancy must therefore also satisfy beta, not just
            # alpha (the default check for an actor with empty already_inside).
            states = {state.resource_id: state for state in world.resource_states}
            axes = {rid:(x,y) for rid,x,y in world.resource_forward_axes}
            for o in res.occupancies:
                if o.status is OccupancyStatus.PROVED_FREE:
                    continue
                if not states[o.resource_id].beta or o.resource_id not in axes:
                    return False
                ax, ay = axes[o.resource_id]
                velocity = seg.witness.field[0]*ax + seg.witness.field[1]*ay
                if velocity.lo < 0:
                    return False
        return True
    except (TypeError, ValueError, KeyError, RuntimeError, OverflowError, AttributeError):
        return False


def audit_a5_protocol(cell: BeliefCell, action: ActionWitness, contract: SCContract,
                      protocol: ProtocolAutomaton, observations: ObservationModel,
                      outcomes: tuple[A5ProtocolOutcome, ...]) -> bool:
    """Check all enabled outcomes *of the declared finite protocol*.

    `outcomes` MUST be supplied by an independent protocol/observation
    propagator; this checker only audits correspondence and completeness
    against that model. No hidden-state-specific action or early observation.
    """
    try:
        if (contract.protocol_digest != protocol.digest() or
                contract.clock_digest != a5_clock_digest(protocol, observations, contract.step_s) or
                action not in cell.actions or action.controller_ref is not None):
            return False
        source = {a.atom_id: a for a in cell.atoms}
        transitions = {tr.source_atom_id: tr for tr in action.transitions}
        if len(transitions) != len(action.transitions) or set(transitions) != set(source):
            return False
        edge_by_key = {}
        for out in outcomes:
            if out.cell_id != cell.cell_id or out.action_id != action.action_id or not out.successors:
                return False
            key = (out.source_atom_id, out.transition_id)
            if key in edge_by_key:
                return False
            edge_by_key[key] = out
        required = set()
        for aid, atom in source.items():
            mode = atom.mode_dict.get('protocol_state')
            if mode is None or mode not in {s.state_id for s in protocol.states}:
                return False
            available = protocol.outgoing(mode)
            if not available:
                return False
            expected_by_obs = {}
            for trans in available:
                # Version A5/1 deliberately does not exclude any branch by
                # a caller-supplied string tag, including "false". A later
                # guard-satisfiability proof can add precise exclusions.
                if trans.guard_tag != 'always':
                    return False
                # No mapping from resource-monitor labels to A5World states
                # exists here. Even a constant nonempty monitor cannot be
                # interpreted as a verified static permission assignment.
                if any(s.resource_monitor for s in protocol.states
                       if s.state_id in (mode, trans.target_state_id)):
                    return False
                status, _ = branch_temporal_status(trans)
                window = public_observation_window(trans)
                # Only exact, future public observation moments are supported.
                if (status != 'PROVED' or trans.clocks.change.hi > contract.step_s or
                        any(not trans.clocks.relation_proved(a,b) for a,b in trans.clocks.declared_relations) or window is None or window.lo != window.hi or
                        window.hi != contract.step_s or trans.observation not in observations.allowed_labels):
                    return False
                required.add((aid, trans.transition_id))
                entry = edge_by_key.get((aid, trans.transition_id))
                if entry is None:
                    return False
                for successor in entry.successors:
                    # This narrow adapter has no propagator for additional
                    # hidden coordinates: only the protocol state may change.
                    expected_mode = dict(atom.mode_dict)
                    expected_mode['protocol_state'] = trans.target_state_id
                    if (successor.mode_dict != expected_mode or atom.other or successor.other):
                        return False
                expected_by_obs.setdefault(trans.observation, []).extend(entry.successors)
            if not expected_by_obs:
                return False
            # Same public label across distinct hidden protocol branches must
            # be merged into one support, with no silent dropped atoms.
            tr = transitions[aid]
            if tr.verdict is not EvidenceVerdict.PROVED:
                return False
            actual = {b.observation: b.atoms for b in tr.branches}
            if set(actual) != set(expected_by_obs):
                return False
            for obs, predicted in expected_by_obs.items():
                # Equality of full atom boxes and modes, not ID membership only.
                if (len(predicted) != len(set(a.atom_id for a in predicted)) or
                        {a.atom_id: a for a in predicted} !=
                        {a.atom_id: a for a in actual[obs]} or
                        len(actual[obs]) != len(predicted)):
                    return False
        return set(edge_by_key) == required
    except (ValueError, TypeError, AttributeError, KeyError, OverflowError):
        return False
