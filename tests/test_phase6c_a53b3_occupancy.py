from fractions import Fraction as Q
from dataclasses import replace
import pytest
from rampd_core.interval import Interval
from rampd_core.footprint import SweptFootprint,VehicleGeometry
from rampd_core.model import StateBounds
from rampd_core.resources import ResourceRegion,ResourceState
from rampd_core.a53b_occupancy import no_new_entry_proved
from rampd_core.a5_replay_bridge import replay_a5_physical
from test_phase6c_a5_bridge import fixture,_rebind

def fp(x,lo=Q(0),hi=Q(0)):
    z=Interval.point(0)
    return SweptFootprint(StateBounds(x,z,z,z,z,z),VehicleGeometry(2,1),lo,hi,'ego')

def test_strict_interior_and_monotone_exit_no_reentry():
    r=ResourceRegion('r',Interval(-2,2),Interval(-2,2))
    start=fp(Interval.point(0)); end=fp(Interval(0,4),Q(0),Q(1)); z=Interval.point(0)
    assert no_new_entry_proved(start,end,r,(Interval(0,5),z),z)
    assert not no_new_entry_proved(start,end,r,(Interval(-1,5),z),z)
    assert not no_new_entry_proved(start,end,r,(Interval(0,5),z),Interval(-1,1))
    assert no_new_entry_proved(fp(Interval.point(1)),end,r,(Interval(0,5),z),z) # center strictly inside; fixed-heading Minkowski proof
    assert no_new_entry_proved(fp(Interval.point(2.5)),fp(Interval(2.5,4),Q(0),Q(1)),r,(Interval(0,5),z),z) # partial overlap with center outside
    assert not no_new_entry_proved(fp(Interval.point(3)),end,r,(Interval(0,5),z),z) # mere boundary contact
    assert no_new_entry_proved(start,fp(Interval(-.1,.1),Q(0),Q(1)),r,(Interval(-1,1),z),Interval(-1,1))

def test_drain_incumbent_accepted_entering_or_stay_closed_rejected():
    c,p,obs,cell,action,out,ob,ctx,w,safe=fixture()
    s=ResourceState('lane',False,True,'forward',1)
    for bounds,beta,expected in (((-5,5),True,True),((2.05,5),True,False),((-5,5),False,False)):
        st=replace(s,beta=beta)
        ww=replace(w,regions=(ResourceRegion('lane',Interval(*bounds),Interval(-5,5)),),resource_states=(st,),resource_forward_axes=(('lane',1.,0.),),timed_resource_slices=((Q(0),c.step_s,(st,)),(c.step_s,c.step_s,(st,))))
        cc,oo,ee,ww=_rebind(c,ob,ctx,ww)
        assert replay_a5_physical(ee,cc,oo,ww,safe)==expected

def test_fractional_capacity_rejected():
    with pytest.raises(ValueError): ResourceRegion('r',Interval(0,1),Interval(0,1),1.5)
    with pytest.raises(ValueError): ResourceState('r',True,True,'forward',True)

def test_other_actor_incumbent_still_counts_capacity():
    from test_phase6c_a53b2_actors import edge
    (c,ob,ctx,w),safe=edge(capacity=2)
    st=replace(w.resource_states[0],alpha=False)
    ww=replace(w,resource_states=(st,),timed_resource_slices=((Q(0),c.step_s,(st,)),(c.step_s,c.step_s,(st,))))
    cc,oo,ee,ww=_rebind(c,ob,ctx,ww)
    assert replay_a5_physical(ee,cc,oo,ww,safe)
    st=replace(st,capacity=1)
    ww=replace(ww,resource_states=(st,),timed_resource_slices=((Q(0),c.step_s,(st,)),(c.step_s,c.step_s,(st,))))
    cc,oo,ee,ww=_rebind(c,ob,ctx,ww)
    assert not replay_a5_physical(ee,cc,oo,ww,safe)
