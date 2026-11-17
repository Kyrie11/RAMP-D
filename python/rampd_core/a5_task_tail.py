"""A5/2: composed proof for a declared finite, step-relative static toy world.

No moving other-agent tubes, dynamic monitors, feedback, or message clocks.
Observation labels are a declared symbolic model, not inferred sensor truth.
A successful result is a conditional finite physical task-completion witness,
not a full RAMP-D real-scene or unrestricted-continuous certificate.
"""
from __future__ import annotations
from dataclasses import dataclass
from fractions import Fraction
from .belief import BeliefCell
from .model import StateBounds
from .invariant import EvidenceContext
from .protocol import ProtocolAutomaton
from .observations import ObservationModel
from .safe_continuation import SCContract, sc_support_digest
from .a5_replay_bridge import (A5World, A5ProtocolOutcome, A5PhysicalObligation,
    audit_a5_protocol, replay_a5_physical, a5_world_digest, a5_clock_digest,
    _canonical_hash)


@dataclass(frozen=True)
class A5TaskGoal:
    """An independent task predicate: all state coordinates and protocol mode.

    The model must explicitly use *step-relative* event and observation clocks.
    The box is a terminal target in the declared bicycle reference frame.
    """
    target: StateBounds
    accepting_modes: tuple[str, ...]
    deadline_s: Fraction
    version: str

    def __post_init__(self):
        modes = tuple(self.accepting_modes)
        if (not isinstance(self.target, StateBounds) or not modes or
            any(not isinstance(m,str) or not m for m in modes) or
            len(set(modes)) != len(modes) or type(self.deadline_s) is not Fraction or
            self.deadline_s <= 0 or not isinstance(self.version,str) or not self.version):
            raise ValueError('invalid independently declared task goal')
        object.__setattr__(self,'accepting_modes',tuple(sorted(modes)))

    @property
    def digest(self):
        return _canonical_hash('a5-task-goal-sha256:', {
            'scope':'STATIC_STEP_RELATIVE_SYNTHETIC', 'version':self.version,
            'target':[[x.lo.hex(),x.hi.hex()] for x in self.target.as_tuple()],
            'accepting_modes':self.accepting_modes, 'deadline':str(self.deadline_s)})

    def accepts(self, cell: BeliefCell):
        return all(not a.other and self.target.contains(a.ego) and
                   a.mode_dict.get('protocol_state') in self.accepting_modes for a in cell.atoms)


@dataclass(frozen=True)
class A5TailNode:
    cell: BeliefCell
    depth: int
    action_id: str | None = None
    children: tuple[tuple[str,str],...] = ()
    outcomes: tuple[A5ProtocolOutcome,...] = ()
    obligations: tuple[A5PhysicalObligation,...] = ()

    def __post_init__(self):
        if type(self.depth) is not int or self.depth < 0:
            raise ValueError('nonnegative depth required')
        for name in ('children','outcomes','obligations'):
            seq = getattr(self,name)
            object.__setattr__(self,name,tuple(tuple(x) for x in seq) if name=='children' else tuple(seq))


@dataclass(frozen=True)
class A5TailResult:
    status: str
    reason: str
    worst_s: Fraction | None = None
    checked_nodes: int = 0
    checked_tubes: int = 0
    model_relative_only: bool = True

    @property
    def ok(self):
        return self.status == 'DECLARED_STATIC_TASK_TAIL_PROVED'


def audit_a5_task_tail(root: BeliefCell, nodes: tuple[A5TailNode,...],
                       contract: SCContract, goal: A5TaskGoal, world: A5World,
                       protocol: ProtocolAutomaton, observations: ObservationModel,
                       claimed_max_s: Fraction) -> A5TailResult:
    """Recompute every reachable edge and exact temporal budget. No callbacks.

    root, goal, world, protocol and contract are independent problem inputs.
    A node is one public information history (or an explicitly merged cell).
    Every same-label outcome across all source atoms must be in its one child.
    Require exact atom union, not independent marginals or ID-only cover.
    """
    checked = tubes = 0
    def require(condition, reason):
        if not condition:
            raise ValueError(reason)
    try:
        require(type(claimed_max_s) is Fraction and 0 < claimed_max_s <= goal.deadline_s,
                'BAD_CLAIMED_TIME')
        require(contract.task_digest == goal.digest and contract.model_digest == a5_world_digest(world)
                and world.model_digest == contract.model_digest and world.safe_domain is not None and
                world.complete_actors_assumed and world.complete_resources_assumed and
                contract.protocol_digest == protocol.digest() and
                contract.clock_digest == a5_clock_digest(protocol,observations,contract.step_s),
                'CONTEXT_MISMATCH')
        require(not world.other_actors, 'OTHER_ACTOR_ABSOLUTE_TIME_UNSUPPORTED')
        # Only local step-relative symbolic observations; absolute message/effectivity
        # clocks cannot be restarted at each tail node. No resource monitor dynamics.
        require(all(t.message is None and t.clocks.issue is None and t.clocks.receipt is None
                    and t.clocks.change.hi <= contract.step_s and not t.silence_exclusion_proved
                    and t.silence_evidence is None for t in protocol.transitions),
                'UNSUPPORTED_PROTOCOL_CLOCK')
        require(set(goal.accepting_modes) <= {s.state_id for s in protocol.states}, 'UNKNOWN_ACCEPTING_MODE')
        nodes = tuple(nodes)
        by_id = {n.cell.cell_id:n for n in nodes}
        require(len(by_id)==len(nodes) and len({n.cell.policy_node_id for n in nodes})==len(nodes),
                'DUPLICATE_PUBLIC_NODE')
        require(root.cell_id in by_id and by_id[root.cell_id].depth==0 and
                sc_support_digest(root)==sc_support_digest(by_id[root.cell_id].cell), 'ROOT_MISMATCH')
        # Zero-duration accepting root needs a separate instantaneous resource
        # proof; do not return a positive certificate without a physical step.
        require(not goal.accepts(root), 'ZERO_DURATION_ACCEPTANCE_UNSUPPORTED')
        todo=[root.cell_id]; seen=set(); leaves=[]
        while todo:
            cid=todo.pop()
            if cid in seen: continue
            seen.add(cid); n=by_id[cid]; checked+=1
            require(n.depth*contract.step_s <= goal.deadline_s, 'DEADLINE_EXCEEDED')
            require(all(not a.other and world.safe_domain.contains_atom(a)[0] for a in n.cell.atoms),
                    'UNSAFE_NODE')
            if n.action_id is None:
                require(not n.children and not n.outcomes and not n.obligations and goal.accepts(n.cell),
                        'TERMINAL_GOAL_NOT_PROVED')
                leaves.append(n.depth*contract.step_s); continue
            require(n.depth*contract.step_s < goal.deadline_s, 'NONACCEPTING_AT_DEADLINE')
            action=next((a for a in n.cell.actions if a.action_id==n.action_id),None)
            require(action is not None and audit_a5_protocol(n.cell,action,contract,protocol,observations,n.outcomes),
                    'PROTOCOL_REPLAY_UNPROVED')
            obs_atoms={}; omap={o.source_atom_id:o for o in n.obligations}
            require(len(omap)==len(n.obligations) and set(omap)=={a.atom_id for a in n.cell.atoms},
                    'PHYSICAL_OBLIGATIONS_INCOMPLETE')
            sources={a.atom_id:a for a in n.cell.atoms}
            for tr in action.transitions:
                ctx=EvidenceContext(n.cell,sources[tr.source_atom_id],action,tr)
                require(replay_a5_physical(ctx,contract,omap[tr.source_atom_id],world,world.safe_domain),
                        'PHYSICAL_REPLAY_UNPROVED')
                tubes+=1
                for branch in tr.branches:
                    merged=obs_atoms.setdefault(branch.observation,{})
                    for a in branch.atoms:
                        require(a.atom_id not in merged or merged[a.atom_id]==a, 'ATOM_ID_COLLISION')
                        merged[a.atom_id]=a
            child=dict(n.children)
            require(len(child)==len(n.children) and set(child)==set(obs_atoms),'PUBLIC_BRANCH_COVER_MISMATCH')
            for label, dst in child.items():
                require(dst in by_id and by_id[dst].depth==n.depth+1, 'TIME_OR_CHILD_MISMATCH')
                require({a.atom_id:a for a in by_id[dst].cell.atoms}==obs_atoms[label], 'POSTERIOR_UNION_MISMATCH')
                todo.append(dst)
        require(seen==set(by_id) and bool(leaves), 'UNREACHABLE_NODE_OR_NO_TERMINAL')
        worst=max(leaves)
        require(worst==claimed_max_s, 'WORST_TIME_MISMATCH')
        return A5TailResult('DECLARED_STATIC_TASK_TAIL_PROVED','ALL_DECLARED_BRANCHES_REPLAYED',worst,checked,tubes)
    except (ValueError, TypeError, RuntimeError, KeyError, AttributeError, OverflowError, StopIteration) as e:
        return A5TailResult('UNKNOWN',str(e),None,checked,tubes)


def _tail_policy_digest(nodes: tuple[A5TailNode,...], contract: SCContract) -> str:
    """Stable identity of selected policy and proof references, not a proof."""
    rows=[]
    for n in sorted(nodes,key=lambda n:n.cell.cell_id):
        a=next((a for a in n.cell.actions if a.action_id==n.action_id),None)
        rows.append({'support':sc_support_digest(n.cell),'depth':n.depth,
                     'action':n.action_id,'control':None if a is None else [v.hex() for v in a.control],
                     'children':sorted(n.children),
                     'physical_refs':sorted(o.evidence_ref for o in n.obligations),
                     'protocol_outcomes':sorted((o.source_atom_id,o.transition_id,
                       sc_support_digest(BeliefCell('outcome',o.successors))) for o in n.outcomes)})
    return _canonical_hash('a5-tail-policy-sha256:',{'contract':contract.digest,'nodes':rows})


def seal_a5_terminal(root: BeliefCell, nodes: tuple[A5TailNode,...],
                     contract: SCContract, goal: A5TaskGoal, world: A5World,
                     protocol: ProtocolAutomaton, observations: ObservationModel,
                     claimed_max_s: Fraction):
    """Produce SC's existing terminal record ONLY after the composed audit.

    The bound is a duration from this tail root, not an absolute mission time.
    SC's inherited prefix+tail completion still needs a mission-deadline check.
    Margin is not implemented by this checker and must remain None.
    """
    from .safe_continuation import TerminalTailCertificate
    nodes=tuple(nodes)
    result=audit_a5_task_tail(root,nodes,contract,goal,world,protocol,observations,claimed_max_s)
    if not result.ok: raise ValueError(result.reason)
    digest=_tail_policy_digest(nodes,contract)
    ref=_canonical_hash('a5-tail-proof-sha256:',{'root':sc_support_digest(root),
        'policy':digest,'contract':contract.digest,'duration':str(result.worst_s)})
    return TerminalTailCertificate(root.cell_id,digest,ref,result.worst_s,contract.protocol_digest,
            contract.clock_digest,contract.model_digest,contract.task_digest,margin_lower=None)


def replay_a5_terminal(root, certificate, contract, *, nodes, goal, world, protocol, observations):
    """Concrete terminal_replayer for the existing SC API; reseal & compare."""
    from .safe_continuation import TerminalTailCertificate
    if not isinstance(certificate,TerminalTailCertificate) or certificate.margin_lower is not None:
        return False
    try:
        expected=seal_a5_terminal(root,nodes,contract,goal,world,protocol,observations,certificate.max_tail_s)
        return certificate==expected
    except (ValueError,TypeError,RuntimeError,KeyError,AttributeError,OverflowError):
        return False
