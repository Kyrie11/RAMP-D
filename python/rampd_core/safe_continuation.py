"""Finite task-winning information-state kernel for the revised RAMP-D paper.

Implements the *conditional finite-abstraction* counterpart of Eq. (SC-winning):
    W_0 = externally replay-verified finite completion tails
    W_{r+1} = W_r union safe common-control predecessors of W_r.

No bare claimed evidence or predicted futures are accepted as proofs.
External callbacks MUST actually replay full-tube safety, complete protocol
observation/posterior support and the terminal tail including task acceptance.
The library can validate their binding; it cannot prove their implementations.

Ranks are monotone decreasing, and the worst-case completion bound uses exact
rational arithmetic.  Optional value estimates are *certified lower bounds of
stored policy margins*, not exact V_H or regret bounds.  This is intentionally
not a substitute for CCG, temporal controllability or full-support verification.
"""
from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from typing import Callable, Iterable
import hashlib
import json

from .belief import BeliefCell
from .invariant import (ActionWitness, EvidenceContext, SafeDomain,
                        _evaluate_action)


def _nonempty(name: str, value: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a nonempty string")
    return value


def _rat_nonnegative(name: str, value) -> Fraction:
    # Proof-carrying times and lower bounds MUST have an explicit exact
    # interpretation.  A Python float is not the decimal/rational quantity
    # most callers think it denotes, and silently rounding a certified lower
    # bound can overstate it. Pass Fraction or decimal/rational string.
    if isinstance(value, (bool, float)):
        raise TypeError(f"{name}: use Fraction, int or exact decimal string; not float/bool")
    result = Fraction(value)
    if result < 0:
        raise ValueError(f"{name} must be nonnegative")
    return result


def _unit_margin(name: str, value) -> Fraction:
    val = _rat_nonnegative(name, value)
    if val > 1:
        raise ValueError(f"{name} must be a normalized lower margin in [0,1]")
    return val


@dataclass(frozen=True)
class SCContract:
    """Bindings shared by every terminal and transition proof."""
    protocol_digest: str
    clock_digest: str
    model_digest: str
    task_digest: str
    step_s: Fraction
    horizon: int

    def __post_init__(self):
        for field in ("protocol_digest", "clock_digest", "model_digest", "task_digest"):
            _nonempty(field, getattr(self, field))
        step = _rat_nonnegative("step_s", self.step_s)
        if step == 0:
            raise ValueError("step_s must be positive")
        if type(self.horizon) is not int or self.horizon < 0:
            raise ValueError("horizon must be a nonnegative integer")
        object.__setattr__(self, "step_s", step)

    def to_dict(self):
        return {"protocol_digest": self.protocol_digest,
                "clock_digest": self.clock_digest, "model_digest": self.model_digest,
                "task_digest": self.task_digest,
                "step_s": str(self.step_s), "horizon": self.horizon}

    @property
    def digest(self):
        return _digest(self.to_dict())


@dataclass(frozen=True)
class TerminalTailCertificate:
    """Caller-supplied witness, not self-proving: terminal_replayer must verify.

    This includes a policy that reaches the accepting task automaton state
    within the bound for *all* admissible posterior histories.  Safety-only
    waiting is not task acceptance.  The optional margin is verified by the
    same terminal replay.  No default positive margin is manufactured.
    """
    cell_id: str
    tail_policy_digest: str
    evidence_ref: str
    max_tail_s: Fraction
    protocol_digest: str
    clock_digest: str
    model_digest: str
    task_digest: str
    margin_lower: Fraction | None = None

    def __post_init__(self):
        for f in ("cell_id", "tail_policy_digest", "evidence_ref",
                  "protocol_digest", "clock_digest", "model_digest", "task_digest"):
            _nonempty(f, getattr(self, f))
        object.__setattr__(self, "max_tail_s", _rat_nonnegative("max_tail_s", self.max_tail_s))
        if self.margin_lower is not None:
            object.__setattr__(self, "margin_lower", _unit_margin("margin_lower", self.margin_lower))

    def bound_to(self, context: SCContract) -> bool:
        return (self.protocol_digest == context.protocol_digest and
                self.clock_digest == context.clock_digest and
                self.model_digest == context.model_digest and
                self.task_digest == context.task_digest)


@dataclass(frozen=True)
class TubeMarginCertificate:
    """Lower bound on g_tube for the complete public action and full support.

    margin_replayer must establish its provenance and the lower-bound claim;
    it is not inferred from point trajectories or a prediction model.
    """
    cell_id: str
    action_id: str
    evidence_ref: str
    contract_digest: str
    lower: Fraction

    def __post_init__(self):
        for f in ("cell_id", "action_id", "evidence_ref", "contract_digest"):
            _nonempty(f, getattr(self, f))
        object.__setattr__(self, "lower", _unit_margin("lower", self.lower))


@dataclass(frozen=True)
class SCPolicyStep:
    cell_id: str
    rank: int
    action_id: str
    controller_ref: str | None
    observation_children: tuple[tuple[str, str], ...]
    worst_completion_s: Fraction
    margin_lower: Fraction | None


@dataclass(frozen=True)
class SCResult:
    """Only an inner candidate, conditional on the supplied replay callbacks."""
    contract_digest: str
    family_by_rank: tuple[tuple[str, ...], ...]
    rank_pairs: tuple[tuple[str, int], ...]
    terminals: tuple[str, ...]
    policy_steps: tuple[SCPolicyStep, ...]
    completion_upper_pairs: tuple[tuple[str, Fraction], ...]
    margin_lower_pairs: tuple[tuple[str, Fraction], ...]
    reasons: tuple[tuple[str, str], ...]
    support_digest_pairs: tuple[tuple[str, str], ...] = ()
    step_s: Fraction = Fraction(0)
    status: str = "CONDITIONAL_FINITE_ABSTRACTION_ONLY"
    certified_full_support: bool = False

    @property
    def support_digests(self) -> dict[str, str]:
        return dict(self.support_digest_pairs)

    @property
    def ranks(self) -> dict[str, int]:
        return dict(self.rank_pairs)

    @property
    def completion_upper_s(self) -> dict[str, Fraction]:
        return dict(self.completion_upper_pairs)

    @property
    def margins_lower(self) -> dict[str, Fraction]:
        return dict(self.margin_lower_pairs)

    def to_dict(self):
        return {
            "contract_digest": self.contract_digest,
            "family_by_rank": [list(x) for x in self.family_by_rank],
            "rank_pairs": [[k, r] for k, r in self.rank_pairs],
            "terminals": list(self.terminals),
            "policy_steps": [
                {"cell_id": s.cell_id, "rank": s.rank, "action_id": s.action_id,
                 "controller_ref": s.controller_ref,
                 "observation_children": [list(x) for x in s.observation_children],
                 "worst_completion_s": str(s.worst_completion_s),
                 "margin_lower": None if s.margin_lower is None else str(s.margin_lower)}
                for s in self.policy_steps],
            "completion_upper_pairs": [[k, str(v)] for k, v in self.completion_upper_pairs],
            "margin_lower_pairs": [[k, str(v)] for k, v in self.margin_lower_pairs],
            "reasons": [list(x) for x in self.reasons],
            "support_digest_pairs": [list(x) for x in self.support_digest_pairs],
            "step_s": str(self.step_s),
            "status": self.status, "certified_full_support": self.certified_full_support,
        }


def _digest(payload) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf8")
    return "sc-sha256:" + hashlib.sha256(raw).hexdigest()


def sc_support_digest(cell: BeliefCell) -> str:
    """Stable full physical/discrete support identity, not merely a cell label.

    The digest deliberately includes exact binary64 interval endpoints (the
    current abstract-game representation), every other-agent coordinate,
    discrete modes, public policy-node ID, and atom identities. It is a
    *version binding*, NOT proof of exact/complete concrete support.
    """
    return _digest({
        "cell_id": cell.cell_id, "policy_node_id": cell.policy_node_id,
        "atoms": [
            {"id": a.atom_id,
             "ego": [[v.lo.hex(), v.hi.hex()] for v in a.ego.as_tuple()],
             "other": [[name, val.lo.hex(), val.hi.hex()] for name, val in a.other],
             "mode": [list(pair) for pair in a.mode]}
            for a in sorted(cell.atoms, key=lambda a: a.atom_id)
        ],
    })


def compute_sc_inner(
    cells: Iterable[BeliefCell], safe_domain: SafeDomain, contract: SCContract,
    terminal_tails: Iterable[TerminalTailCertificate], *,
    evidence_replayer: Callable[[EvidenceContext, SCContract], bool] | None,
    branch_cover_replayer: Callable[[BeliefCell, ActionWitness, SCContract], bool] | None,
    terminal_replayer: Callable[[BeliefCell, TerminalTailCertificate, SCContract], bool] | None,
    margins: Iterable[TubeMarginCertificate] = (),
    margin_replayer: Callable[[BeliefCell, ActionWitness, TubeMarginCertificate, SCContract], bool] | None = None,
) -> SCResult:
    """Compute finite SC inner family and a strictly descending policy graph.

    At each step one action covers every source atom.  All successor atoms
    consistent with the SAME observation are unioned before checking target
    inclusion.  Failure to replay any source transition excludes the action.
    Only previous-rank cells are targets; cycles/stalling cannot be admitted.
    A separate branch-cover replay is MANDATORY: it must establish that the
    action enumerates every protocol-allowed successor and that different
    observation labels really distinguish the corresponding histories (or
    have been merged under one public child).  A transition proof alone is
    not sufficient to discharge this relational completeness obligation.

    The replay callbacks are trust boundaries; `True` must mean a verified
    full-support proof, and nothing is asserted on their behalf here.
    """
    cells = tuple(cells)
    if not isinstance(contract, SCContract) or not isinstance(safe_domain, SafeDomain):
        raise TypeError("expected SCContract and SafeDomain")
    if len({c.cell_id for c in cells}) != len(cells):
        raise ValueError("duplicate cell ids")
    if len({c.policy_node_id for c in cells}) != len(cells):
        raise ValueError("distinct information supports need unique public policy nodes")
    for c in cells:
        if not isinstance(c, BeliefCell):
            raise TypeError("cells must be BeliefCell")
    by_id = {c.cell_id: c for c in cells}
    tails = tuple(terminal_tails)
    if len({x.cell_id for x in tails}) != len(tails):
        raise ValueError("duplicate terminal cell ids")
    if any(not isinstance(x, TerminalTailCertificate) for x in tails):
        raise TypeError("terminal tails must be TerminalTailCertificate")
    if any(t.cell_id not in by_id for t in tails):
        raise ValueError("terminal certificate references unknown cell")
    margin_rows = tuple(margins)
    if any(not isinstance(m, TubeMarginCertificate) for m in margin_rows):
        raise TypeError("margins must be TubeMarginCertificate")
    margin_map = {}
    for m in margin_rows:
        k = (m.cell_id, m.action_id)
        if k in margin_map:
            raise ValueError("duplicate tube margin witness")
        margin_map[k] = m

    # No positive status for unproved initial-domain, terminal, or transition.
    safe = {}
    reasons = {}
    for c in cells:
        outcomes = [safe_domain.contains_atom(atom) for atom in c.atoms]
        bad = next((why for ok, why in outcomes if not ok), None)
        safe[c.cell_id] = bad is None
        if bad is not None:
            reasons[c.cell_id] = "UNSAFE_DOMAIN:" + bad

    rank: dict[str, int] = {}
    bound: dict[str, Fraction] = {}
    val_lower: dict[str, Fraction] = {}
    selected: dict[str, SCPolicyStep] = {}
    for tail in sorted(tails, key=lambda t: t.cell_id):
        cell = by_id[tail.cell_id]
        if not safe[tail.cell_id]:
            continue
        if not tail.bound_to(contract):
            reasons[tail.cell_id] = "TERMINAL_CONTEXT_MISMATCH"
            continue
        try:
            verified = terminal_replayer is not None and terminal_replayer(cell, tail, contract) is True
        except Exception:
            verified = False
        if not verified:
            reasons[tail.cell_id] = "TERMINAL_REPLAY_UNPROVED"
            continue
        rank[tail.cell_id] = 0
        bound[tail.cell_id] = tail.max_tail_s
        if tail.margin_lower is not None:
            val_lower[tail.cell_id] = tail.margin_lower

    terminal_ids = tuple(sorted(rank))
    families = [terminal_ids]
    for h in range(1, contract.horizon + 1):
        previous = {cid: by_id[cid] for cid in sorted(rank)}
        index: dict[str, list[BeliefCell]] = {}
        for c in previous.values():
            for atom in c.atoms:
                index.setdefault(atom.atom_id, []).append(c)
        # Snapshot previous ranks: additions in this iteration are not allowed
        # as destinations of other additions in the same iteration.
        new: dict[str, tuple[ActionWitness, tuple[tuple[str, str], ...], Fraction, Fraction | None]] = {}
        for cid in sorted(by_id):
            if cid in rank or not safe[cid]:
                continue
            cell = by_id[cid]
            candidates = []
            for action in sorted(cell.actions, key=lambda a: getattr(a, "action_id", "")):
                if not isinstance(action, ActionWitness):
                    continue
                try:
                    complete = (branch_cover_replayer is not None and
                                branch_cover_replayer(cell, action, contract) is True)
                except Exception:
                    complete = False
                if not complete:
                    continue
                def bound_evidence(context):
                    return (evidence_replayer is not None and
                            evidence_replayer(context, contract) is True)
                children, _ = _evaluate_action(cell, action, previous, bound_evidence, index)
                if children is None:
                    continue
                # Every branch uses one stored (observation -> policy-node)
                # selection, chosen only after combining hidden source atoms.
                worst = contract.step_s + max(bound[child] for _, child in children)
                values = [val_lower[child] for _, child in children if child in val_lower]
                margin_bound = margin_map.get((cid, action.action_id))
                g = None
                if (margin_bound is not None and margin_bound.contract_digest == contract.digest and
                        margin_replayer is not None):
                    try:
                        if margin_replayer(cell, action, margin_bound, contract) is True:
                            g = margin_bound.lower
                    except Exception:
                        pass
                q_lower = min([g] + values) if g is not None and len(values) == len(children) else None
                candidates.append((action, children, worst, q_lower))
            if candidates:
                # Highest proved lower margin when available, then deterministic
                # fallback. This is an achievable-policy lower bound, not an
                # exact max over all continuous public controls.
                candidates.sort(key=lambda x: (x[3] is None, -(x[3] or Fraction(0)), x[0].action_id))
                new[cid] = candidates[0]
            else:
                reasons[cid] = "NO_REPLAYED_RANK_DECREASING_COMMON_ACTION"
        for cid in sorted(new):
            action, children, completion, q = new[cid]
            rank[cid] = h
            bound[cid] = completion
            if q is not None:
                val_lower[cid] = q
            selected[cid] = SCPolicyStep(cid, h, action.action_id, action.controller_ref,
                                         children, completion, q)
            reasons.pop(cid, None)
        families.append(tuple(sorted(rank)))

    for cid in by_id:
        if cid not in rank and cid not in reasons:
            reasons[cid] = "OUTSIDE_HORIZON_OR_UNPROVED"
    # Independent in-memory checks: no nondecrease, uncovered child or bad time.
    for cid, item in selected.items():
        if not item.observation_children:
            raise RuntimeError("empty observation successor set")
        if any(rank[child] >= item.rank for _, child in item.observation_children):
            raise RuntimeError("rank did not decrease")
        if bound[cid] != contract.step_s + max(bound[child] for _, child in item.observation_children):
            raise RuntimeError("worst-case completion time inconsistent")
    return SCResult(contract.digest, tuple(families), tuple(sorted(rank.items())),
                    terminal_ids, tuple(selected[c] for c in sorted(selected)),
                    tuple(sorted(bound.items())), tuple(sorted(val_lower.items())),
                    tuple(sorted(reasons.items())),
                    support_digest_pairs=tuple(sorted((cid, sc_support_digest(cell))
                                                      for cid, cell in by_id.items())),
                    step_s=contract.step_s)


def replay_sc_inner(expected: SCResult, *args, **kwargs) -> bool:
    """Re-run caller-provided replayers and compare canonical results.

    Independence of external physical/terminal replayers is a separate proof
    obligation; this function alone is not independent formal verification.
    """
    if not isinstance(expected, SCResult):
        return False
    try:
        return compute_sc_inner(*args, **kwargs).to_dict() == expected.to_dict()
    except Exception:
        return False


class SCExecutionError(RuntimeError):
    """The declared completion-rank certificate cannot cover this execution."""


@dataclass(frozen=True)
class SCExecutionBudget:
    """Rank remaining after an observation; cannot be reset by replanning."""
    contract_digest: str
    cell_id: str
    remaining_rank: int
    support_digest: str = ""
    remaining_completion_s: Fraction | None = None

    def __post_init__(self):
        _nonempty("contract_digest", self.contract_digest)
        _nonempty("cell_id", self.cell_id)
        if type(self.remaining_rank) is not int or self.remaining_rank < 0:
            raise ValueError("remaining rank must be a nonnegative integer")
        if self.remaining_completion_s is not None:
            bound = _rat_nonnegative("remaining_completion_s", self.remaining_completion_s)
            object.__setattr__(self, "remaining_completion_s", bound)


def start_sc_execution(certificate: SCResult, cell_id: str) -> SCExecutionBudget:
    rank = certificate.ranks.get(cell_id)
    if rank is None:
        raise SCExecutionError("START_CELL_HAS_NO_REPLAYED_TASK_COMPLETION_POLICY")
    support_digest = certificate.support_digests.get(cell_id)
    if not support_digest:
        raise SCExecutionError("START_SUPPORT_BINDING_MISSING")
    bound = certificate.completion_upper_s.get(cell_id)
    if bound is None or certificate.step_s <= 0:
        raise SCExecutionError("START_COMPLETION_BINDING_MISSING")
    return SCExecutionBudget(certificate.contract_digest, cell_id, rank,
                             support_digest, bound)


def advance_sc_execution(certificate: SCResult, budget: SCExecutionBudget,
                         observation: str, next_cell_id: str) -> SCExecutionBudget:
    """Consume ONE stored common-control step and its actually seen observation.

    Runtime must independently check that the actual physical successor is in
    the declared child support.  This function checks the stored rank policy
    and does not have access to the vehicle sensor/geometry evidence itself.
    """
    if certificate.contract_digest != budget.contract_digest:
        raise SCExecutionError("REPLAN_CONTEXT_CHANGED")
    if budget.remaining_completion_s is None or certificate.step_s <= 0:
        raise SCExecutionError("EXECUTION_COMPLETION_BUDGET_MISSING")
    parent_time = certificate.completion_upper_s.get(budget.cell_id)
    if parent_time is None or parent_time < 0 or parent_time > budget.remaining_completion_s:
        raise SCExecutionError("EXECUTION_COMPLETION_CERTIFICATE_EXCEEDS_BUDGET")
    if budget.remaining_rank == 0:
        raise SCExecutionError("TERMINAL_TAIL_REQUIRED_NO_FURTHER_PREFIX")
    if (not budget.support_digest or
            certificate.support_digests.get(budget.cell_id) != budget.support_digest):
        raise SCExecutionError("EXECUTION_SUPPORT_CONTEXT_CHANGED")
    parent_rank = certificate.ranks.get(budget.cell_id)
    if parent_rank is None or parent_rank > budget.remaining_rank:
        raise SCExecutionError("PARENT_CERTIFICATE_EXCEEDS_INHERITED_BUDGET")
    policy = {p.cell_id: p for p in certificate.policy_steps}.get(budget.cell_id)
    if policy is None or policy.rank != parent_rank:
        raise SCExecutionError("PUBLIC_POLICY_STEP_NOT_CERTIFIED")
    matched = dict(policy.observation_children)
    if observation not in matched:
        raise SCExecutionError("UNEXPECTED_OBSERVATION_INVALIDATES_TASK_CERTIFICATE")
    if matched[observation] != next_cell_id:
        raise SCExecutionError("CHILD_SUPPORT_DOES_NOT_MATCH_PUBLIC_OBSERVATION")
    next_rank = certificate.ranks.get(next_cell_id)
    if next_rank is None or next_rank >= parent_rank or next_rank > budget.remaining_rank - 1:
        raise SCExecutionError("CHILD_RANK_NOT_STRICTLY_DECREASED")
    next_support = certificate.support_digests.get(next_cell_id)
    if not next_support:
        raise SCExecutionError("CHILD_SUPPORT_BINDING_MISSING")
    remaining_time = min(budget.remaining_completion_s, parent_time) - certificate.step_s
    child_time = certificate.completion_upper_s.get(next_cell_id)
    if remaining_time < 0 or child_time is None or child_time > remaining_time:
        raise SCExecutionError("CHILD_COMPLETION_EXCEEDS_INHERITED_TIME_BUDGET")
    from .a75_rank import tighten
    try:
        rank, completion = tighten(parent_rank, parent_time, next_rank, child_time, elapsed=certificate.step_s, executed=True)
    except ValueError as e:
        raise SCExecutionError("CHILD_RANK_OR_COMPLETION_BUDGET_INVALID") from e
    return SCExecutionBudget(budget.contract_digest, next_cell_id,
                             rank, next_support, completion)


def replan_sc_execution(new_certificate: SCResult,
                        inherited: SCExecutionBudget) -> SCExecutionBudget:
    """Require a newly computed policy for the SAME support/context within budget."""
    if inherited.contract_digest != new_certificate.contract_digest:
        raise SCExecutionError("REPLAN_CONTEXT_CHANGED")
    if (not inherited.support_digest or
            new_certificate.support_digests.get(inherited.cell_id) != inherited.support_digest):
        raise SCExecutionError("REPLAN_INFORMATION_SUPPORT_CHANGED")
    if (inherited.remaining_completion_s is None or
            new_certificate.step_s <= 0 or
            new_certificate.completion_upper_s.get(inherited.cell_id, Fraction(-1)) < 0 or
            new_certificate.completion_upper_s[inherited.cell_id] > inherited.remaining_completion_s):
        raise SCExecutionError("REPLAN_COMPLETION_BOUND_EXCEEDS_INHERITED_BUDGET")
    new_rank = new_certificate.ranks.get(inherited.cell_id)
    if new_rank is None or new_rank > inherited.remaining_rank:
        raise SCExecutionError("REPLAN_RESETS_OR_EXCEEDS_INHERITED_RANK")
    from .a75_rank import tighten
    try:
        rank, completion = tighten(inherited.remaining_rank, inherited.remaining_completion_s, new_rank, new_certificate.completion_upper_s[inherited.cell_id])
    except ValueError as e:
        raise SCExecutionError("REPLAN_RANK_OR_COMPLETION_BUDGET_INVALID") from e
    return SCExecutionBudget(inherited.contract_digest, inherited.cell_id, rank, inherited.support_digest, completion)
