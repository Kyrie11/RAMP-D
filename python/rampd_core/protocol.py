"""Explicit finite protocol semantics for Phase 4.

The protocol layer enumerates allowed branches.  It never infers that a
physical change is known merely because it happened, and it keeps change,
issue, receipt, and local-observation clocks separate.  A branch whose clock
ordering is not proved is usable for exploration but must produce ``UNKNOWN``
in the full verifier.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum
from fractions import Fraction
import hashlib
import json


class CausalStage(IntEnum):
    EXTERNAL = 0
    FLOW_TRIGGER = 1
    INTERACTION = 2
    AGENT_RESPONSE = 3
    MESSAGE_OBSERVATION = 4


@dataclass(frozen=True, order=True)
class TimeWindow:
    lo: Fraction
    hi: Fraction

    def __post_init__(self):
        lo, hi = Fraction(self.lo), Fraction(self.hi)
        if lo < 0 or hi < lo:
            raise ValueError("invalid nonnegative time window")
        object.__setattr__(self, "lo", lo)
        object.__setattr__(self, "hi", hi)

    def contains(self, t):
        t = Fraction(t)
        return self.lo <= t <= self.hi

    def to_dict(self):
        return {"lo": [self.lo.numerator, self.lo.denominator],
                "hi": [self.hi.numerator, self.hi.denominator]}

    @classmethod
    def from_dict(cls, value):
        return cls(Fraction(*value["lo"]), Fraction(*value["hi"]))


@dataclass(frozen=True)
class ClockTrace:
    """Independent windows for the four protocol clocks."""

    change: TimeWindow
    issue: TimeWindow | None = None
    receipt: TimeWindow | None = None
    local: TimeWindow | None = None
    declared_relations: tuple[tuple[str, str], ...] = ()

    def __post_init__(self):
        names = {"change", "issue", "receipt", "local"}
        rel = tuple((str(a), str(b)) for a, b in self.declared_relations)
        if any(a not in names or b not in names or a == b for a, b in rel):
            raise ValueError("invalid clock relation")
        if len(set(rel)) != len(rel):
            raise ValueError("duplicate clock relation")
        object.__setattr__(self, "declared_relations", rel)

    def window(self, name):
        if name not in {"change", "issue", "receipt", "local"}:
            raise KeyError(name)
        return getattr(self, name)

    def relation_proved(self, earlier, later):
        if (earlier, later) not in self.declared_relations:
            return False
        a, b = self.window(earlier), self.window(later)
        return a is not None and b is not None and a.hi <= b.lo

    def to_dict(self):
        def enc(x):
            return None if x is None else x.to_dict()
        return {"change": self.change.to_dict(), "issue": enc(self.issue),
                "receipt": enc(self.receipt), "local": enc(self.local),
                "declared_relations": [list(x) for x in self.declared_relations]}

    @classmethod
    def from_dict(cls, value):
        def dec(x):
            return None if x is None else TimeWindow.from_dict(x)
        return cls(TimeWindow.from_dict(value["change"]), dec(value.get("issue")),
                   dec(value.get("receipt")), dec(value.get("local")),
                   tuple(tuple(x) for x in value.get("declared_relations", ())))


@dataclass(frozen=True)
class EffectiveInterval:
    on: Fraction
    off: Fraction

    def __post_init__(self):
        on, off = Fraction(self.on), Fraction(self.off)
        if on < 0 or off <= on:
            raise ValueError("effective interval must satisfy 0 <= on < off")
        object.__setattr__(self, "on", on)
        object.__setattr__(self, "off", off)

    def contains(self, t):
        t = Fraction(t)
        return self.on <= t < self.off

    def to_dict(self):
        return {"on": [self.on.numerator, self.on.denominator,
                        self.off.numerator, self.off.denominator]}

    @classmethod
    def from_dict(cls, value):
        return cls(Fraction(value["on"][0], value["on"][1]),
                   Fraction(value["on"][2], value["on"][3]))


@dataclass(frozen=True)
class MessageSpec:
    message_id: str
    version: int
    source: str
    content_digest: str
    effective: EffectiveInterval
    clocks: ClockTrace
    delivery_guaranteed: bool = False

    def __post_init__(self):
        if not self.message_id or not self.source or not self.content_digest:
            raise ValueError("message id/source/content digest required")
        if int(self.version) < 0:
            raise ValueError("message version must be nonnegative")
        if not isinstance(self.delivery_guaranteed, bool):
            raise TypeError("delivery_guaranteed must be bool")
        object.__setattr__(self, "version", int(self.version))

    def to_dict(self):
        return {"message_id": self.message_id, "version": self.version,
                "source": self.source, "content_digest": self.content_digest,
                "effective": self.effective.to_dict(), "clocks": self.clocks.to_dict(),
                "delivery_guaranteed": bool(self.delivery_guaranteed)}

    @classmethod
    def from_dict(cls, value):
        return cls(value["message_id"], value["version"], value["source"],
                   value["content_digest"], EffectiveInterval.from_dict(value["effective"]),
                   ClockTrace.from_dict(value["clocks"]), value.get("delivery_guaranteed", False))


@dataclass(frozen=True)
class ProtocolState:
    state_id: str
    mode: tuple[tuple[str, str], ...] = ()
    resource_monitor: tuple[tuple[str, str], ...] = ()
    received_messages: tuple[tuple[str, int], ...] = ()

    def __post_init__(self):
        if not self.state_id:
            raise ValueError("state id required")
        for name in ("mode", "resource_monitor", "received_messages"):
            vals = tuple(sorted(getattr(self, name)))
            if len({x[0] for x in vals}) != len(vals):
                raise ValueError("duplicate state key")
            object.__setattr__(self, name, vals)

    def to_dict(self):
        return {"state_id": self.state_id, "mode": [list(x) for x in self.mode],
                "resource_monitor": [list(x) for x in self.resource_monitor],
                "received_messages": [list(x) for x in self.received_messages]}

    @classmethod
    def from_dict(cls, value):
        return cls(value["state_id"], tuple(tuple(x) for x in value.get("mode", ())),
                   tuple(tuple(x) for x in value.get("resource_monitor", ())),
                   tuple((x[0], int(x[1])) for x in value.get("received_messages", ())))


@dataclass(frozen=True)
class ProtocolTransition:
    transition_id: str
    source_state_id: str
    target_state_id: str
    events: tuple[tuple[str, CausalStage], ...]
    clocks: ClockTrace
    observation: str
    message: MessageSpec | None = None
    silence: bool = False
    guard_tag: str = ""
    silence_exclusion_proved: bool = False

    def __post_init__(self):
        if not self.transition_id or not self.source_state_id or not self.target_state_id:
            raise ValueError("transition ids required")
        ev = tuple((str(i), CausalStage(s)) for i, s in self.events)
        if not ev or any(a[1] > b[1] for a, b in zip(ev, ev[1:])):
            raise ValueError("causal stages must be a nonempty nondecreasing sequence")
        if not self.observation:
            raise ValueError("observation label required")
        if bool(self.silence) != (self.observation == "silence"):
            raise ValueError("silence flag and label disagree")
        if self.silence and self.message is not None:
            raise ValueError("silence cannot carry a message")
        if not self.silence and self.message is None:
            raise ValueError("received branch must carry a message")
        if self.message is not None and self.message.clocks != self.clocks:
            raise ValueError("message and transition clocks must be identical")
        if self.guard_tag not in ("", "always", "unknown", "false"):
            raise ValueError("unsupported guard tag; use always/unknown/false")
        if self.silence_exclusion_proved and not self.silence:
            raise ValueError("silence exclusion applies only to silence branches")
        if not isinstance(self.silence, bool) or not isinstance(self.silence_exclusion_proved, bool):
            raise TypeError("silence flags must be bool")
        object.__setattr__(self, "events", ev)

    def to_dict(self):
        return {"transition_id": self.transition_id, "source_state_id": self.source_state_id,
                "target_state_id": self.target_state_id,
                "events": [[i, int(s)] for i, s in self.events],
                "clocks": self.clocks.to_dict(), "observation": self.observation,
                "message": None if self.message is None else self.message.to_dict(),
                "silence": bool(self.silence), "guard_tag": self.guard_tag,
                "silence_exclusion_proved": bool(self.silence_exclusion_proved)}

    @classmethod
    def from_dict(cls, value):
        msg = value.get("message")
        return cls(value["transition_id"], value["source_state_id"], value["target_state_id"],
                   tuple((i, CausalStage(s)) for i, s in value["events"]),
                   ClockTrace.from_dict(value["clocks"]), value["observation"],
                   None if msg is None else MessageSpec.from_dict(msg),
                   value.get("silence", False), value.get("guard_tag", ""),
                   value.get("silence_exclusion_proved", False))


@dataclass(frozen=True)
class CoverageLedger:
    state_ids: tuple[str, ...]
    outgoing_transition_ids: tuple[tuple[str, tuple[str, ...]], ...]
    complete: bool
    missing_states: tuple[str, ...] = ()

    def to_dict(self):
        return {"state_ids": list(self.state_ids),
                "outgoing_transition_ids": [[s, list(i)] for s, i in self.outgoing_transition_ids],
                "complete": self.complete, "missing_states": list(self.missing_states)}


@dataclass(frozen=True)
class ProtocolAutomaton:
    states: tuple[ProtocolState, ...]
    initial_state_id: str
    transitions: tuple[ProtocolTransition, ...]
    version: str = "phase4-protocol-v1"

    def __post_init__(self):
        states, transitions = tuple(self.states), tuple(self.transitions)
        ids = {s.state_id for s in states}
        if not states or len(ids) != len(states) or self.initial_state_id not in ids:
            raise ValueError("invalid automaton states")
        if len({t.transition_id for t in transitions}) != len(transitions):
            raise ValueError("duplicate transition id")
        if any(t.source_state_id not in ids or t.target_state_id not in ids for t in transitions):
            raise ValueError("transition references unknown state")
        object.__setattr__(self, "states", states)
        object.__setattr__(self, "transitions", transitions)

    def outgoing(self, state_id):
        if state_id not in {s.state_id for s in self.states}:
            raise KeyError(state_id)
        return tuple(sorted((t for t in self.transitions if t.source_state_id == state_id),
                            key=lambda x: x.transition_id))

    def enumerate_successors(self, state_id, *, at_time=None, observation=None):
        out = self.outgoing(state_id)
        if at_time is not None:
            # ``at_time`` is the earliest current public time.  A transition
            # scheduled later remains enabled; collapsing it to an exact
            # current-time test would silently drop delayed protocol events.
            out = tuple(t for t in out if t.clocks.change.hi >= at_time)
        if observation is not None:
            out = tuple(t for t in out if t.observation == observation)
        return out

    def coverage(self):
        ordered = sorted(self.states, key=lambda x: x.state_id)
        rows = tuple((s.state_id, tuple(t.transition_id for t in self.outgoing(s.state_id)))
                     for s in ordered)
        missing = tuple(s for s, ids in rows if not ids)
        return CoverageLedger(tuple(s.state_id for s in ordered), rows, not missing, missing)

    def digest(self):
        payload = {"version": self.version, "initial_state_id": self.initial_state_id,
                   "states": [s.to_dict() for s in sorted(self.states, key=lambda x: x.state_id)],
                   "transitions": [t.to_dict() for t in sorted(self.transitions, key=lambda x: x.transition_id)]}
        raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
        return "protocol-sha256:" + hashlib.sha256(raw).hexdigest()

    def to_dict(self):
        return {"version": self.version, "initial_state_id": self.initial_state_id,
                "states": [s.to_dict() for s in self.states],
                "transitions": [t.to_dict() for t in self.transitions], "digest": self.digest()}

    @classmethod
    def from_dict(cls, value):
        result = cls(tuple(ProtocolState.from_dict(x) for x in value["states"]), value["initial_state_id"],
                     tuple(ProtocolTransition.from_dict(x) for x in value["transitions"]),
                     value.get("version", "phase4-protocol-v1"))
        if value.get("digest") and value["digest"] != result.digest():
            raise ValueError("protocol digest mismatch")
        return result


def branch_temporal_status(branch: ProtocolTransition):
    """Return branch validity, never knowledge from a silence observation.

    A silence branch is a valid observation branch, but its hidden event remains
    possible unless ``silence_exclusion_proved`` was established by an explicit
    publication and delivery deadline contract.  The full verifier should use
    :func:`silence_knowledge_status` when deciding whether a hidden mode may be
    removed from a posterior.
    """
    if branch.guard_tag in ("false", "unknown", ""):
        return ("UNKNOWN", "GUARD_NOT_PROVED" if branch.guard_tag != "false"
                else "GUARD_FALSE")
    if branch.message is None:
        return "PROVED", "SILENCE_BRANCH"
    c = branch.clocks
    if c.issue is None or c.receipt is None:
        return "UNKNOWN", "MESSAGE_CLOCK_MISSING_ISSUE_OR_RECEIPT"
    if not c.relation_proved("issue", "receipt"):
        return "UNKNOWN", "ISSUE_TO_RECEIPT_ORDER_UNPROVED"
    if c.local is not None and not c.relation_proved("receipt", "local"):
        return "UNKNOWN", "RECEIPT_TO_LOCAL_ORDER_UNPROVED"
    return "PROVED", "CLOCK_RELATIONS_PROVED"


def silence_knowledge_status(branch: ProtocolTransition):
    """Whether this silence branch may exclude its hidden event histories."""
    if not branch.silence:
        return "PROVED", "NOT_SILENCE"
    if not branch.silence_exclusion_proved:
        return "UNKNOWN", "SILENCE_DOES_NOT_EXCLUDE_HIDDEN_EVENT"
    if branch.message is not None:
        return "UNKNOWN", "INVALID_SILENCE_MESSAGE"
    return "PROVED", "PUBLICATION_AND_DELIVERY_DEADLINE_PROVED"


def build_coverage_ledger(automaton):
    return automaton.coverage()
