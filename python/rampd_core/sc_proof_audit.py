"""Independent structural checker for the *finite conditional* SC certificate.

Deliberately does NOT call compute_sc_inner, _evaluate_action, or
replay_sc_inner. The replay callback is a trust boundary and cannot by itself
establish the concrete physical, protocol, or terminal proof obligations.
This checker can reject altered finite certificates and helps localize errors.
"""
from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from typing import Callable, Iterable

from .belief import BeliefCell, SupportAtom
from .invariant import ActionWitness, EvidenceContext, EvidenceVerdict, SafeDomain
from .safe_continuation import (SCContract, SCResult, TerminalTailCertificate,
                                TubeMarginCertificate, sc_support_digest)


@dataclass(frozen=True)
class SCProofAudit:
    status: str
    reason: str
    checked_cells: int
    checked_actions: int
    conditional_only: bool = True
    full_support_certified: bool = False

    @property
    def ok(self) -> bool:
        return self.status == 'CONDITIONAL_REPLAY_PASS'


def _within(source: SupportAtom, target: SupportAtom) -> bool:
    if source.mode != target.mode:
        return False
    if tuple(k for k, _ in source.other) != tuple(k for k, _ in target.other):
        return False
    if any((t.lo > s.lo or s.hi > t.hi)
           for s, t in zip(source.ego.as_tuple(), target.ego.as_tuple())):
        return False
    return all(t.lo <= s.lo and s.hi <= t.hi
               for (_, s), (_, t) in zip(source.other, target.other))


def _covered(union: list[SupportAtom], target: BeliefCell) -> bool:
    return bool(union) and all(any(_within(a, b) for b in target.atoms)
                               for a in union)


def _truth(func: Callable | None, *args) -> bool:
    if func is None:
        return False
    try:
        return func(*args) is True
    except Exception:
        return False


def audit_sc_proof(
    proof: SCResult, cells: Iterable[BeliefCell], safe_domain: SafeDomain,
    contract: SCContract, terminal_tails: Iterable[TerminalTailCertificate], *,
    evidence_replayer: Callable[[EvidenceContext, SCContract], bool] | None,
    branch_cover_replayer: Callable[[BeliefCell, ActionWitness, SCContract], bool] | None,
    terminal_replayer: Callable[[BeliefCell, TerminalTailCertificate, SCContract], bool] | None,
    margins: Iterable[TubeMarginCertificate] = (),
    margin_replayer: Callable | None = None,
) -> SCProofAudit:
    """Check ALL claimed finite-game proof edges independently from the generator.

    Returns CONDITIONAL_REPLAY_PASS only if the same external proof replayers
    independently accepted every claimed terminal, transition, observation
    partition, and optional margin. Structural soundness of those replayers is
    NOT established here, so this audit never claims full-support safety.
    """
    checked = 0
    actions = 0

    def bad(reason: str) -> SCProofAudit:
        return SCProofAudit('INVALID_OR_UNPROVED', reason, checked, actions)

    if not isinstance(proof, SCResult) or not isinstance(contract, SCContract):
        return bad('INPUT_TYPE')
    if proof.contract_digest != contract.digest or proof.step_s != contract.step_s:
        return bad('SC_CONTEXT_MISMATCH')
    if proof.certified_full_support or proof.status != 'CONDITIONAL_FINITE_ABSTRACTION_ONLY':
        return bad('OVERSTATED_ASSURANCE_SCOPE')
    cells = tuple(cells)
    by_id = {c.cell_id: c for c in cells}
    if len(by_id) != len(cells):
        return bad('DUPLICATE_CELL')
    actual_digests = {cid: sc_support_digest(c) for cid, c in by_id.items()}
    if actual_digests != proof.support_digests or len(proof.support_digest_pairs) != len(actual_digests):
        return bad('INFORMATION_SUPPORT_BINDING_MISMATCH')
    ranks = proof.ranks
    completion = proof.completion_upper_s
    claimed_margin = proof.margins_lower
    if len(ranks) != len(proof.rank_pairs) or len(proof.completion_upper_pairs) != len(completion):
        return bad('DUPLICATE_RANK_OR_TIME')
    if not ranks or any(cid not in by_id or type(r) is not int or r < 0 or r > contract.horizon
                        for cid, r in ranks.items()):
        return bad('RANK_DOMAIN')
    if set(ranks) != set(completion):
        return bad('COMPLETION_DOMAIN')
    if len(proof.family_by_rank) != contract.horizon + 1:
        return bad('HORIZON_FAMILY_COUNT')
    for h, family in enumerate(proof.family_by_rank):
        expected = {c for c, r in ranks.items() if r <= h}
        if set(family) != expected or len(family) != len(expected):
            return bad('WINNING_FAMILY_RANK_MISMATCH')
    if len(proof.terminals) != len(set(proof.terminals)):
        return bad('DUPLICATE_TERMINAL')
    if set(proof.terminals) != {cid for cid, r in ranks.items() if r == 0}:
        return bad('TERMINAL_RANK_MISMATCH')
    tails = {}
    for tail in terminal_tails:
        if tail.cell_id in tails:
            return bad('DUPLICATE_TAIL')
        tails[tail.cell_id] = tail
    for cid in sorted(ranks):
        c = by_id[cid]
        checked += 1
        if not all(safe_domain.contains_atom(a)[0] for a in c.atoms):
            return bad('UNSAFE_CLAIM:' + cid)
    for cid in proof.terminals:
        tail = tails.get(cid)
        if tail is None or not tail.bound_to(contract) or not _truth(terminal_replayer, by_id[cid], tail, contract):
            return bad('TERMINAL_UNPROVED:' + cid)
        if completion[cid] != tail.max_tail_s:
            return bad('TERMINAL_COMPLETION_INCORRECT:' + cid)
        if cid in claimed_margin and claimed_margin[cid] != tail.margin_lower:
            return bad('TERMINAL_MARGIN_INCORRECT:' + cid)
    steps = {}
    for step in proof.policy_steps:
        if step.cell_id in steps:
            return bad('DUPLICATE_POLICY_STEP')
        steps[step.cell_id] = step
    if set(steps) != set(ranks) - set(proof.terminals):
        return bad('NONTERMINAL_POLICY_MISSING_OR_EXTRA')
    margin_map = {(m.cell_id, m.action_id): m for m in margins}
    if len(margin_map) != len(tuple(margins)):
        return bad('DUPLICATE_MARGIN_WITNESS')
    if any(cid not in ranks for cid in claimed_margin):
        return bad('ORPHAN_MARGIN')
    for cid, step in sorted(steps.items()):
        c = by_id[cid]
        if step.rank != ranks[cid] or step.rank <= 0:
            return bad('POLICY_RANK_MISMATCH:' + cid)
        action = next((a for a in c.actions
                       if isinstance(a, ActionWitness) and a.action_id == step.action_id), None)
        if action is None or action.controller_ref != step.controller_ref:
            return bad('PUBLIC_ACTION_OR_CONTROLLER_MISMATCH:' + cid)
        actions += 1
        # This is an external proof of complete protocol branch coverage,
        # not a numeric inference from the number of observed branches.
        if not _truth(branch_cover_replayer, c, action, contract):
            return bad('PROTOCOL_OBSERVATION_COVERAGE_UNPROVED:' + cid)
        by_source = {tr.source_atom_id: tr for tr in action.transitions}
        if len(by_source) != len(action.transitions) or set(by_source) != {a.atom_id for a in c.atoms}:
            return bad('INCOMPLETE_SOURCE_COVERAGE:' + cid)
        posterior = {}
        for atom in c.atoms:
            tr = by_source[atom.atom_id]
            if tr.verdict is not EvidenceVerdict.PROVED:
                return bad('UNCERTIFIED_TRANSITION:' + cid)
            if not _truth(evidence_replayer, EvidenceContext(c, atom, action, tr), contract):
                return bad('PHYSICAL_TUBE_UNPROVED:' + cid)
            for branch in tr.branches:
                posterior.setdefault(branch.observation, []).extend(branch.atoms)
        children = dict(step.observation_children)
        if (len(children) != len(step.observation_children) or
                set(children) != set(posterior)):
            return bad('PUBLIC_OBSERVATION_PARTITION_MISMATCH:' + cid)
        for observation, child in children.items():
            if (child not in ranks or ranks[child] >= ranks[cid] or
                    not _covered(posterior[observation], by_id[child])):
                return bad('SUCCESSOR_NOT_COVERED_OR_RANK_NONDECREASE:' + cid)
        worst = contract.step_s + max(completion[child] for child in children.values())
        if step.worst_completion_s != worst or completion[cid] != worst:
            return bad('EXACT_RATIONAL_COMPLETION_MISMATCH:' + cid)
        m = margin_map.get((cid, action.action_id))
        if cid in claimed_margin:
            if (m is None or m.contract_digest != contract.digest or
                    not _truth(margin_replayer, c, action, m, contract) or
                    any(child not in claimed_margin for child in children.values())):
                return bad('MARGIN_PROOF_MISSING:' + cid)
            lower = min([m.lower] + [claimed_margin[child] for child in children.values()])
            if lower != claimed_margin[cid] or step.margin_lower != lower:
                return bad('MARGIN_RECURSION_MISMATCH:' + cid)
        elif step.margin_lower is not None:
            return bad('UNRECORDED_POLICY_MARGIN:' + cid)
    return SCProofAudit('CONDITIONAL_REPLAY_PASS', 'FINITE_STRUCTURE_AND_REPLAY_CALLBACKS_ACCEPTED',
                        checked, actions)
