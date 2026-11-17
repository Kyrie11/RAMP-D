"""A5/3b: absolute-time joint prefix/tail graph for a declared ego-only world.

Replays each edge on exact event subslabs with common branch permissions. This is an inner sufficient check, not an exact dynamic winning set.
No moving actors, continuously uncertain event schedules, pending messages or feedback.
"""
from dataclasses import dataclass, replace
from fractions import Fraction
from .a53_schedule import PermissionSchedule, exact, local_protocol, partition_family
from .a5_task_tail import A5TailResult, replay_a5_tail_edge
from .a5_replay_bridge import a5_world_digest, a5_clock_digest, _canonical_hash
from .safe_continuation import SCContract, sc_support_digest


@dataclass(frozen=True)
class A53Mission:
    world: object
    protocol: object
    observations: object
    goal: object
    schedule: PermissionSchedule
    step: Fraction
    initial_support_digest: str
    segmented_resources: bool = True
    branch_schedules: tuple[tuple[str,PermissionSchedule], ...] = ()

    def __post_init__(self):
        w=self.world; s=self.schedule
        bs=tuple((tid,sch) for tid,sch in self.branch_schedules)
        object.__setattr__(self,'branch_schedules',bs)
        if type(self.segmented_resources) is not bool or (bs and not self.segmented_resources):
            raise ValueError('branch schedules require segmented mode')
        if bs and (len({tid for tid,_ in bs})!=len(bs) or {tid for tid,_ in bs}!={t.transition_id for t in self.protocol.transitions} or
                   any(not isinstance(sch,PermissionSchedule) or (sch.start,sch.deadline,sch.resource_ids)!=(s.start,s.deadline,s.resource_ids) for _,sch in bs)):
            raise ValueError('complete independently declared schedule for every protocol transition required')
        if exact(self.step)<=0 or not self.initial_support_digest:
            raise ValueError('invalid step or root binding')
        if self.goal.deadline_s!=s.deadline-s.start:
            raise ValueError('goal duration and mission deadline disagree')
        if (w.timed_resource_slices or w.other_actors or not w.complete_actors_assumed or not w.complete_resources_assumed or
            w.safe_domain is None or w.model_digest!=a5_world_digest(w)):
            raise ValueError('only independently declared complete ego-only world supported')
        r={x.resource_id:x for x in w.regions}; rs={x.resource_id:x for x in w.resource_states}
        if len(r)!=len(w.regions) or len(rs)!=len(w.resource_states) or set(r)!=set(s.resource_ids) or set(rs)!=set(r):
            raise ValueError('world/schedule resource mismatch')
        if any(rs[k].capacity!=r[k].capacity for k in r) or any(e.capacity>r[e.resource_id].capacity for sch in (s,*(sch for _,sch in bs)) for e in sch.epochs):
            raise ValueError('schedule exceeds declared capacity')
        # All rule schedules are declared externally, independent of ego.
        # Formal controller/awareness changes require an extended model.
        if any(state.mode or state.resource_monitor or state.received_messages for state in self.protocol.states):
            raise ValueError('unmodelled protocol monitor or message state')
        if not set(self.goal.accepting_modes)<={state.state_id for state in self.protocol.states}:
            raise ValueError('unknown accepting mode')

    @property
    def digest(self):
        return _canonical_hash('a53-mission-sha256:',{'world':self.world.model_digest,
            'protocol':self.protocol.digest(),'observations':self.observations.digest(),
            'goal':self.goal.digest,'schedule':self.schedule.digest,'step':str(self.step),
            'initial_support':self.initial_support_digest,'segmented_resources':self.segmented_resources,'branch_schedules':sorted((tid,sch.digest) for tid,sch in self.branch_schedules)})

    def edge_context(self, cell, depth):
        if type(depth) is not int or depth<0: raise ValueError('invalid depth')
        start=self.schedule.start+depth*self.step; end=start+self.step
        restrictions=self.schedule.restrictions(start,end)
        states=tuple(replace(s,alpha=restrictions[s.resource_id][0],beta=restrictions[s.resource_id][1],
            direction=restrictions[s.resource_id][2],capacity=restrictions[s.resource_id][3]) for s in self.world.resource_states)
        regions=tuple(replace(r,capacity=restrictions[r.resource_id][3]) for r in self.world.regions)
        proto=local_protocol(self.protocol,(a.mode_dict.get('protocol_state') for a in cell.atoms),start,end,self.digest)
        slices=()
        if self.segmented_resources:
            # Keep maximum capacities in geometry; per-slab capacities are
            # verified from the independent schedule, not from the witness.
            regions=self.world.regions; states=self.world.resource_states
            family=dict(self.branch_schedules)
            partition=(partition_family((family[t.transition_id] for t in proto.transitions),start,end)
                       if family else self.schedule.partition(start,end))
            slices=tuple((a-start,b-start,tuple(replace(s,alpha=r[s.resource_id][0],beta=r[s.resource_id][1],
                direction=r[s.resource_id][2],capacity=r[s.resource_id][3]) for s in states))
                for a,b,r in partition)
        w=replace(self.world,regions=regions,resource_states=states,timed_resource_slices=slices,model_version=f'{self.world.model_version}:{self.digest}:{start}:{end}')
        w=replace(w,model_digest=a5_world_digest(w))
        c=SCContract(proto.digest(),a5_clock_digest(proto,self.observations,self.step),w.model_digest,
                     self.goal.digest,self.step,int((self.schedule.deadline-self.schedule.start)//self.step))
        return c,w,proto


def audit_a53_mission(mission: A53Mission, root, nodes, claimed_finish: Fraction):
    """One absolute mission clock from root through all declared prefix/tail edges.

    The entire candidate must be supplied; this does not promote an isolated
    tail or an arbitrary SC callback to an absolute mission proof.
    worst_s is duration from mission start. All aborts are UNKNOWN.
    """
    checked=tubes=0
    def require(test,why):
        if not test: raise ValueError(why)
    try:
        require(mission.schedule.start<exact(claimed_finish)<=mission.schedule.deadline,'BAD_ABSOLUTE_CLAIM')
        ns=tuple(nodes); by_id={n.cell.cell_id:n for n in ns}
        require(len(by_id)==len(ns) and len({n.cell.policy_node_id for n in ns})==len(ns),'DUPLICATE_NODE')
        require(sc_support_digest(root)==mission.initial_support_digest and root.cell_id in by_id and
                sc_support_digest(by_id[root.cell_id].cell)==mission.initial_support_digest and by_id[root.cell_id].depth==0,'ROOT_MISMATCH')
        require(not mission.goal.accepts(root),'ZERO_DURATION_ACCEPTANCE_UNSUPPORTED')
        seen=set(); todo=[root.cell_id]; leaves=[]
        while todo:
            cid=todo.pop()
            if cid in seen: continue
            seen.add(cid); n=by_id[cid]; checked+=1
            now=mission.schedule.start+n.depth*mission.step
            require(now<=mission.schedule.deadline,'ABSOLUTE_DEADLINE_EXCEEDED')
            require(all(not a.other and mission.world.safe_domain.contains_atom(a)[0] for a in n.cell.atoms),'UNSAFE_NODE')
            if n.action_id is None:
                require(not n.children and not n.outcomes and not n.obligations and mission.goal.accepts(n.cell),'TERMINAL_GOAL_NOT_PROVED')
                leaves.append(now); continue
            c,w,p=mission.edge_context(n.cell,n.depth)
            posterior,count=replay_a5_tail_edge(n,c,w,p,mission.observations); tubes+=count
            children=dict(n.children)
            require(len(children)==len(n.children) and set(children)==set(posterior),'PUBLIC_BRANCH_COVER_MISMATCH')
            for label,dst in children.items():
                require(dst in by_id and by_id[dst].depth==n.depth+1,'TIME_OR_CHILD_MISMATCH')
                require({a.atom_id:a for a in by_id[dst].cell.atoms}==posterior[label],'POSTERIOR_UNION_MISMATCH')
                todo.append(dst)
        require(seen==set(by_id) and bool(leaves),'UNREACHABLE_NODE_OR_NO_TERMINAL')
        require(max(leaves)==claimed_finish,'ABSOLUTE_FINISH_MISMATCH')
        # Reuse result carrier, but distinct status via separate subclass below.
        return A53MissionResult('DECLARED_ABSOLUTE_MISSION_PROVED','ALL_DECLARED_EDGES_REPLAYED',
                   claimed_finish-mission.schedule.start,checked,tubes)
    except (ValueError,TypeError,RuntimeError,AttributeError,KeyError,OverflowError,StopIteration) as exc:
        return A53MissionResult('UNKNOWN',str(exc),None,checked,tubes)


@dataclass(frozen=True)
class A53MissionResult(A5TailResult):
    @property
    def ok(self):
        return self.status=='DECLARED_ABSOLUTE_MISSION_PROVED'
