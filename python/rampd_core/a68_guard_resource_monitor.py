"""A68 conservative *declared* single conflict-zone admission automaton.

Discrete permission semantics and occupancy changes are checked under exact
rational time. Does NOT independently prove that actor footprints truly occupy
the zone or that signal/clearance declarations are physically authoritative.
"""
from __future__ import annotations
from dataclasses import dataclass
from fractions import Fraction as Q

@dataclass(frozen=True)
class ZoneTick:
    time: Q
    command_version: int
    ack_version: int|None
    entry_open: bool
    stay_open: bool
    exit_open: bool
    resource_clear_before: bool
    capacity: int
    occupants: tuple[tuple[str,str], ...]
    def __post_init__(self):
        if type(self.time) is not Q or self.time<0:raise ValueError('exact time')
        if type(self.command_version) is not int or self.command_version<0:raise ValueError('version')
        if self.ack_version is not None and (type(self.ack_version) is not int or self.ack_version<0):
            raise ValueError('ack version')
        if type(self.capacity) is not int or self.capacity<1:raise ValueError('capacity')
        if any(type(getattr(self,k)) is not bool for k in
               ('entry_open','stay_open','exit_open','resource_clear_before')):raise TypeError('literal Guard booleans')
        if any(not isinstance(k,str) or not k or d not in ('A','B') for k,d in self.occupants):
            raise ValueError('typed id and opposing direction A/B')
        if len({k for k,_ in self.occupants})!=len(self.occupants):
            raise ValueError('unique actor ids')


def audit_zone_transitions(ticks:tuple[ZoneTick,...],*,dt:Q,
                           initial_occupants:tuple[tuple[str,str],...]=(),
                           actor_roster_attested:bool=False,
                           controller_authority_attested:bool=False) -> dict:
    if type(dt) is not Q or dt<=0:raise ValueError('positive rational dt')
    if any(not isinstance(t,ZoneTick) for t in ticks):raise TypeError('ZoneTick records required')
    reasons=[]
    if not ticks:reasons.append('NO_REALIZED_ZONE_TICKS')
    if not actor_roster_attested:reasons.append('ACTOR_ROSTER_NOT_ATTESTED')
    if not controller_authority_attested:reasons.append('CONTROLLER_AUTHORITY_NOT_ATTESTED')
    previous=dict(initial_occupants)
    if len(previous)!=len(initial_occupants):raise ValueError('unique initial roster required')
    prior=None
    for tick in ticks:
        here=dict(tick.occupants)
        new=set(here)-set(previous);stays=set(here)&set(previous);leaves=set(previous)-set(here)
        if len(here)>tick.capacity:reasons.append('ZONE_CAPACITY_EXCEEDED')
        if len({d for d in here.values()})>1:reasons.append('OPPOSING_DIRECTIONS_SIMULTANEOUS')
        if any(here[k]!=previous[k] for k in stays):reasons.append('ACTOR_DIRECTION_CHANGED_INSIDE_ZONE')
        if new:
            if not tick.entry_open:reasons.append('ENTRY_GUARD_CLOSED')
            if tick.command_version!=tick.ack_version:reasons.append('ENTRY_WITHOUT_EFFECTIVE_MATCHING_ACK')
            # Exclusive-clearance protocol: no new entrants while prior occupants
            # remain. A separate platoning/capacity policy would need proof.
            if previous or not tick.resource_clear_before:
                reasons.append('NEW_ENTRY_BEFORE_ZONE_CERTIFIABLY_CLEARED')
        if stays and not tick.stay_open:reasons.append('STAY_GUARD_CLOSED')
        if leaves and not tick.exit_open:reasons.append('EXIT_GUARD_CLOSED')
        if tick.resource_clear_before and previous:
            reasons.append('FALSE_PREENTRY_CLEARANCE_WITH_PRIOR_OCCUPANTS')
        if prior is not None:
            if tick.time-prior.time!=dt:reasons.append('MISSING_OR_NONUNIFORM_TICK')
            if tick.command_version<prior.command_version:reasons.append('RULE_VERSION_ROLLBACK')
            if (tick.ack_version is not None and prior.ack_version is not None and
                tick.ack_version<prior.ack_version):reasons.append('ACK_VERSION_ROLLBACK')
        if tick.ack_version is not None and tick.ack_version>tick.command_version:
            reasons.append('FUTURE_ACK')
        prior=tick;previous=here
    return dict(schema='rampd.a68.single_zone_guard_monitor.v1',
                status='CONDITIONAL_DECLARED_ZONE_TRANSITIONS_PASS' if not reasons else 'UNKNOWN',
                reasons=sorted(set(reasons)),tick_count=len(ticks),
                scope='DECLARED_EXCLUSIVE_CLEARANCE_SINGLE_ZONE_DISCRETE_ONLY',
                continuous_occupancy_proven=False,actual_signal_ack_observed=False,
                physical_resource_safe_certified=False,safe_training_labels_allowed=False)
