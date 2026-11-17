"""A5 synthetic physical/protocol proof tests: requires native MPFR core."""
from dataclasses import replace
from fractions import Fraction as Q
from rampd_core.interval import Interval
from rampd_core.model import BicycleParameters, StateBounds, ControlBounds
from rampd_core.reachability import integrate, TubeStatus
from rampd_core.belief import BeliefCell, SupportAtom
from rampd_core.invariant import (SafeDomain, ActionWitness, AtomTransition,
                                   ObservationSuccessors, EvidenceVerdict, EvidenceContext)
from rampd_core.protocol import (ProtocolAutomaton, ProtocolState, ProtocolTransition,
                                  TimeWindow, ClockTrace, CausalStage)
from rampd_core.observations import ObservationModel
from rampd_core.footprint import VehicleGeometry
from rampd_core.resources import ResourceRegion, ResourceState
from rampd_core.safe_continuation import SCContract
from rampd_core.a5_replay_bridge import (A5ProtocolOutcome, A5World,
    A5PhysicalObligation, replay_a5_physical, audit_a5_protocol)


def fixture():
    step = Q(1,8)
    c = ClockTrace(TimeWindow(step,step), local=TimeWindow(step,step))
    tr = ProtocolTransition('move', 'start', 'end',
                            (('external', CausalStage.EXTERNAL),), c,
                            'silence', silence=True, guard_tag='always')
    proto = ProtocolAutomaton((ProtocolState('start'),ProtocolState('end')),
                              'start', (tr,))
    from rampd_core.a5_replay_bridge import a5_world_digest, a5_clock_digest
    params = BicycleParameters(2.8,.9)
    safe = SafeDomain(StateBounds(*(Interval(-8,8) for _ in range(6))), friction=params)
    world = A5World('unset',VehicleGeometry(4,2),(),(),(),True,True,
                    ego_params=params, ego_disturbance=(Interval.point(0),)*6,
                    ego_control_bounds=ControlBounds(Interval(-2,2),Interval(-1,1)),
                    safe_domain=safe)
    world = replace(world,model_digest=a5_world_digest(world))
    contract = SCContract(proto.digest(), a5_clock_digest(proto,ObservationModel(('silence',)),step),
                          world.model_digest, 'task:toy', step, 2)
    x = StateBounds.point([0,0,0,1,0,0])
    u = ControlBounds.point(0,0)
    tube = integrate(x,u,params, float(step))
    assert tube.status is TubeStatus.VALIDATED
    src = SupportAtom('start-atom',x,mode=(('protocol_state','start'),))
    succ = SupportAtom('end-atom',tube.endpoint,mode=(('protocol_state','end'),))
    obligation = A5PhysicalObligation.seal('start-cell', 'move', src.atom_id,tube,contract)
    witness = ActionWitness('move', (0,0),
                (AtomTransition(src.atom_id,EvidenceVerdict.PROVED,obligation.evidence_ref,
                 (ObservationSuccessors('silence',(succ,)),)),))
    cell = BeliefCell('start-cell',(src,),(witness,))
    e = EvidenceContext(cell,src,witness,witness.transitions[0])
    outcome = A5ProtocolOutcome(cell.cell_id,witness.action_id,src.atom_id,'move',(succ,))
    return contract,proto,ObservationModel(('silence',)),cell,witness,outcome,obligation,e,world,safe


def test_replayed_single_public_protocol_and_physics():
    contract,proto,obs,cell,action,outcome,ob,e,world,safe = fixture()
    assert audit_a5_protocol(cell,action,contract,proto,obs,(outcome,))
    assert replay_a5_physical(e,contract,ob,world,safe)


def test_missing_or_mutated_protocol_branch_rejected():
    contract,proto,obs,cell,action,outcome,ob,e,world,safe = fixture()
    assert not audit_a5_protocol(cell,action,contract,proto,obs,())
    assert not audit_a5_protocol(cell,action,contract,proto,obs,(replace(outcome,transition_id='fake'),))
    second = ProtocolTransition('alternative','start','end',
        (('external',CausalStage.EXTERNAL),),
        ClockTrace(TimeWindow(Q(1,8),Q(1,8)),local=TimeWindow(Q(1,8),Q(1,8))),
        'silence', silence=True, guard_tag='always')
    new_proto = replace(proto,transitions=proto.transitions+(second,))
    from rampd_core.a5_replay_bridge import a5_clock_digest
    new_contract=replace(contract,protocol_digest=new_proto.digest(),
                         clock_digest=a5_clock_digest(new_proto,obs,contract.step_s))
    second_outcome = replace(outcome, transition_id='alternative',
                             successors=(replace(outcome.successors[0], atom_id='alternative-atom'),))
    # With the correct union of outcomes, the protocol gate passes.
    branches=(ObservationSuccessors('silence', outcome.successors+second_outcome.successors),)
    tr=replace(action.transitions[0], branches=branches)
    new_action=replace(action, transitions=(tr,))
    new_cell=replace(cell, actions=(new_action,))
    assert audit_a5_protocol(new_cell,new_action,new_contract,new_proto,obs,(outcome,second_outcome))
    # Omission is now tested with a valid clock and otherwise consistent inputs.
    assert not audit_a5_protocol(new_cell,new_action,new_contract,new_proto,obs,(outcome,))


def test_no_early_hidden_event_observation():
    contract,proto,obs,cell,action,outcome,ob,e,world,safe=fixture()
    early=replace(proto.transitions[0],clocks=ClockTrace(TimeWindow(Q(0),Q(0)),local=TimeWindow(Q(0),Q(0))))
    new_proto=replace(proto,transitions=(early,))
    from rampd_core.a5_replay_bridge import a5_clock_digest
    new_contract=replace(contract,protocol_digest=new_proto.digest(),
                         clock_digest=a5_clock_digest(new_proto,obs,contract.step_s))
    assert not audit_a5_protocol(cell,action,new_contract,new_proto,obs,(outcome,))


def test_incomplete_world_unknown_and_tampered_evidence_rejected():
    contract,proto,obs,cell,action,outcome,ob,e,world,safe=fixture()
    assert not replay_a5_physical(e,contract,ob,replace(world,complete_actors_assumed=False),safe)
    assert not replay_a5_physical(e,contract,replace(ob,evidence_ref='fake'),world,safe)
    assert not replay_a5_physical(e,replace(contract,model_digest='other'),ob,world,safe)
    assert not replay_a5_physical(e,contract,ob,replace(world,ego_geometry=VehicleGeometry(8,3)),safe)
    narrow = SafeDomain(StateBounds(*(Interval.point(20) for _ in range(6))))
    assert not replay_a5_physical(e,contract,ob,world,narrow)


def test_static_forbidden_resource_is_not_proved_safe():
    contract,proto,obs,cell,action,outcome,ob,e,world,safe=fixture()
    # Fixed body at origin overlaps closed resource; enclosure must be unknown.
    region=ResourceRegion('closed', Interval(-5,5),Interval(-5,5),1)
    state=ResourceState('closed',False,False,'forward',1)
    # Positive control: identical geometry but permitted occupancy.
    c,o,ctx,w = _rebind(contract,ob,e,replace(world,regions=(region,),
        resource_states=(replace(state,alpha=True,beta=True),),resource_forward_axes=(('closed',1.,0.),)))
    assert replay_a5_physical(ctx,c,o,w,safe)
    contract, ob, e, world = _rebind(contract, ob, e, replace(world, regions=(region,), resource_states=(state,)))
    assert not replay_a5_physical(e,contract,ob,world,safe)


def _rebind(contract, ob, e, world, tube=None, branches=None):
    """Reseal entire consistent context so a rejection is NOT a stale hash."""
    from rampd_core.a5_replay_bridge import a5_world_digest
    world = replace(world, model_digest=a5_world_digest(world))
    contract = replace(contract, model_digest=world.model_digest)
    ob = A5PhysicalObligation.seal(e.cell.cell_id, e.action.action_id,
                                   e.source_atom.atom_id, tube or ob.tube, contract)
    tr = replace(e.transition, evidence_ref=ob.evidence_ref,
                 branches=e.transition.branches if branches is None else branches)
    action = replace(e.action, transitions=(tr,))
    cell = replace(e.cell, actions=(action,))
    return contract, ob, EvidenceContext(cell, e.source_atom, action, tr), world


def test_resealed_world_requires_declared_model_and_disturbance():
    contract,proto,obs,cell,action,outcome,ob,e,world,safe = fixture()
    for modified in (replace(world, ego_params=BicycleParameters(3.1,.9)),
                     replace(world, ego_disturbance=(Interval(-.1,.1),)*6),
                     replace(world, ego_control_bounds=ControlBounds.point(1,0)),
                     replace(world, ego_params=None)):
        c, o, ctx, w = _rebind(contract, ob, e, modified)
        assert not replay_a5_physical(ctx,c,o,w,safe)


def test_resealed_wrong_hidden_successor_rejected():
    contract,proto,obs,cell,action,outcome,ob,e,world,safe = fixture()
    original = outcome.successors[0]
    # Same observation, another hidden alternative whose state is disjoint
    # from the true endpoint; a good first atom cannot justify this branch.
    wrong = replace(original, atom_id='wrong', ego=StateBounds.point([3,0,0,0,0,0]),
                    mode=(('protocol_state','other_end'),))
    c,o,ctx,w = _rebind(contract,ob,e,world,
        branches=(ObservationSuccessors('silence',(original,wrong)),))
    assert not replay_a5_physical(ctx,c,o,w,safe)


def test_context_membership_and_safe_domain_binding():
    contract,proto,obs,cell,action,outcome,ob,e,world,safe = fixture()
    assert not replay_a5_physical(replace(e,cell=replace(cell,actions=())),contract,ob,world,safe)
    assert not replay_a5_physical(e,contract,ob,world,
        SafeDomain(StateBounds(*(Interval(-100,100) for _ in range(6)))))


def test_protocol_unmodelled_mode_mutation_rejected():
    contract,proto,obs,cell,action,outcome,ob,e,world,safe = fixture()
    successor = replace(outcome.successors[0], mode=(('protocol_state','end'),('extra','changed')))
    tr = replace(e.transition, branches=(ObservationSuccessors('silence',(successor,)),))
    witness = replace(action, transitions=(tr,))
    current = replace(cell, actions=(witness,))
    assert not audit_a5_protocol(current,witness,contract,proto,obs,(replace(outcome,successors=(successor,)),))


def test_friction_domain_cannot_be_omitted():
    contract,proto,obs,cell,action,outcome,ob,e,world,safe = fixture()
    without_friction = replace(safe, friction=None)
    c,o,ctx,w = _rebind(contract,ob,e,replace(world,safe_domain=without_friction))
    assert not replay_a5_physical(ctx,c,o,w,without_friction)


def test_possible_occupancy_requires_entry_and_stay_permission():
    contract,proto,obs,cell,action,outcome,ob,e,world,safe = fixture()
    region=ResourceRegion('stay-closed', Interval(-5,5),Interval(-5,5),1)
    state=ResourceState('stay-closed',True,False,'forward',1)
    c,o,ctx,w = _rebind(contract,ob,e,replace(world,regions=(region,),resource_states=(state,),resource_forward_axes=((region.resource_id,1.,0.),)))
    assert not replay_a5_physical(ctx,c,o,w,safe)


def test_unmapped_constant_resource_monitor_is_not_a_protocol_proof():
    contract,proto,obs,cell,action,outcome,ob,e,world,safe = fixture()
    from rampd_core.a5_replay_bridge import a5_clock_digest
    monitored=replace(proto,states=tuple(replace(s,resource_monitor=(('lane','closed'),)) for s in proto.states))
    c=replace(contract,protocol_digest=monitored.digest(),
              clock_digest=a5_clock_digest(monitored,obs,contract.step_s))
    assert not audit_a5_protocol(cell,action,c,monitored,obs,(outcome,))


def test_resource_direction_is_world_velocity_not_speed_sign():
    contract,proto,obs,cell,action,outcome,ob,e,world,safe = fixture()
    region=ResourceRegion('lane',Interval(-5,5),Interval(-5,5),1)
    state=ResourceState('lane',True,True,'forward',1)
    for axes,expected in (((),False),((('lane',-1.,0.),),False),((('lane',1.,0.),),True)):
        c,o,ctx,w=_rebind(contract,ob,e,replace(world,regions=(region,),resource_states=(state,),resource_forward_axes=axes))
        assert replay_a5_physical(ctx,c,o,w,safe)==expected


def test_declared_clock_relations_and_change_within_step_required():
    c,proto,obs,cell,action,outcome,ob,e,world,safe=fixture()
    from rampd_core.a5_replay_bridge import a5_clock_digest
    step=c.step_s
    for clock in (ClockTrace(TimeWindow(step*2,step*2),local=TimeWindow(step,step)),
                  ClockTrace(TimeWindow(Q(0),Q(0)),local=TimeWindow(step,step),declared_relations=(('local','change'),))):
        p=replace(proto,transitions=(replace(proto.transitions[0],clocks=clock),))
        cc=replace(c,protocol_digest=p.digest(),clock_digest=a5_clock_digest(p,obs,step))
        assert not audit_a5_protocol(cell,action,cc,p,obs,(outcome,))
