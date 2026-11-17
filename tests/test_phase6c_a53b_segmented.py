"""Native A5/3b tests. No fake arithmetic for certificate paths."""
from dataclasses import replace
from fractions import Fraction as Q
from rampd_core.a5_replay_bridge import replay_a5_physical,_subslab_box
from rampd_core.resources import ResourceRegion,ResourceState
from rampd_core.interval import Interval
from test_phase6c_a5_bridge import fixture,_rebind


def setup(closes):
    c,p,obs,cell,action,outcome,ob,ctx,w,safe=fixture()
    # 4m long, initially rear x=-2. After 0.08s moving at 1m/s,
    # rear x>-1.95, and this resource has been fully left.
    r=ResourceRegion('lane',Interval(-2.05,-1.95),Interval(-.2,.2),1)
    opened=ResourceState('lane',True,True,'forward',1)
    closed=replace(opened,alpha=False,beta=False,capacity=0)
    world=replace(w,regions=(r,),resource_states=(opened,),resource_forward_axes=(('lane',1.,0.),),
        timed_resource_slices=((Q(0),closes,(opened,)),(closes,c.step_s,(closed,)),(c.step_s,c.step_s,(closed,))))
    return c,ob,ctx,world,safe,closed


def test_exit_before_closure_recovered_not_safe_under_whole_step_meet():
    c,ob,ctx,world,safe,closed=setup(Q(2,25))
    c1,o1,e1,w1=_rebind(c,ob,ctx,world)
    assert replay_a5_physical(e1,c1,o1,w1,safe)
    old=replace(world,timed_resource_slices=(),resource_states=(closed,),regions=(replace(world.regions[0],capacity=0),))
    c2,o2,e2,w2=_rebind(c,ob,ctx,old)
    assert not replay_a5_physical(e2,c2,o2,w2,safe)


def test_close_while_physically_still_occupied_is_unknown():
    c,ob,ctx,world,safe,_=setup(Q(1,100))
    c,o,e,w=_rebind(c,ob,ctx,world)
    assert not replay_a5_physical(e,c,o,w,safe)


def test_resealed_missing_terminal_rule_or_gap_rejected():
    c,ob,ctx,w,safe,_=setup(Q(2,25))
    a,b,last=w.timed_resource_slices
    for rows in ((a,b),(a,(b[0]+Q(1,1000),b[1],b[2]),last),((Q(1,1000),*a[1:]),b,last)):
        nc,no,ne,nw=_rebind(c,ob,ctx,replace(w,timed_resource_slices=rows))
        assert not replay_a5_physical(ne,nc,no,nw,safe)


def test_resealed_new_terminal_boundary_closure_must_be_checked():
    c,ob,ctx,w,safe,closed=setup(Q(2,25)); opened=w.resource_states[0]
    # Resource around endpoint, old slab permits it; new terminal rule does not.
    w=replace(w,regions=(ResourceRegion('lane',Interval(0,1),Interval(-1,1),1),),
              timed_resource_slices=((Q(0),c.step_s,(opened,)),(c.step_s,c.step_s,(closed,))))
    nc,no,ne,nw=_rebind(c,ob,ctx,w)
    assert not replay_a5_physical(ne,nc,no,nw,safe)


def test_subslab_contains_analytic_unit_speed_motion():
    c,ob,*_=setup(Q(2,25))
    for seg in ob.tube.segments:
        lo=seg.start_time; hi=min(seg.end_time,c.step_s)
        if lo>hi: continue
        mid=(lo+hi)/2
        b=_subslab_box(seg,lo,hi)
        assert Q.from_float(b.px.lo)<=lo<=mid<=hi<=Q.from_float(b.px.hi)


def test_branch_schedule_must_bind_every_protocol_transition():
    import pytest
    from test_phase6c_a53_mission import example
    m,*_=example(far=True)
    ids=[t.transition_id for t in m.protocol.transitions]
    assert len(ids)>1
    with pytest.raises(ValueError,match='every protocol transition'):
        replace(m,branch_schedules=((ids[0],m.schedule),))
    new=replace(m,branch_schedules=tuple((tid,m.schedule) for tid in ids))
    assert new.digest!=m.digest
    # Even identical branch schedules must be explicitly bound in the evidence.
    _,root,nodes,finish=example(far=True)
    from rampd_core.a53_mission import audit_a53_mission
    assert not audit_a53_mission(new,root,nodes,finish).ok
