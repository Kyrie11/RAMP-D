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
    world = A5World('unset',VehicleGeometry(4,2),(),(),(),True,True)
    world = replace(world,model_digest=a5_world_digest(world))
    contract = SCContract(proto.digest(), a5_clock_digest(proto,ObservationModel(('silence',)),step),
                          world.model_digest, 'task:toy', step, 2)
    x = StateBounds.point([0,0,0,0,0,0])
    u = ControlBounds.point(0,0)
    tube = integrate(x,u,BicycleParameters(2.8,.9), float(step))
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
    safe = SafeDomain(StateBounds(*(Interval(-8,8) for _ in range(6))))
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
    new_contract=replace(contract,protocol_digest=new_proto.digest())
    assert not audit_a5_protocol(cell,action,new_contract,new_proto,obs,(outcome,))


def test_no_early_hidden_event_observation():
    contract,proto,obs,cell,action,outcome,ob,e,world,safe=fixture()
    early=replace(proto.transitions[0],clocks=ClockTrace(TimeWindow(Q(0),Q(0)),local=TimeWindow(Q(0),Q(0))))
    new_proto=replace(proto,transitions=(early,))
    assert not audit_a5_protocol(cell,action,replace(contract,protocol_digest=new_proto.digest()),new_proto,obs,(outcome,))


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
    assert not replay_a5_physical(e,contract,ob,
       replace(world,regions=(region,),resource_states=(state,)),safe)
