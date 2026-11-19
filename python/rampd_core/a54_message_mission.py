"""Compile a finite exhaustive declared schedule/message relation into A53Mission.

Each hidden world persists across steps. Public ingress is sampled at decision
boundaries; payload and receipt timestamp become public only when received.
The compiler does not model traffic-dependent guards, observation errors, or
prove that the supplied worlds cover reality. The underlying physical replay
uses the meet of outgoing schedules for each source atom mode (root meet for
all histories), while one common action is verified across the public support.
"""
from dataclasses import dataclass
from fractions import Fraction as Q
import json, hashlib
from .a53_schedule import PermissionSchedule, exact
from .a53b_event_clock import MessageWorld
from .protocol import ProtocolAutomaton, ProtocolState, ProtocolTransition, ClockTrace, TimeWindow, CausalStage

@dataclass(frozen=True)
class DeclaredHistory:
    history_id: str
    schedule: PermissionSchedule
    # message_id and payload_ref MUST be canonical PUBLIC ingress fields,
    # not private source-world or simulator provenance identifiers.
    messages: tuple[MessageWorld,...] = ()
    def __post_init__(self):
        msgs=tuple(self.messages); object.__setattr__(self,'messages',msgs)
        if not self.history_id or not isinstance(self.schedule,PermissionSchedule): raise ValueError('history identity/schedule required')
        if any(not isinstance(m,MessageWorld) for m in msgs) or len({m.message_id for m in msgs})!=len(msgs): raise ValueError('unique report identity required in each history')
        # No unmodelled prior public receipt; this compiler starts before ingress.
        if any(m.receipt is not None and m.receipt<=self.schedule.start for m in msgs): raise ValueError('pre-root receipts need an explicit initial observation relation')

    def observation(self,a,b):
        if not self.schedule.start<=exact(a)<exact(b)<=self.schedule.deadline: raise ValueError('observation outside mission')
        received=sorted((m.receipt,m.message_id,m.payload_ref) for m in self.messages if m.receipt is not None and a<m.receipt<=b)
        # Encode actual public content, never world id, hidden issue or next arrival.
        return 'silence' if not received else 'ingress:'+json.dumps([(str(t),i,p) for t,i,p in received],separators=(',',':'),ensure_ascii=False)

@dataclass(frozen=True)
class CompiledHistories:
    protocol: ProtocolAutomaton
    labels: tuple[str,...]
    branch_schedules: tuple
    step: Q
    base_schedule: PermissionSchedule
    terminal_modes: tuple[str,...]
    manifest_digest: str

    def mission(self,world,root,goal):
        from dataclasses import replace
        from .a53_mission import A53Mission
        from .observations import ObservationModel
        from .safe_continuation import sc_support_digest
        if any(a.mode_dict.get('protocol_state')!=self.protocol.initial_state_id for a in root.atoms): raise ValueError('root must represent shared pre-ingress support')
        # Caller supplies physical task goal and allowed completion modes. Do not
        # replace it silently; helper declares only generated final-depth modes.
        if not set(goal.accepting_modes)<=set(self.terminal_modes): raise ValueError('goal needs declared terminal modes')
        return A53Mission(world,self.protocol,ObservationModel(self.labels),goal,self.base_schedule,self.step,sc_support_digest(root),branch_schedules=self.branch_schedules)


def compile_histories(histories,step):
    histories=tuple(histories)
    if not histories or any(not isinstance(h,DeclaredHistory) for h in histories) or len({h.history_id for h in histories})!=len(histories) or exact(step)<=0: raise ValueError('nonempty unique histories and positive step required')
    histories=tuple(sorted(histories,key=lambda h:h.history_id)); base=histories[0].schedule
    if any((h.schedule.start,h.schedule.deadline,h.schedule.resource_ids)!=(base.start,base.deadline,base.resource_ids) for h in histories): raise ValueError('incompatible history schedules')
    span=(base.deadline-base.start)/step
    if span.denominator!=1 or span<1: raise ValueError('mission grid does not tile deadline')
    N=int(span); root='history-root'; states=[ProtocolState(root)]; edges=[]; schedules=[]; labels={'silence'}; terminals=[]
    manifest=[(h.history_id,h.schedule.digest,[(m.message_id,m.payload_ref,str(m.issue),str(m.receipt),m.source_ref,m.world_id) for m in sorted(h.messages,key=lambda m:m.message_id)]) for h in histories]
    digest=hashlib.sha256(json.dumps([str(step),manifest],ensure_ascii=False,separators=(',',':')).encode()).hexdigest()
    for i,h in enumerate(histories):
        previous=root
        for k in range(1,N+1):
            a=base.start+(k-1)*step; b=a+step
            target=f'history:{i}:{k}'; tid=f'history-edge:{i}:{k}'; obs=h.observation(a,b); labels.add(obs)
            states.append(ProtocolState(target))
            # `change` here is the unrolled macro-transition boundary, NOT the
            # physical rule on-time or hidden issue. Actual effectivity is in
            # the schedule and ingress in the manifest, both digest-bound.
            edges.append(ProtocolTransition(tid,previous,target,((tid,CausalStage.MESSAGE_OBSERVATION),),ClockTrace(TimeWindow(b,b),local=TimeWindow(b,b)),obs,silence=obs=='silence',guard_tag='always'))
            schedules.append((tid,h.schedule)); previous=target
        terminals.append(previous)
    return CompiledHistories(ProtocolAutomaton(tuple(states),root,tuple(edges),version='a54-history:'+digest),tuple(sorted(labels)),tuple(schedules),step,base,tuple(terminals),digest)
