"""Phase A59/0: fail-closed, *conditional* Native Post -> finite SC rank bridge.

The upstream native audit is model-relative, and possible signal phases are
hidden variables, NOT public observations.  This adapter preserves each
same-observation posterior as a UNION and binds the complete signal controller
state as latent mode coordinates.  A successful local rank screen is only a
candidate for independent branch/tail/full-protocol replay, never CERTIFIED.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from fractions import Fraction

from .native_tick_guard import NativeParent, NativeSuccessor
from .native_safety_obligations import GuardSafetyAudit, guarded_physical_post
from .belief import BeliefCell, SupportAtom
from .invariant import support_subset_cell
from .safe_continuation import SCContract, SCResult, sc_support_digest

_RESERVED = ('a59:controller_id', 'a59:controller_version', 'a59:resource_id',
             'a59:phase', 'a59:since', 'a59:tick', 'a59:empty_since')


@dataclass(frozen=True)
class PhysicalRankScreen:
    status: str
    reasons: tuple[str, ...]
    observation_children: tuple[tuple[str, str], ...]
    posterior_sizes: tuple[tuple[str, int], ...]
    source_rank: int | None
    certified: bool = False
    # This gate does not verify physical actor roster completeness, dynamic
    # rule/observation branches, resource permission or accepting terminal tail.
    task_tail_verified: bool = False
    full_protocol_observation_verified: bool = False
    physical_environment_verified: bool = False


def _controller_modes(s: NativeSuccessor) -> tuple[tuple[str, str], ...]:
    c = s.controller
    return tuple(zip(_RESERVED, (
        c.controller_id, str(c.version), c.resource_id, c.phase,
        str(c.since), str(c.last_tick),
        'none' if c.empty_since is None else str(c.empty_since))))


def _attach_hidden_controller(s: NativeSuccessor) -> SupportAtom:
    """Every distinct hidden controller state stays distinct after same-label merging."""
    mode = dict(s.atom.mode)
    prior = set(mode) & set(_RESERVED)
    if prior and prior != set(_RESERVED):
        raise ValueError('partial hidden controller state in native atom')
    # Repeated closed-loop steps replace the entire prior hidden state. Never
    # union old and new phases (that would manufacture an unreachable state).
    mode.update(_controller_modes(s))
    return replace(s.atom, mode=tuple(sorted(mode.items())))


def screen_native_sc_rank(source_cell: BeliefCell,
                          parents: tuple[NativeParent, ...],
                          posterior: dict[str, tuple[NativeSuccessor, ...]],
                          audit: GuardSafetyAudit, *,
                          contract: SCContract, sc_result: SCResult,
                          target_cells: tuple[BeliefCell, ...]) -> PhysicalRankScreen:
    """Check scoped predecessor candidate without upgrading an A58 audit to proof.

    Rank and terminal policy come from a *prior* model-relative SC inner game;
    this screen does not create new certified ranks or infer missing observations.
    Trust in completeness of upstream declared guards is intentionally NOT
    granted here.  Proof adapters must replay the source/prefix/branch/tail.
    """
    if not isinstance(source_cell, BeliefCell) or not isinstance(contract, SCContract) or not isinstance(sc_result, SCResult) or not isinstance(audit, GuardSafetyAudit):
        raise TypeError('typed source, SC and native evidence required')
    parents = tuple(parents)
    targets = tuple(target_cells)
    if not parents or any(not isinstance(p, NativeParent) for p in parents) or any(not isinstance(t, BeliefCell) for t in targets):
        raise TypeError('complete native parents and typed target cells required')
    reasons = []
    source_atoms = {a.atom_id:a for a in source_cell.atoms}
    by_id = {p.atom.atom_id:p for p in parents}
    if len(by_id) != len(parents) or set(by_id) != set(source_atoms) or any(by_id[k].atom != source_atoms[k] for k in source_atoms):
        reasons.append('SOURCE_SUPPORT_OR_PARENT_MISMATCH')
    # NativeParent may be carrying an atom produced by a preceding A59 step.
    # Reject partially stamped or stale latent controller metadata before
    # projecting it into the next jointly observed posterior.
    for p in parents:
        stamp = dict(p.atom.mode)
        stamped = set(stamp) & set(_RESERVED)
        if stamped and (stamped != set(_RESERVED) or
                any(stamp[k] != v for k,v in _controller_modes(p) if k in stamp)):
            reasons.append('STALE_OR_PARTIAL_SOURCE_CONTROLLER_CONTEXT')
    if len({t.cell_id for t in targets})!=len(targets):
        reasons.append('DUPLICATE_TARGET_ID')
    if audit.status != 'CONDITIONAL_EGO_AVOIDANCE_PASS' or len(audit.parent_audits) != len(parents) or any(
            a.parent_id not in by_id or a.status != 'CONDITIONAL_EGO_AVOIDANCE_PASS'
            for a in audit.parent_audits) or {a.parent_id for a in audit.parent_audits}!=set(by_id):
        reasons.append('PHYSICAL_AUDIT_NOT_PASSING_ALL_PARENTS')
    if sc_result.contract_digest != contract.digest or sc_result.step_s != contract.step_s:
        reasons.append('SC_CONTRACT_MISMATCH')
    digests = sc_result.support_digests
    if digests.get(source_cell.cell_id) != sc_support_digest(source_cell):
        reasons.append('SOURCE_SC_SUPPORT_DIGEST_MISMATCH')
    ranks = sc_result.ranks
    src_rank = ranks.get(source_cell.cell_id)
    if type(src_rank) is not int or not 1 <= src_rank <= contract.horizon:
        reasons.append('SOURCE_RANK_UNAVAILABLE_OR_OUTSIDE_HORIZON')
    if any(p.controller.plan.tick != contract.step_s or p.controller.resource_id !=
           parents[0].controller.resource_id or p.controller.controller_id !=
           parents[0].controller.controller_id or p.controller.last_tick != parents[0].controller.last_tick
           for p in parents):
        reasons.append('TICK_OR_CONTROLLER_CONTEXT_MISMATCH')
    if not isinstance(posterior, dict) or not posterior or set(posterior) != set(audit.posterior_labels):
        reasons.append('OBSERVATION_PARTITION_MISMATCH')
        posterior = {} if not isinstance(posterior,dict) else posterior
    if {o for p in parents for o in p.observations}!=set(posterior):
        reasons.append('DECLARED_PUBLIC_OBSERVATION_NOT_FULLY_REPRESENTED')
    links = []
    counts = []
    for obs, rows in sorted(posterior.items()):
        if not isinstance(obs,str) or not obs or not isinstance(rows,(tuple,list)) or not rows:
            reasons.append('INVALID_PUBLIC_OBSERVATION');continue
        counts.append((obs,len(rows)))
        if any(not isinstance(s,NativeSuccessor) for s in rows):
            reasons.append('INVALID_POSTERIOR_SUCCESSOR');continue
        if len({(s.parent_id,s.case_id) for s in rows})!=len(rows):
            reasons.append('DUPLICATE_LATENT_POSTERIOR_CASE:'+obs);continue
        # Every source parent must be accounted for in the combined set for
        # each observation which is possible for that parent. Do NOT require
        # every parent to generate a given observation.
        for p in parents:
            if obs in p.observations and not any(s.parent_id == p.atom.atom_id for s in rows):
                reasons.append('MISSING_SOURCE_IN_PUBLIC_OBSERVATION:'+obs)
        if any(s.parent_id not in by_id for s in rows):
            reasons.append('POSTERIOR_CONTAINS_UNDECLARED_PARENT:'+obs);continue
        if any(obs not in by_id[s.parent_id].observations for s in rows):
            reasons.append('HIDDEN_OBSERVATION_NOT_DECLARED_FOR_PARENT:'+obs);continue
        try:
            support = tuple(_attach_hidden_controller(s) for s in rows)
        except ValueError:
            reasons.append('LATENT_CONTROLLER_MODE_CONFLICT');continue
        candidates = [t for t in targets
                      if digests.get(t.cell_id) == sc_support_digest(t)
                      and type(ranks.get(t.cell_id)) is int
                      and src_rank is not None and ranks[t.cell_id]<src_rank
                      and support_subset_cell(support,t)]
        if not candidates:
            reasons.append('NO_RANK_DECREASING_JOINT_POSTERIOR_COVER:'+obs)
        else:
            target=min(candidates,key=lambda t:t.cell_id)
            links.append((obs,target.cell_id))
    return PhysicalRankScreen('CONDITIONAL_PHYSICAL_RANK_PREDECESSOR_CANDIDATE'
                              if not reasons else 'UNKNOWN',
                              tuple(sorted(set(reasons))),tuple(links),tuple(counts),src_rank)


def native_sc_predecessor(source_cell, parents, control, *, contract, sc_result,
                          target_cells, params, ego_geometry, disturbance,
                          resource, queue_a, queue_b, limits, options=None,
                          max_cases=100000):
    """Actually execute MPFR Native Post and its A58 per-slab audit before rank screening."""
    parents=tuple(parents)
    status,posterior,tubes,audit=guarded_physical_post(
        parents,control,params=params,ego_geometry=ego_geometry,
        disturbance=disturbance,resource=resource,queue_a=queue_a,
        queue_b=queue_b,limits=limits,options=options,max_cases=max_cases)
    screen=screen_native_sc_rank(source_cell,parents,posterior,audit,
                contract=contract,sc_result=sc_result,target_cells=tuple(target_cells))
    return status,posterior,tubes,audit,screen
