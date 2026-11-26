"""Exact model-clock support and observation evidence, not a physical clock claim.

A single uncertain permission change may be conservatively compiled to a
schedule for physical replay. Message worlds are explicit finite hypotheses;
no probabilistic truncation or proof of real-world completeness is implied.
"""
from dataclasses import dataclass
from fractions import Fraction as Q
from .permission_schedule import exact, PermissionEpoch, PermissionSchedule


def uncertain_switch_schedule(start, deadline, terminal_off, before, after, lo, hi, source_ref):
    """Right-continuous single switch at any t in [lo,hi]. Pointwise meet.

    before/after are PermissionEpoch templates. Their times are placeholders;
    all actual times are explicit arguments. Result may be stricter than any
    one history. No statement about observation arrival is implied.
    """
    for t in (start,deadline,terminal_off,lo,hi): exact(t)
    if not start<=lo<=hi<=deadline<terminal_off or not source_ref or before.resource_id!=after.resource_id:
        raise ValueError('invalid single-switch clock/scope')
    rid=before.resource_id
    def copy(a,b,e):
        return PermissionEpoch(rid,a,b,e.alpha,e.beta,e.direction,e.capacity,source_ref+'|'+e.source_ref)
    rows=[]
    if start<lo: rows.append(copy(start,lo,before))
    if lo<hi:
        rows.append(PermissionEpoch(rid,lo,hi,before.alpha and after.alpha,before.beta and after.beta,
             before.direction if before.direction==after.direction else 'NO_COMMON_DIRECTION',
             min(before.capacity,after.capacity),source_ref+'|meet|'+before.source_ref+'|'+after.source_ref))
    rows.append(copy(hi,terminal_off,after))
    return PermissionSchedule(start,deadline,(rid,),tuple(rows),version='a53b3-uncertain-single-switch-meet-v1')

@dataclass(frozen=True)
class ClockLabel:
    kind: str
    lower: Q | None
    upper: Q | None
    source_ref: str


def sampled_onset(previous_time, time, previous_present, present, *, complete, source_ref):
    """At least one 0->1 onset in (previous_time,time], not necessarily unique."""
    if not exact(previous_time)<exact(time) or not source_ref or any(type(v) is not bool for v in (previous_present,present,complete)):
        raise ValueError('invalid sample evidence')
    if complete and not previous_present and present:
        return ClockLabel('AT_LEAST_ONE_ONSET_BRACKET',previous_time,time,source_ref)
    return ClockLabel('UNKNOWN',None,None,source_ref)


def receipt_label(issue, cutoff, receipt, *, monitoring_complete, source_ref, confirmed_drop=False):
    """Receipt time on model clock; right-censor only with observed issue and complete monitor.

    A confirmed model drop is distinct; survival includes a possible mass at
    infinity if the channel permits permanent loss.
    """
    exact(cutoff)
    if not source_ref or type(monitoring_complete) is not bool or type(confirmed_drop) is not bool: raise ValueError('missing evidence')
    if issue is not None and exact(issue)>cutoff: raise ValueError('issue after cutoff')
    if confirmed_drop:
        if issue is None or receipt is not None: raise ValueError('drop requires issued, undelivered message')
        return ClockLabel('CONFIRMED_MODEL_DROP',None,None,source_ref)
    if receipt is not None:
        if issue is None or not issue<=exact(receipt)<=cutoff: raise ValueError('receipt outside issued window')
        return ClockLabel('OBSERVED_MODEL_RECEIPT',receipt,receipt,source_ref)
    if issue is not None and monitoring_complete:
        return ClockLabel('RIGHT_CENSORED_RECEIPT',cutoff,None,source_ref)
    return ClockLabel('UNKNOWN',None,None,source_ref)

@dataclass(frozen=True)
class MessageWorld:
    world_id: str
    message_id: str
    payload_ref: str
    issue: Q | None
    receipt: Q | None
    source_ref: str
    def __post_init__(self):
        if not all((self.world_id,self.message_id,self.payload_ref,self.source_ref)): raise ValueError('world and message provenance required')
        if self.issue is not None: exact(self.issue)
        if self.receipt is not None and (self.issue is None or exact(self.receipt)<self.issue): raise ValueError('receipt before issue')
    def observation(self, time):
        exact(time)
        return ('RECEIVED',self.message_id,self.payload_ref,self.receipt) if self.receipt is not None and self.receipt<=time else ('SILENCE',)


def partition_message_worlds(worlds, time):
    """Complete partition of DECLARED alternatives by public cumulative receipt.

    None receipt means no receipt in the modeled trajectory (drop/no issue),
    not a negative label for an unmodeled trajectory. Receipt is the modelled
    publicly timestamped ingress, NOT a hidden physical delivery instant.
    Payload is included only
    after receipt; future receipt and hidden issue do not leak into silence.
    """
    worlds=tuple(worlds); exact(time)
    if not worlds or any(not isinstance(w,MessageWorld) for w in worlds) or len({w.world_id for w in worlds})!=len(worlds):
        raise ValueError('unique nonempty declared worlds required')
    out={}
    for w in worlds: out.setdefault(w.observation(time),[]).append(w.world_id)
    return {k:tuple(v) for k,v in out.items()}
