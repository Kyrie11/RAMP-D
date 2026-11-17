"""Phase 6C-A5/1: exact finite task-policy and observation-cover audit.

Dependency-free discrete proof checker (not a physical or real-world certificate).
The table of allowed outcomes is a *declared model*. Exhaustiveness relative to
an external traffic protocol is a separate, mandatory boundary.
"""
from __future__ import annotations
from dataclasses import dataclass
from fractions import Fraction
import hashlib
import json


def _fraction(value, field):
    if isinstance(value, (float, bool)):
        raise TypeError(field + ': exact Fraction/int/decimal string required')
    q = Fraction(value)
    if q < 0:
        raise ValueError(field + ': nonnegative bound required')
    return q


@dataclass(frozen=True)
class FiniteTaskEdge:
    state: str
    action: str
    observation: str
    next_state: str

    def __post_init__(self):
        if not all(isinstance(v, str) and v for v in (self.state, self.action,
                                                      self.observation, self.next_state)):
            raise ValueError('edge fields must be nonempty strings')


@dataclass(frozen=True)
class FiniteTaskModel:
    """Complete model of allowable task transitions for each (state, action).

    The external environment must warrant that the enumerated outcomes cover
    all admissible observation histories. Nothing in this class asserts that
    a dataset or simulator proves this external completeness premise.
    """
    states: tuple[str, ...]
    accepting: frozenset[str]
    edges: tuple[FiniteTaskEdge, ...]
    step_s: Fraction
    version: str

    def __post_init__(self):
        states = tuple(self.states)
        if (not states or any(not isinstance(s, str) or not s for s in states)
                or len(states) != len(set(states)) or not self.accepting <= set(states)):
            raise ValueError('invalid state partition / accepting set')
        edges = tuple(self.edges)
        if any(e.state not in states or e.next_state not in states for e in edges):
            raise ValueError('edge references unknown task state')
        if len(edges) != len(set(edges)):
            raise ValueError('duplicate task edge')
        if not isinstance(self.version, str) or not self.version:
            raise ValueError('model version required')
        h = _fraction(self.step_s, 'step_s')
        if h == 0:
            raise ValueError('step_s must be positive')
        object.__setattr__(self, 'states', states)
        object.__setattr__(self, 'edges', edges)
        object.__setattr__(self, 'accepting', frozenset(self.accepting))
        object.__setattr__(self, 'step_s', h)

    @property
    def digest(self):
        body = {'version': self.version, 'states': sorted(self.states),
                'accepting': sorted(self.accepting), 'step_s': str(self.step_s),
                'edges': sorted((e.state, e.action, e.observation, e.next_state)
                                for e in self.edges)}
        return 'a5-task-sha256:' + hashlib.sha256(json.dumps(
            body, sort_keys=True, separators=(',', ':')).encode()).hexdigest()

    def successors(self, state: str, action: str) -> tuple[FiniteTaskEdge, ...]:
        return tuple(e for e in self.edges if e.state == state and e.action == action)


@dataclass(frozen=True)
class FiniteTailPolicy:
    """Explicit nonanticipative action per task state, with finite rank budget.

    State labels must ALREADY be information states (merged posteriors), not
    unobserved hidden modes. The checker does not invent observation knowledge.
    """
    model_digest: str
    start_states: tuple[str, ...]
    actions: tuple[tuple[str, str], ...]
    claimed_max_s: Fraction
    max_depth: int

    def __post_init__(self):
        if not isinstance(self.model_digest, str) or not self.model_digest:
            raise ValueError('model_digest required')
        if not self.start_states or len(set(self.start_states)) != len(self.start_states):
            raise ValueError('nonempty distinct initial task states required')
        if len({s for s, _ in self.actions}) != len(self.actions):
            raise ValueError('one public action per task state')
        if type(self.max_depth) is not int or self.max_depth < 0:
            raise ValueError('finite nonnegative integer maximum depth required')
        object.__setattr__(self, 'claimed_max_s', _fraction(self.claimed_max_s, 'claimed_max_s'))


@dataclass(frozen=True)
class FiniteTailAudit:
    status: str
    reason: str
    exact_worst_s: Fraction | None
    checked_states: int
    model_relative_only: bool = True

    @property
    def ok(self):
        return self.status == 'FINITE_TASK_TAIL_PROVED'


def audit_finite_tail(model: FiniteTaskModel, policy: FiniteTailPolicy) -> FiniteTailAudit:
    """Independent AND/OR replay, no probabilistic selection and no wait loops.

    If ANY declared branch fails to accept within the finite budget, fail
    closed. Compare claimed worst completion time using exact rational values.
    """
    if policy.model_digest != model.digest:
        return FiniteTailAudit('UNKNOWN', 'TASK_MODEL_CONTEXT_MISMATCH', None, 0)
    if any(s not in model.states for s in policy.start_states):
        return FiniteTailAudit('UNKNOWN', 'TASK_START_OUTSIDE_MODEL', None, 0)
    actions = dict(policy.actions)
    seen = 0

    def visit(state: str, remaining: int):
        nonlocal seen
        seen += 1
        if state in model.accepting:
            return Fraction(0)
        if remaining == 0:
            raise ValueError('NONACCEPTING_AT_DEPTH_LIMIT')
        action = actions.get(state)
        if not action:
            raise ValueError('NO_PUBLIC_ACTION')
        branches = model.successors(state, action)
        if not branches:
            raise ValueError('MISSING_DECLARED_OUTCOMES')
        # Repeated observations at same public node must route to the same
        # successor information state, or the model needs posterior merging.
        post = {}
        for edge in branches:
            if edge.observation in post and post[edge.observation] != edge.next_state:
                raise ValueError('UNMERGED_SAME_OBSERVATION')
            post[edge.observation] = edge.next_state
        return model.step_s + max(visit(child, remaining - 1) for child in post.values())

    try:
        worst = max(visit(s, policy.max_depth) for s in policy.start_states)
    except (ValueError, RecursionError) as err:
        return FiniteTailAudit('UNKNOWN', str(err), None, seen)
    if worst != policy.claimed_max_s:
        return FiniteTailAudit('UNKNOWN', 'WORST_CASE_DURATION_MISMATCH', worst, seen)
    return FiniteTailAudit('FINITE_TASK_TAIL_PROVED', 'ALL_DECLARED_BRANCHES_ACCEPT', worst, seen)
