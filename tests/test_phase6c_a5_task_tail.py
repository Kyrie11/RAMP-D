from dataclasses import replace
from fractions import Fraction as Q
import pytest
from rampd_core.a5_task_tail import A5TaskGoal,A5TailNode,audit_a5_task_tail
from rampd_core.a5_replay_bridge import (A5PhysicalObligation,A5ProtocolOutcome,a5_clock_digest,exact_step_endpoint)
from rampd_core.exact_time import binary64_bracket
from rampd_core.belief import BeliefCell,SupportAtom
from rampd_core.invariant import ActionWitness,AtomTransition,ObservationSuccessors,EvidenceVerdict
from rampd_core.model import StateBounds,ControlBounds
from rampd_core.interval import Interval
from rampd_core.reachability import integrate,TubeStatus
from rampd_core.protocol import ProtocolState,ClockTrace,TimeWindow
from test_phase6c_a5_bridge import fixture


def scenario(step=Q(1,10),bad_goal=False,public_branch=False):
    c,proto,obs,_,_,_,_,_,world,_=fixture()
    clock=ClockTrace(TimeWindow(step,step),local=TimeWindow(step,step))
    first=replace(proto.transitions[0],target_state_id='mid',clocks=clock)
    second=replace(first,transition_id='finish',source_state_id='mid',target_state_id='end')
    # two indistinguishable modes at the intermediate public history
    alt=replace(first,transition_id='alt',target_state_id='mid2')
    alt2=replace(second,transition_id='finish2',source_state_id='mid2')
    proto=replace(proto,states=proto.states+(ProtocolState('mid'),ProtocolState('mid2')),
                  transitions=(first,alt,second,alt2))
    if public_branch:
        from rampd_core.observations import ObservationModel
        obs=ObservationModel(('silence','seen'))
        early=replace(first,transition_id='early',target_state_id='end',observation='seen',silence=False)
        proto=replace(proto,transitions=proto.transitions+(early,))
    target=StateBounds(Interval(float(step*2)-.01,float(step*2)+.01),Interval(-.01,.01),
                       Interval(-.01,.01),Interval(.99,1.01),Interval(-.01,.01),Interval(-.01,.01))
    if public_branch: target=replace(target,px=Interval(float(step)-.01,float(step*2)+.01))
    if bad_goal: target=StateBounds.point([20,0,0,1,0,0])
    goal=A5TaskGoal(target,('end',),step*2,'straight-goal')
    c=replace(c,protocol_digest=proto.digest(),clock_digest=a5_clock_digest(proto,obs,step),
              task_digest=goal.digest,step_s=step)
    atoms=(SupportAtom('root-a',StateBounds.point([0,0,0,1,0,0]),mode=(('protocol_state','start'),)),)
    nodes=[]; early_atoms=[]
    for depth,nid in enumerate(('root','middle')):
        action_id='coast'; transitions=[]; outcomes=[]; obligations=[]; next_atoms=[]
        for a in atoms:
            tube=integrate(a.ego,ControlBounds.point(0,0),world.ego_params,binary64_bracket(step)[1])
            assert tube.status is TubeStatus.VALIDATED
            endpoint=exact_step_endpoint(tube,step)
            ob=A5PhysicalObligation.seal(nid,action_id,a.atom_id,tube,c)
            obligations.append(ob); successors={}
            for edge in proto.outgoing(a.mode_dict['protocol_state']):
                atom=SupportAtom(a.atom_id+'-'+edge.transition_id,endpoint,mode=(('protocol_state',edge.target_state_id),))
                successors.setdefault(edge.observation,[]).append(atom)
                if edge.observation=='seen': early_atoms.append(atom)
                else: next_atoms.append(atom)
                outcomes.append(A5ProtocolOutcome(nid,action_id,a.atom_id,edge.transition_id,(atom,)))
            transitions.append(AtomTransition(a.atom_id,EvidenceVerdict.PROVED,ob.evidence_ref,
                               tuple(ObservationSuccessors(label,tuple(atoms)) for label,atoms in successors.items())))
        cell=BeliefCell(nid,atoms,(ActionWitness(action_id,(0,0),tuple(transitions)),))
        children=(('silence','middle' if depth==0 else 'goal'),)
        if depth==0 and public_branch: children+=(('seen','early-goal'),)
        nodes.append(A5TailNode(cell,depth,action_id,children,tuple(outcomes),tuple(obligations)))
        atoms=tuple(next_atoms)
    nodes.append(A5TailNode(BeliefCell('goal',atoms),2))
    if public_branch: nodes.append(A5TailNode(BeliefCell('early-goal',tuple(early_atoms)),1))
    return nodes[0].cell,tuple(nodes),c,goal,world,proto,obs,step*2


@pytest.mark.parametrize('step',[Q(1,8),Q(1,10),Q(1,3)])
def test_exact_task_tail_multiple_hidden_modes(step):
    args=scenario(step); r=audit_a5_task_tail(*args)
    assert r.ok,r.reason
    assert r.worst_s==step*2 and r.checked_tubes==3 and r.checked_nodes==3


def test_wrong_child_and_missing_physical_proof_rejected():
    root,nodes,*rest=scenario()
    for middle in (replace(nodes[1],cell=replace(nodes[1].cell,atoms=nodes[1].cell.atoms[:1])),
                   replace(nodes[1],obligations=nodes[1].obligations[:1]),replace(nodes[1],depth=0),
                   replace(nodes[1],action_id=None,children=(),outcomes=(),obligations=())):
        assert not audit_a5_task_tail(root,(nodes[0],middle,nodes[2]),*rest).ok


def test_false_terminal_or_deadline_rejected():
    root,nodes,c,goal,world,proto,obs,claim=scenario()
    assert not audit_a5_task_tail(root,nodes,c,goal,world,proto,obs,Q(1,10)).ok
    r=audit_a5_task_tail(*scenario(bad_goal=True))
    assert not r.ok and r.reason=='TERMINAL_GOAL_NOT_PROVED'


def test_exact_endpoint_not_rounded_endpoint():
    args=scenario(Q(1,10)); tube=args[1][0].obligations[0].tube
    endpoint=exact_step_endpoint(tube,Q(1,10))
    assert Q.from_float(endpoint.px.lo)<=Q(1,10)<=Q.from_float(endpoint.px.hi)
    assert Q.from_float(tube.requested_horizon_s)>Q(1,10)
    with pytest.raises(ValueError): exact_step_endpoint(tube,Q(1,9))


def test_terminal_replayer_integration_and_no_fabricated_margin():
    from functools import partial
    from rampd_core.a5_task_tail import seal_a5_terminal,replay_a5_terminal
    from rampd_core.safe_continuation import compute_sc_inner
    root,nodes,c,goal,world,proto,obs,claim=scenario()
    cert=seal_a5_terminal(root,nodes,c,goal,world,proto,obs,claim)
    replay=partial(replay_a5_terminal,nodes=nodes,goal=goal,world=world,protocol=proto,observations=obs)
    assert replay(root,cert,c) and cert.margin_lower is None
    assert not replay(root,replace(cert,margin_lower=Q(1,2)),c)
    assert not replay(root,replace(cert,tail_policy_digest='forged'),c)
    assert not replay(root,replace(cert,max_tail_s=Q(1,10)),c)
    sc=compute_sc_inner((root,),world.safe_domain,c,(cert,),evidence_replayer=None,
                       branch_cover_replayer=None,terminal_replayer=replay)
    assert sc.ranks[root.cell_id]==0 and sc.completion_upper_s[root.cell_id]==claim
    assert not sc.certified_full_support


def test_distinct_public_observations_and_unequal_tail_durations():
    root,nodes,c,goal,world,proto,obs,claim=scenario(public_branch=True)
    r=audit_a5_task_tail(root,nodes,c,goal,world,proto,obs,claim)
    assert r.ok,r.reason
    assert r.checked_nodes==4 and r.worst_s==Q(1,5)
    broken=replace(nodes[0],children=nodes[0].children[:1])
    assert not audit_a5_task_tail(root,(broken,*nodes[1:]),c,goal,world,proto,obs,claim).ok
