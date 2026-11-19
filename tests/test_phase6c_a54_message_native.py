from fractions import Fraction as Q
from dataclasses import replace
from rampd_core.a54_message_mission import DeclaredHistory,compile_histories
from rampd_core.a53b_event_clock import MessageWorld
from rampd_core.a53_schedule import PermissionSchedule,PermissionEpoch
from rampd_core.a53_mission import audit_a53_mission
from rampd_core.a5_task_tail import A5TaskGoal,A5TailNode
from rampd_core.a5_replay_bridge import A5PhysicalObligation,A5ProtocolOutcome,exact_step_endpoint,a5_world_digest
from rampd_core.belief import BeliefCell,SupportAtom
from rampd_core.invariant import ActionWitness,AtomTransition,ObservationSuccessors,EvidenceVerdict
from rampd_core.model import StateBounds,ControlBounds
from rampd_core.interval import Interval
from rampd_core.resources import ResourceRegion,ResourceState
from rampd_core.reachability import integrate,TubeStatus
from rampd_core.exact_time import binary64_bracket
from test_phase6c_a5_bridge import fixture


def candidate(*,near=False):
    _,_,_,_,_,_,_,_,world,_=fixture(); dt=Q(1,10); start=Q(10); end=start+2*dt
    # A closure on a distant resource is compatible with the same public action;
    # the near-resource variant must be rejected even while the message is silent.
    region=ResourceRegion('r',Interval(-5,5) if near else Interval(30,40),Interval(-5,5),1)
    world=replace(world,regions=(region,),resource_states=(ResourceState('r',True,True,'forward',1),),resource_forward_axes=(('r',1.,0.),))
    world=replace(world,model_digest=a5_world_digest(world))
    open_epoch=PermissionEpoch('r',start,end+dt,True,True,'forward',1,'fixture')
    open_schedule=PermissionSchedule(start,end,('r',),(open_epoch,))
    close_schedule=PermissionSchedule(start,end,('r',),(replace(open_epoch,off=start+dt/2),replace(open_epoch,on=start+dt/2,alpha=False,beta=False)))
    compiled=compile_histories((DeclaredHistory('open',open_schedule),DeclaredHistory('drop',close_schedule,(MessageWorld('drop','m','closure',start,None,'fixture'),)),DeclaredHistory('received',close_schedule,(MessageWorld('received','m','closure',start,start+dt+dt/2,'fixture'),))),dt)
    root=BeliefCell('root',(SupportAtom('a',StateBounds.point([0,0,0,1,0,0]),mode=(('protocol_state',compiled.protocol.initial_state_id),)),))
    target=StateBounds(Interval(.19,.21),Interval(-.01,.01),Interval(-.01,.01),Interval(.99,1.01),Interval(-.01,.01),Interval(-.01,.01))
    goal=A5TaskGoal(target,compiled.terminal_modes,2*dt,'fixture')
    mission=compiled.mission(world,root,goal); nodes=[]
    def build(cell,depth):
        if depth==2:
            nodes.append(A5TailNode(cell,depth));return
        contract,w,p=mission.edge_context(cell,depth); outcomes=[]; obs_atoms={}; obligations=[]; transitions=[]
        for a in cell.atoms:
            tube=integrate(a.ego,ControlBounds.point(0,0),w.ego_params,binary64_bracket(dt)[1]);assert tube.status is TubeStatus.VALIDATED
            endpoint=exact_step_endpoint(tube,dt); ob=A5PhysicalObligation.seal(cell.cell_id,'coast',a.atom_id,tube,contract);obligations.append(ob)
            groups={}
            for e in p.outgoing(a.mode_dict['protocol_state']):
                child=SupportAtom(a.atom_id+'-'+e.transition_id,endpoint,mode=(('protocol_state',e.target_state_id),)); groups.setdefault(e.observation,[]).append(child);obs_atoms.setdefault(e.observation,[]).append(child)
                outcomes.append(A5ProtocolOutcome(cell.cell_id,'coast',a.atom_id,e.transition_id,(child,)))
            transitions.append(AtomTransition(a.atom_id,EvidenceVerdict.PROVED,ob.evidence_ref,tuple(ObservationSuccessors(o,tuple(v)) for o,v in groups.items())))
        children=tuple((o,cell.cell_id+'-'+str(i)) for i,o in enumerate(sorted(obs_atoms)))
        cell=replace(cell,actions=(ActionWitness('coast',(0,0),tuple(transitions)),));nodes.append(A5TailNode(cell,depth,'coast',children,tuple(outcomes),tuple(obligations)))
        for o,cid in children:build(BeliefCell(cid,tuple(obs_atoms[o])),depth+1)
    build(root,0)
    return mission,nodes[0].cell,tuple(nodes),end


def test_compiled_history_physical_mission_and_silence_union():
    args=candidate(); result=audit_a53_mission(*args);assert result.ok,result.reason
    m,root,nodes,end=args
    assert len(nodes[1].cell.atoms)==3 and len(nodes[1].children)==2
    broken=replace(nodes[1],children=nodes[1].children[:1])
    assert not audit_a53_mission(m,root,(nodes[0],broken,*nodes[2:]),end).ok
    assert not audit_a53_mission(*candidate(near=True)).ok


def test_mode_conditioned_resource_slices_are_bound_and_keep_correlation():
    m,root,nodes,end=candidate(); middle=nodes[1].cell
    c,w,p=m.edge_context(middle,1)
    rows=dict(w.timed_slices_by_mode)
    assert set(rows)=={a.mode_dict['protocol_state'] for a in middle.atoms}
    assert {rr[0][2][0].alpha for rr in rows.values()}=={True,False}
    assert not w.timed_resource_slices[0][2][0].alpha # global meet still available as diagnostic
    assert a5_world_digest(replace(w,timed_slices_by_mode=()))!=w.model_digest
