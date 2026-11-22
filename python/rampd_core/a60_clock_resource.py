"""Phase 6C-A59/1a: fail-closed model-clock and per-slab resource obligations.

The output is a CONDITIONALLY audited finite-model interface, NOT a full
protocol certificate. All times are exact Fractions; a sampled simulator
snapshot does not establish coverage of an inter-sample physical event.
"""
from __future__ import annotations
from dataclasses import dataclass
from fractions import Fraction as Q
from collections import defaultdict

from .footprint import SweptFootprint
from .resources import ResourceRegion, rectangular_separated, strict_rectangular_overlap


@dataclass(frozen=True)
class ClockEvent:
    event_id: str
    kind: str  # EXT_ONSET / RULE_EFFECTIVE / ISSUE / RECEIPT / COMMAND / ACK / PUBLIC_OBSERVATION
    time: Q
    source_ref: str
    correlated_id: str = ''
    domain: str = 'EXACT_MODEL'  # never silently promote reported-onset timestamps

    def __post_init__(self):
        if not all(isinstance(x, str) for x in (self.event_id, self.kind, self.source_ref, self.correlated_id, self.domain)):
            raise TypeError('clock metadata must be strings')
        if not self.event_id or not self.source_ref or type(self.time) is not Q or self.time < 0:
            raise ValueError('clock event requires exact nonnegative model timestamp and provenance')
        if self.kind not in ('EXT_ONSET','RULE_EFFECTIVE','ISSUE','RECEIPT','COMMAND','ACK','PUBLIC_OBSERVATION'):
            raise ValueError('unknown clock event kind')
        if self.domain not in ('EXACT_MODEL','OBSERVED_SIM','EXTERNAL_REPORT','UNKNOWN'):
            raise ValueError('unknown timestamp domain')


@dataclass(frozen=True)
class ObligationAudit:
    status: str
    reasons: tuple[str, ...]
    coverage: tuple[str, ...] = ()
    certified: bool = False


def audit_clock_events(events, *, start: Q, end: Q, split_times=(),
                       history_events=(), complete: bool = False) -> ObligationAudit:
    """Within-tick causality, split event boundaries, evidence domains.

    Does NOT claim exogenous physical onset <= report, and does not infer
    receipt from absent observations. Split boundaries must be explicit.
    """
    if type(start) is not Q or type(end) is not Q or not 0 <= start < end:
        raise ValueError('exact tick interval required')
    if type(complete) is not bool:
        raise TypeError('completeness declaration must be bool')
    splits = tuple(split_times)
    if len(set(splits)) != len(splits) or any(type(t) is not Q or not start < t < end for t in splits):
        raise ValueError('unique exact internal split times required')
    rows = tuple(events)
    history = tuple(history_events)
    if any(not isinstance(e, ClockEvent) for e in rows+history):
        raise TypeError('typed clock events required')
    if any(e.time > start for e in history):
        raise ValueError('clock history must precede current tick')
    reasons = []
    if not complete: reasons.append('INCOMPLETE_CLOCK_EVENT_SUPPORT')
    if any(e.time < start or e.time > end for e in rows):
        reasons.append('EVENT_OUTSIDE_TICK')
    if any(e.domain != 'EXACT_MODEL' for e in rows+history):
        reasons.append('NONMODEL_CLOCK_CANNOT_PROVE_EXACT_EFFECTIVITY')
    ids = set()
    for e in history+rows:
        key = (e.event_id,e.kind,e.correlated_id)
        if key in ids: reasons.append('DUPLICATE_CLOCK_EVENT')
        ids.add(key)
        if e in rows and e.kind in ('EXT_ONSET','RULE_EFFECTIVE','COMMAND','ACK','ISSUE','RECEIPT') and start < e.time < end and e.time not in splits:
            reasons.append('UNSPLIT_INTERNAL_EVENT:'+e.kind)
    by_event = defaultdict(list)
    for e in history+rows: by_event[e.event_id].append(e)
    for eid, group in by_event.items():
        kinds = defaultdict(list)
        for e in group: kinds[e.kind].append(e)
        for downstream, upstream in [('RECEIPT','ISSUE'),('ACK','COMMAND')]:
            for d in kinds[downstream]:
                if not kinds[upstream]:
                    reasons.append('MISSING_CAUSAL_PREDECESSOR:'+eid+':'+upstream)
                elif not any(u.time <= d.time and (not d.correlated_id or u.correlated_id == d.correlated_id)
                             for u in kinds[upstream]):
                    reasons.append('INVALID_CAUSAL_ORDER_OR_ID:'+eid+':'+downstream)
        # An external report's timestamp never counts as a verified physical onset.
    return ObligationAudit('CONDITIONAL_EXACT_MODEL_CLOCK_PASS' if not reasons else 'UNKNOWN',
                           tuple(sorted(set(reasons))),tuple(sorted({e.kind for e in rows})))


@dataclass(frozen=True)
class ResourceActor:
    actor_id: str
    direction: str
    demand: int
    initial: str  # IN / OUT / UNKNOWN (proven initial body-resource occupancy)
    def __post_init__(self):
        if not self.actor_id or not self.direction or type(self.demand) is not int or self.demand <= 0 or self.initial not in ('IN','OUT','UNKNOWN'):
            raise ValueError('invalid actor occupancy witness')


@dataclass(frozen=True)
class ResourceSlice:
    start: Q
    end: Q
    footprints: tuple[tuple[str, SweptFootprint], ...]
    def __post_init__(self):
        if type(self.start) is not Q or type(self.end) is not Q or not 0 <= self.start < self.end:
            raise ValueError('strict exact slab times required')
        if not self.footprints or len(dict(self.footprints)) != len(self.footprints):
            raise ValueError('unique complete per-slab footprints required')
        if any(not isinstance(f, SweptFootprint) or f.start_time != self.start or f.end_time != self.end
                   for _, f in self.footprints):
            raise ValueError('footprints must cover exactly the slab')


@dataclass(frozen=True)
class ResourcePermission:
    resource_id: str
    alpha: bool
    beta: bool
    exit_open: bool
    directions: tuple[str, ...]
    capacity: int
    demand_unit: int = 1
    def __post_init__(self):
        if not self.resource_id or any(type(x) is not bool for x in (self.alpha,self.beta,self.exit_open)) or not self.directions:
            raise ValueError('separate entry, stay and exit permissions required')
        if len(set(self.directions)) != len(self.directions) or type(self.capacity) is not int or self.capacity < 0 or type(self.demand_unit) is not int or self.demand_unit < 1:
            raise ValueError('invalid direction/capacity')


def audit_resource_transition(region: ResourceRegion, permission: ResourcePermission,
                              actors: tuple[ResourceActor, ...], slabs: tuple[ResourceSlice, ...], *,
                              complete_roster: bool, exact_tick_boundaries: bool) -> ObligationAudit:
    """Proof rules for declared rectangular physical resources and continuous tubes.

    Counts every MAY intersecting actor against capacity. For closed alpha,
    an incumbent may remain only when it is PROVED inside the resource for
    every slab (otherwise exit+reentry remains possible). All uncertain
    intersections are UNKNOWN, never silently interpreted as legal travel.
    """
    if not isinstance(region,ResourceRegion) or not isinstance(permission,ResourcePermission) or region.resource_id != permission.resource_id:
        raise ValueError('resource contract mismatch')
    actors=tuple(actors); slabs=tuple(slabs)
    if not actors or len({a.actor_id for a in actors})!=len(actors) or any(not isinstance(a,ResourceActor) for a in actors):
        raise ValueError('unique explicit roster required')
    if not slabs or any(not isinstance(s, ResourceSlice) for s in slabs):
        raise ValueError('nonempty physical subslabs required')
    reasons=[]
    if type(complete_roster) is not bool or not complete_roster: reasons.append('UNPROVEN_ACTOR_ROSTER_COMPLETENESS')
    if type(exact_tick_boundaries) is not bool or not exact_tick_boundaries: reasons.append('RESOURCE_SWITCH_MAY_OCCUR_INSIDE_SLAB')
    ever_free = {a.actor_id: False for a in actors}
    for k,s in enumerate(slabs):
        if k and s.start != slabs[k-1].end: reasons.append('RESOURCE_SLAB_GAP_OR_OVERLAP')
        fps=dict(s.footprints)
        if set(fps)!={a.actor_id for a in actors}: reasons.append('INCOMPLETE_RESOURCE_FOOTPRINT_ROSTER')
        may_load=0
        for a in actors:
            f=fps.get(a.actor_id)
            if f is None: continue
            free=rectangular_separated(f,region)
            must=not free and strict_rectangular_overlap(f,region)
            if not free:
                if a.demand % permission.demand_unit: reasons.append('CAPACITY_UNIT_NOT_DIVISIBLE:'+a.actor_id)
                may_load+=(a.demand+permission.demand_unit-1)//permission.demand_unit
                if a.direction not in permission.directions:reasons.append('FORBIDDEN_DIRECTION_POSSIBLE:'+a.actor_id)
                if not permission.beta: reasons.append('STAY_OR_CLEAR_CLOSED_POSSIBLE:'+a.actor_id)
                if not permission.alpha:
                    # Initial incumbent staying continuously inside is legal
                    # only when each slab makes occupancy certain.
                    if a.initial!='IN' or not must or ever_free[a.actor_id]:
                        reasons.append('ENTRY_CLOSED_REENTRY_NOT_EXCLUDED:'+a.actor_id)
                if not permission.exit_open and not must:
                    reasons.append('EXIT_CLOSED_CLEARANCE_NOT_EXCLUDED:'+a.actor_id)
            else:
                ever_free[a.actor_id] = True
                if a.initial == 'IN' and not permission.exit_open:
                    reasons.append('EXIT_CLOSED_CROSSING_POSSIBLE:'+a.actor_id)
        if may_load>min(region.capacity,permission.capacity):
            reasons.append('CAPACITY_EXCEEDED_POSSIBLE')
    if region.capacity != permission.capacity or region.demand_unit != permission.demand_unit:
        reasons.append('RESOURCE_CAPACITY_CONTRACT_MISMATCH')
    # Missing initial evidence is material whenever body occupancy is possible.
    if any(a.initial=='UNKNOWN' for a in actors):
        reasons.append('UNKNOWN_INITIAL_OCCUPANCY')
    return ObligationAudit('CONDITIONAL_RESOURCE_SLAB_GATE_PASS' if not reasons else 'UNKNOWN',
                           tuple(sorted(set(reasons))),tuple(f'{s.start}:{s.end}' for s in slabs))


def conditional_a59_1_bridge(rank_screen, resource_audit: ObligationAudit,
                              clock_audit: ObligationAudit) -> ObligationAudit:
    """Conjunction only; never upgrades conditional rank to certified SC."""
    if not isinstance(resource_audit,ObligationAudit) or not isinstance(clock_audit,ObligationAudit):
        raise TypeError('typed audits required')
    reasons=list(resource_audit.reasons)+list(clock_audit.reasons)
    if getattr(rank_screen,'status',None)!='CONDITIONAL_PHYSICAL_RANK_PREDECESSOR_CANDIDATE' or getattr(rank_screen,'certified',True):
        reasons.append('NATIVE_RANK_SCREEN_NOT_CONDITIONAL_PASS')
    if resource_audit.status!='CONDITIONAL_RESOURCE_SLAB_GATE_PASS':reasons.append('RESOURCE_GATE_NOT_PASS')
    if clock_audit.status!='CONDITIONAL_EXACT_MODEL_CLOCK_PASS':reasons.append('CLOCK_GATE_NOT_PASS')
    return ObligationAudit('CONDITIONAL_A59_1_SUBGATE_CANDIDATE' if not reasons else 'UNKNOWN',
                           tuple(sorted(set(reasons))),
                           ('NATIVE_RANK','RECTANGULAR_RESOURCE_SLABS','MODEL_CLOCK'))


def audit_native_resource_tubes(parents, tubes, *, ego_geometry,
                                resource: ResourceRegion, permissions_by_parent,
                                directions_by_actor, complete_roster: bool):
    """Derive resource slabs FROM replay-validated Native Tube and actor envelopes.

    This avoids caller-supplied point snapshots being mistaken for continuous
    occupancy. Geometry is still rectangular and actor model support declared.
    The upstream native dynamic protocol, tail, observation relation and real
    physical model completeness remain outside this conditional check.
    """
    from .a57_native_guard import NativeParent
    from .a53b_actor_envelope import propagate_other
    from .a5_replay_bridge import _subslab_box
    from .certificate import to_dict, replay_certificate
    from .reachability import TubeStatus
    from .footprint import VehicleGeometry
    parents=tuple(parents)
    if (not parents or len({p.atom.atom_id for p in parents})!=len(parents) or
        not all(isinstance(p,NativeParent) for p in parents) or
        not isinstance(ego_geometry,VehicleGeometry) or not isinstance(resource,ResourceRegion)):
        raise TypeError('typed parents, vehicle and resource required')
    if set(tubes)!={p.atom.atom_id for p in parents} or set(permissions_by_parent)!={p.atom.atom_id for p in parents}:
        return ObligationAudit('UNKNOWN',('NATIVE_RESOURCE_PARENT_EVIDENCE_MISMATCH',))
    if set(directions_by_actor)!={'ego'}|{m.actor_id for p in parents for m in p.actor_models}:
        return ObligationAudit('UNKNOWN',('NATIVE_RESOURCE_ACTOR_DIRECTION_MISMATCH',))
    reasons=[];coverage=[]
    for parent in parents:
        name=parent.atom.atom_id
        tube=tubes[name]
        if tube.status is not TubeStatus.VALIDATED or not tube.segments or not replay_certificate(to_dict(tube)).ok:
            reasons.append(name+':NATIVE_TUBE_REPLAY_FAILED');continue
        if tube.initial!=parent.atom.ego:
            reasons.append(name+':NATIVE_SOURCE_STATE_MISMATCH');continue
        if tube.segments[0].start_time!=Q(0) or tube.segments[-1].end_time != parent.controller.plan.tick:
            reasons.append(name+':NATIVE_SLAB_TIME_COVERAGE_MISMATCH');continue
        def fps(lo,hi,ego_state):
            x={'ego':SweptFootprint(ego_state,ego_geometry,lo,hi,'ego')}
            z=propagate_other(parent.actor_models,parent.atom,lo,hi)
            for model in parent.actor_models:x[model.actor_id]=model.footprint(z,lo,hi)
            return x
        initial=fps(Q(0),Q(0),parent.atom.ego)
        records=[]
        for aid,one in initial.items():
            state=('OUT' if rectangular_separated(one,resource) else
                   'IN' if strict_rectangular_overlap(one,resource) else 'UNKNOWN')
            records.append(ResourceActor(aid,directions_by_actor[aid],resource.demand_unit,state))
        slabs=[]
        last=Q(0)
        for seg in tube.segments:
            lo,hi=seg.start_time,seg.end_time
            if lo!=last or hi<=lo:
                reasons.append(name+':NATIVE_TIME_GAP');break
            last=hi
            slab=fps(lo,hi,_subslab_box(seg,lo,hi))
            slabs.append(ResourceSlice(lo,hi,tuple(sorted(slab.items()))))
        else:
            result=audit_resource_transition(resource,permissions_by_parent[name],tuple(records),
                            tuple(slabs),complete_roster=complete_roster,exact_tick_boundaries=True)
            reasons.extend(name+':'+why for why in result.reasons)
            coverage.extend(name+':'+x for x in result.coverage)
    return ObligationAudit('CONDITIONAL_RESOURCE_SLAB_GATE_PASS' if not reasons else 'UNKNOWN',
                           tuple(sorted(set(reasons))),tuple(coverage))


def native_sc_predecessor_a59_1(source_cell, parents, control, *,
                                 contract,sc_result,target_cells,params,ego_geometry,
                                 disturbance,resource,queue_a,queue_b,limits,
                                 permissions_by_parent,directions_by_actor,
                                 clock_events=(),clock_complete=False,
                                 complete_actor_roster=False,options=None,max_cases=100000):
    """Run actual native Picard Post, A58 safety, A59 rank and A59/1 obligations.

    A58 still rejects potential resource entry; this stage does NOT circumvent
    that guard and does not yet generate any accepting terminal policy.
    """
    from .a59_sc_predecessor import native_sc_predecessor
    parents=tuple(parents)
    result=native_sc_predecessor(source_cell,parents,control,
                   contract=contract,sc_result=sc_result,target_cells=target_cells,
                   params=params,ego_geometry=ego_geometry,disturbance=disturbance,
                   resource=resource,queue_a=queue_a,queue_b=queue_b,limits=limits,
                   options=options,max_cases=max_cases)
    status,posterior,tubes,audit,screen=result
    start=parents[0].controller.last_tick
    h=parents[0].controller.plan.tick
    events=tuple(clock_events)
    ca=audit_clock_events(events,start=start,end=start+h,complete=clock_complete)
    # Unlike a genuine segmented protocol Post, native_post changes its
    # controller only at the tick boundary. A right-continuous internal rule
    # change must NOT be admitted merely because the clock ledger mentions it.
    if any(start < e.time < start+h for e in events if e.kind in
           ('EXT_ONSET','RULE_EFFECTIVE','COMMAND','ACK','ISSUE','RECEIPT')):
        ca=ObligationAudit('UNKNOWN',tuple(sorted(set(ca.reasons+('UNSUPPORTED_INTERNAL_EVENT_IN_NATIVE_SINGLE_TICK_POST',)))))
    ra=(audit_native_resource_tubes(parents,tubes,ego_geometry=ego_geometry,
                        resource=resource,permissions_by_parent=permissions_by_parent,
                        directions_by_actor=directions_by_actor,complete_roster=complete_actor_roster)
        if tubes else ObligationAudit('UNKNOWN',('NO_NATIVE_TUBES',)))
    return (*result,ra,ca,conditional_a59_1_bridge(screen,ra,ca))
