"""A59/1b-0: exact *declared* hybrid event partition / information gate.

This module does not propagate a physical reachable tube or prove that its
finite clock worlds exhaust nature. It builds an obligation table that a
future Picard + protocol Post must discharge on EVERY resulting subinterval.
No hidden rule event creates a distinguishable observation automatically.
"""
from __future__ import annotations
from dataclasses import dataclass
from fractions import Fraction as Q
from .a60_clock_resource import ClockEvent, audit_clock_events

PUBLIC_KINDS = frozenset({'RECEIPT','PUBLIC_OBSERVATION'})
ACTUATION_KINDS = frozenset({'COMMAND','ACK'})
MOTION_RELEVANT_KINDS = frozenset({'EXT_ONSET','RULE_EFFECTIVE','COMMAND','ACK'})


@dataclass(frozen=True)
class ClockWorld:
    world_id: str
    events: tuple[ClockEvent, ...]
    # Explicit association to observation tokens, never from hidden event id.
    public_tokens: tuple[tuple[str,str], ...] = ()
    declared_complete: bool = False
    public_history_id: str = ''  # all worlds in one belief node must share this
    def __post_init__(self):
        if not isinstance(self.world_id,str) or not self.world_id:
            raise ValueError('explicit nonempty hidden world id required')
        if type(self.declared_complete) is not bool:
            raise TypeError('clock support-completeness declaration must be boolean')
        if not isinstance(self.public_history_id,str):
            raise TypeError('public history identity must be a string')
        if any(not isinstance(e,ClockEvent) for e in self.events):
            raise TypeError('typed events required')
        if len(set(e.event_id for e in self.events if e.kind in PUBLIC_KINDS)) != len([e for e in self.events if e.kind in PUBLIC_KINDS]):
            raise ValueError('duplicate public event id')
        toks=dict(self.public_tokens)
        if len(toks)!=len(self.public_tokens) or any(not isinstance(k,str) or not k or not isinstance(v,str) or not v for k,v in self.public_tokens):
            raise ValueError('unique explicit public observation token assignment required')
        if any(k not in {e.event_id for e in self.events if e.kind in PUBLIC_KINDS} for k in toks):
            raise ValueError('observation token references nonpublic event')


@dataclass(frozen=True)
class AtomicClockSlab:
    start: Q
    end: Q
    events_at_start: tuple[tuple[str,str], ...]   # (world_id, event kind)
    obligations: tuple[str, ...]


@dataclass(frozen=True)
class HybridClockGate:
    status: str
    reasons: tuple[str, ...]
    slabs: tuple[AtomicClockSlab, ...]
    # Each key is a *public* history of (observation time, observation token),
    # never a hidden state id. All compatible worlds are retained in the group.
    posterior_worlds: tuple[tuple[tuple[tuple[Q,str], ...],tuple[str,...]], ...]
    # For each slab's START, keep only public events already delivered.
    # The terminal posterior_worlds above must NEVER be used for earlier control.
    posterior_worlds_by_slab: tuple[tuple[Q,Q,tuple[tuple[tuple[tuple[Q,str], ...],tuple[str,...]], ...]], ...] = ()
    certified: bool = False


def partition_clock_worlds(worlds: tuple[ClockWorld,...], *, start: Q, end: Q,
                           history_events: tuple[ClockEvent,...] = (),
                           require_ack_for_command: bool = True) -> HybridClockGate:
    """Right-continuous rational-time event partition over all declared worlds.

    Common open-loop control is mandatory until a public observation arrives.
    This routine DOES NOT itself assign a policy, update authority/guards, or
    certify full support; it emits per-slab obligations and public groupings.
    """
    worlds=tuple(worlds)
    if type(start) is not Q or type(end) is not Q or not 0<=start<end:
        raise ValueError('exact clock interval required')
    if not worlds or any(not isinstance(w,ClockWorld) for w in worlds) or len({w.world_id for w in worlds})!=len(worlds):
        raise ValueError('unique nonempty joint clock world support required')
    if type(require_ack_for_command) is not bool:raise TypeError('ack policy must be boolean')
    reasons=[];times={start,end};post={}; all_events=[]
    if not all(w.public_history_id for w in worlds):
        reasons.append('MISSING_INITIAL_PUBLIC_HISTORY_ID')
    if len({w.public_history_id for w in worlds})!=1:
        reasons.append('INCOMPATIBLE_INITIAL_PUBLIC_HISTORIES')
    for w in worlds:
        times.update(e.time for e in w.events if start<e.time<end)
        all_events.extend(w.events)
    boundaries=tuple(sorted(times))
    for w in worlds:
        report=audit_clock_events(w.events,start=start,end=end,
                     split_times=boundaries[1:-1],history_events=history_events,
                     complete=w.declared_complete)
        reasons.extend(w.world_id+':'+r for r in report.reasons)
        public={}
        for e in w.events:
            if e.kind in PUBLIC_KINDS:
                tok=dict(w.public_tokens).get(e.event_id)
                if tok is None:
                    reasons.append(w.world_id+':PUBLIC_EVENT_WITHOUT_OBSERVATION_TOKEN:'+e.event_id)
                else:
                    public[(e.time,tok)]=True
            if require_ack_for_command and e.kind=='COMMAND':
                if not any(a.kind=='ACK' and a.event_id==e.event_id
                           and a.correlated_id==e.correlated_id and a.time>=e.time
                           for a in w.events):
                    reasons.append(w.world_id+':MISSING_ACTUATION_ACK:'+e.event_id)
        sig=tuple(sorted(public))
        post.setdefault(sig,[]).append(w.world_id)
    slabs=[];post_by_slab=[]
    for lo,hi in zip(boundaries,boundaries[1:]):
        prefix={}
        for w in worlds:
            # Right-continuous: receipts delivered exactly at lo are observable
            # for controls selected at lo, but not in preceding slabs.
            sig=tuple(sorted((e.time,dict(w.public_tokens)[e.event_id])
                for e in w.events if e.kind in PUBLIC_KINDS
                and e.time<=lo and e.event_id in dict(w.public_tokens)))
            prefix.setdefault(sig,[]).append(w.world_id)
        post_by_slab.append((lo,hi,tuple((sig,tuple(sorted(ids)))
            for sig,ids in sorted(prefix.items()))))
        starting=tuple(sorted((w.world_id,e.kind) for w in worlds
                              for e in w.events if e.time==lo))
        obligations=('APPLY_RIGHT_CONTINUOUS_RULE_AND_CONTROLLER_STATE_AT_START',
                     'SEGMENT_PICARD_EGO_AND_ALL_ACTOR_TUBES',
                     'CHECK_SWEPT_RESOURCE_ENTRY_STAY_EXIT_AND_CONFLICT',
                     'PROPAGATE_HIDDEN_SUPPORT_WITHOUT_PREMATURE_OBSERVATION')
        slabs.append(AtomicClockSlab(lo,hi,starting,obligations))
    return HybridClockGate('CONDITIONAL_EXACT_MODEL_HYBRID_PARTITION_READY'
                           if not reasons else 'UNKNOWN',tuple(sorted(set(reasons))),tuple(slabs),
                           tuple((sig,tuple(sorted(ids))) for sig,ids in sorted(post.items())),
                           tuple(post_by_slab),False)


def audit_multiresource_conflicts(*, regions, conflict_pairs, actor_slices,
                                  complete_resource_graph: bool,
                                  complete_actor_roster: bool):
    """Fail-closed rectangular MAY-occupancy conflict screen on declared slabs.

    actor_slices is a sequence of (start,end, {actor_id: SweptFootprint});
    the caller must provide continuous enclosing footprints, never samples.
    This is an additional necessary condition, NOT general polygons/topology.
    """
    from .resources import ResourceRegion,rectangular_separated
    from .footprint import SweptFootprint
    issues=[]
    if type(complete_resource_graph) is not bool or not complete_resource_graph:
        issues.append('RESOURCE_CONFLICT_GRAPH_UNPROVEN_COMPLETE')
    if type(complete_actor_roster) is not bool or not complete_actor_roster:
        issues.append('ACTOR_ROSTER_UNPROVEN_COMPLETE')
    if not isinstance(regions,dict) or not regions or any(not isinstance(r,ResourceRegion) or k!=r.resource_id for k,r in regions.items()):
        raise ValueError('complete typed resource regions required')
    conflicts=tuple(conflict_pairs)
    if any(len(p)!=2 or p[0]==p[1] or any(k not in regions for k in p) for p in conflicts):
        raise ValueError('valid explicit resource conflict edges required')
    if not actor_slices:raise ValueError('nonempty physical slabs required')
    last=None;roster=None
    for lo,hi,fps in actor_slices:
        if type(lo) is not Q or type(hi) is not Q or not lo<hi or (last is not None and lo!=last):
            issues.append('MISSING_OR_DISCONTIGUOUS_RESOURCE_SLABS')
        last=hi
        if not isinstance(fps,dict) or not fps:raise ValueError('full per-slab footprint dictionary required')
        if roster is not None and set(fps)!=roster:issues.append('ACTOR_ROSTER_CHANGED_INSIDE_TICK')
        roster=set(fps)
        if any(not isinstance(f,SweptFootprint) or f.start_time!=lo or f.end_time!=hi for f in fps.values()):
            issues.append('FOOTPRINT_TIME_INTERVAL_MISMATCH')
            continue
        for ra,rb in conflicts:
            may_a={i for i,f in fps.items() if not rectangular_separated(f,regions[ra])}
            may_b={i for i,f in fps.items() if not rectangular_separated(f,regions[rb])}
            if any(i!=j for i in may_a for j in may_b):
                issues.append('POSSIBLE_CONFLICTING_DISTINCT_ACTORS:'+ra+':'+rb)
    return {'status':'CONDITIONAL_DECLARED_RECTANGULAR_CONFLICT_SCREEN_PASS' if not issues else 'UNKNOWN',
            'reasons':tuple(sorted(set(issues))), 'certified':False,
            'scope':'DECLARED_RECTANGULAR_RESOURCE_OUTER_ENCLOSURES_ONLY'}
