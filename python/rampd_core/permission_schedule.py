"""A5/3a: absolute-clock, independently declared finite permission schedule.

Half-open epochs [on,off), checked on closed physical step [start,end].
No inferred law, no automatic guard pruning, no real-world completeness claim.
"""
from dataclasses import dataclass, replace
from fractions import Fraction
from .protocol import ProtocolAutomaton, TimeWindow
import hashlib
import json


def exact(t):
    if type(t) is not Fraction or t < 0:
        raise ValueError('nonnegative Fraction time required')
    return t


@dataclass(frozen=True)
class PermissionEpoch:
    resource_id: str
    on: Fraction
    off: Fraction
    alpha: bool
    beta: bool
    direction: str
    capacity: int
    source_ref: str

    def __post_init__(self):
        if not self.resource_id or not self.source_ref or exact(self.off) <= exact(self.on):
            raise ValueError('invalid permission epoch')
        if type(self.alpha) is not bool or type(self.beta) is not bool or not self.direction:
            raise ValueError('explicit permissions and direction required')
        if type(self.capacity) is not int or self.capacity < 0:
            raise ValueError('integer nonnegative capacity required')


@dataclass(frozen=True)
class PermissionSchedule:
    start: Fraction
    deadline: Fraction
    resource_ids: tuple[str, ...]
    epochs: tuple[PermissionEpoch, ...]
    version: str = 'a53-absolute-schedule-v1'

    def __post_init__(self):
        if exact(self.deadline) <= exact(self.start) or not self.version:
            raise ValueError('invalid mission interval')
        ids=tuple(sorted(self.resource_ids)); epochs=tuple(sorted(self.epochs,key=lambda e:(e.resource_id,e.on)))
        if len(set(ids))!=len(ids) or set(ids)!={e.resource_id for e in epochs}:
            raise ValueError('schedule resource coverage mismatch')
        for rid in ids:
            rows=[e for e in epochs if e.resource_id==rid]
            if rows[0].on>self.start or rows[-1].off<=self.deadline or any(a.off!=b.on for a,b in zip(rows,rows[1:])):
                raise ValueError('gap, overlap or missing terminal instant in schedule')
        object.__setattr__(self,'resource_ids',ids); object.__setattr__(self,'epochs',epochs)

    @property
    def digest(self):
        body=[self.version,str(self.start),str(self.deadline),self.resource_ids,
              [(e.resource_id,str(e.on),str(e.off),e.alpha,e.beta,e.direction,e.capacity,e.source_ref) for e in self.epochs]]
        return 'a53-schedule-sha256:'+hashlib.sha256(json.dumps(body,separators=(',',':')).encode()).hexdigest()

    def permission_at(self, t):
        """Right-continuous half-open rule semantics, including mission deadline."""
        if not self.start <= exact(t) <= self.deadline:
            raise ValueError('instant outside absolute mission')
        return {e.resource_id:(e.alpha,e.beta,e.direction,e.capacity)
                for e in self.epochs if e.on<=t<e.off}

    def partition(self, start, end):
        """Closed geometric slabs with interior rule, plus terminal point rule.

        At an internal switch the old rule is conservatively checked at its
        left-limit too. The new rule is ALWAYS checked at the switch instant.
        The last zero-width slab prevents omission of a change exactly at end.
        """
        if not self.start<=exact(start)<exact(end)<=self.deadline:
            raise ValueError('step outside absolute mission')
        cuts=sorted({start,end}|{e.on for e in self.epochs if start<e.on<end})
        return tuple((a,b,self.permission_at(a)) for a,b in zip(cuts,cuts[1:]))+((end,end,self.permission_at(end)),)

    def restrictions(self, start, end):
        """Meet of all permissions on CLOSED [start,end]; may be conservative.

        In particular a closure exactly at end is not missed. A change of
        direction yields no common permitted direction, not an arbitrary one.
        """
        if not self.start<=exact(start)<exact(end)<=self.deadline:
            raise ValueError('step outside absolute mission')
        out={}
        for rid in self.resource_ids:
            rows=[e for e in self.epochs if e.resource_id==rid and e.on<=end and e.off>start]
            directions={e.direction for e in rows}
            out[rid]=(all(e.alpha for e in rows),all(e.beta for e in rows),
                      next(iter(directions)) if len(directions)==1 else 'NO_COMMON_DIRECTION',
                      min(e.capacity for e in rows))
        return out


def local_protocol(protocol: ProtocolAutomaton, modes, start: Fraction, end: Fraction, binding: str):
    """Rebase a time-unrolled protocol without dropping any outgoing branch.

    All outgoing edges of each reached state must belong to this slab. No
    message/pending-awareness/monitor semantics inferred here. A state reused
    at another absolute time with inconsistent clocks must fail closed.
    """
    if exact(end)<=exact(start) or not binding:
        raise ValueError('invalid absolute slab')
    modes=set(modes)
    if not modes or None in modes: raise ValueError('missing protocol mode')
    states={s.state_id:s for s in protocol.states}; transitions=[]
    def shift(w):
        if w is None: return None
        if not start<=w.lo<=w.hi<=end: raise ValueError('event outside absolute slab')
        return TimeWindow(w.lo-start,w.hi-start)
    for mode in sorted(modes):
        outgoing=protocol.outgoing(mode)
        if not outgoing: raise ValueError('missing outgoing absolute branch')
        for t in outgoing:
            if (t.guard_tag!='always' or t.message is not None or t.clocks.issue is not None or
                t.clocks.receipt is not None or t.silence_exclusion_proved or t.silence_evidence is not None or
                any(states[m].mode or states[m].resource_monitor or states[m].received_messages for m in (mode,t.target_state_id))):
                raise ValueError('unsupported dynamic message/guard/monitor')
            # Local observations occur at public boundary; physical event can be earlier.
            if t.clocks.local is None or t.clocks.local.lo!=end or t.clocks.local.hi!=end:
                raise ValueError('public observation not at absolute step boundary')
            transitions.append(replace(t,clocks=replace(t.clocks,change=shift(t.clocks.change),local=shift(t.clocks.local))))
    return ProtocolAutomaton(protocol.states,protocol.initial_state_id,tuple(transitions),
        version=f'a53-local:{protocol.digest()}:{binding}:{start}:{end}')


def partition_family(schedules, start, end):
    """Conservative common-control permissions across all declared hidden branches.

    A family of complete externally declared schedules; no guard inference,
    no endogenous traffic-response or correlation proof. At each exact slab
    use the intersection of admissible permissions, not their union.
    """
    schedules=tuple(schedules)
    if not schedules or any(s.resource_ids!=schedules[0].resource_ids for s in schedules):
        raise ValueError('incompatible or empty schedule family')
    for s in schedules:
        if not s.start<=exact(start)<exact(end)<=s.deadline:
            raise ValueError('step outside schedule family')
    cuts=sorted({start,end}|{e.on for s in schedules for e in s.epochs if start<e.on<end})
    def common(t):
        rows=[s.permission_at(t) for s in schedules]; out={}
        for rid in schedules[0].resource_ids:
            vals=[r[rid] for r in rows]; dirs={v[2] for v in vals}
            out[rid]=(all(v[0] for v in vals),all(v[1] for v in vals),
                      next(iter(dirs)) if len(dirs)==1 else 'NO_COMMON_DIRECTION',min(v[3] for v in vals))
        return out
    return tuple((a,b,common(a)) for a,b in zip(cuts,cuts[1:]))+((end,end,common(end)),)
