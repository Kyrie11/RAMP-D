from fractions import Fraction as Q
from dataclasses import replace
import pytest
from rampd_core.a53_mission import A53Mission,audit_a53_mission
from rampd_core.a53_schedule import PermissionSchedule,PermissionEpoch
from rampd_core.a5_replay_bridge import A5PhysicalObligation,a5_world_digest,exact_step_endpoint
from rampd_core.protocol import TimeWindow
from rampd_core.resources import ResourceRegion,ResourceState
from rampd_core.interval import Interval
from rampd_core.safe_continuation import sc_support_digest
from test_phase6c_a5_task_tail import scenario


def example(*,closed_near=False,far=False,close_at_end=False,rotate=False):
    root,nodes,c,goal,world,proto,obs,duration=scenario(public_branch=True)
    start=Q(10); stop=start+duration; dt=c.step_s
    # Protocol states are time-unrolled; old relative offset is not reused.
    def shift(edge):
        off=start+(0 if edge.source_state_id=='start' else dt)
        def add(w): return TimeWindow(w.lo+off,w.hi+off)
        return replace(edge,clocks=replace(edge.clocks,change=add(edge.clocks.change),local=add(edge.clocks.local)))
    proto=replace(proto,transitions=tuple(shift(e) for e in proto.transitions))
    if closed_near or far or rotate:
        region=ResourceRegion('lane',Interval(30,40) if far else Interval(-5,5),Interval(-5,5),1)
        state=ResourceState('lane',True,True,'forward',1)
        world=replace(world,regions=(region,),resource_states=(state,),resource_forward_axes=(('lane',1.,0.),))
        world=replace(world,model_digest=a5_world_digest(world))
        # Closure exactly at the terminal boundary must be checked too.
        when=stop if close_at_end else start+dt
        epochs=(PermissionEpoch('lane',start,when,True,True,'forward',1,'plan'),
                PermissionEpoch('lane',when,stop+dt,rotate,rotate,'reverse' if rotate else 'forward',1,'plan'))
        schedule=PermissionSchedule(start,stop,('lane',),epochs)
    else: schedule=PermissionSchedule(start,stop,(),())
    m=A53Mission(world,proto,obs,goal,schedule,dt,sc_support_digest(root)); new=[]
    for n in nodes:
        if n.action_id is None: new.append(n);continue
        lc,w,p=m.edge_context(n.cell,n.depth)
        obs2=tuple(A5PhysicalObligation.seal(o.cell_id,o.action_id,o.source_atom_id,o.tube,lc) for o in n.obligations)
        ref={o.source_atom_id:o.evidence_ref for o in obs2}
        action=n.cell.actions[0]; action=replace(action,transitions=tuple(replace(tr,evidence_ref=ref[tr.source_atom_id]) for tr in action.transitions))
        new.append(replace(n,cell=replace(n.cell,actions=(action,)),obligations=obs2))
    return m,new[0].cell,tuple(new),stop


def test_absolute_mission_two_depths_and_early_acceptance():
    args=example(); r=audit_a53_mission(*args)
    assert r.ok,r.reason
    assert r.worst_s==Q(1,5) and r.checked_nodes==4 and r.checked_tubes==3


def test_absolute_schedule_changes_far_from_vehicle_are_safe():
    r=audit_a53_mission(*example(far=True));assert r.ok,r.reason


@pytest.mark.parametrize('options',[{'closed_near':True},{'closed_near':True,'close_at_end':True},{'rotate':True}])
def test_dynamic_closure_or_reverse_direction_rejects_possible_occupancy(options):
    r=audit_a53_mission(*example(**options))
    assert not r.ok and r.reason=='PHYSICAL_REPLAY_UNPROVED'


def test_absolute_time_and_posterior_not_reset_or_pruned():
    m,root,nodes,finish=example()
    assert not audit_a53_mission(m,root,nodes,finish-m.step).ok
    assert not audit_a53_mission(m,root,(nodes[0],replace(nodes[1],depth=0),*nodes[2:]),finish).ok
    assert not audit_a53_mission(m,root,(replace(nodes[0],children=nodes[0].children[:1]),*nodes[1:]),finish).ok
    # A support digest is independent of the candidate's declared root.
    wrong=replace(root,atoms=(replace(root.atoms[0],atom_id='different'),))
    assert not audit_a53_mission(m,wrong,nodes,finish).ok


def test_absolute_hashes_cover_clock_and_schedule():
    m,root,nodes,finish=example(far=True)
    e=m.schedule.epochs
    changed=replace(m,schedule=replace(m.schedule,epochs=(e[0],replace(e[1],source_ref='substituted'))))
    assert m.digest!=changed.digest
    assert not audit_a53_mission(changed,root,nodes,finish).ok


def test_exact_endpoint_public_helper_rejects_tampered_native_field():
    _,nodes,*_=scenario()
    tube=nodes[0].obligations[0].tube; seg=tube.segments[0]
    modified=replace(seg,witness=replace(seg.witness,field=(Interval.point(999.),*seg.witness.field[1:])))
    with pytest.raises(ValueError): exact_step_endpoint(replace(tube,segments=(modified,*tube.segments[1:])),Q(1,10))
