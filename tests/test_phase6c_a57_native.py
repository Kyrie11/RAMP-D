from fractions import Fraction as Q
import pytest
from rampd_core.a57_native_guard import NativeParent,native_post
from rampd_core.belief import SupportAtom
from rampd_core.model import StateBounds,ControlBounds,BicycleParameters
from rampd_core.interval import Interval
from rampd_core.footprint import VehicleGeometry
from rampd_core.resources import ResourceRegion
from test_phase6c_a56 import controller

def run(parents,**kw):
    return native_post(parents,ControlBounds.point(0,0),params=BicycleParameters(2.8,.9),ego_geometry=VehicleGeometry(2,1),disturbance=(Interval.point(0),)*6,resource=ResourceRegion('r',Interval(10,20),Interval(-2,2)),queue_a=ResourceRegion('qa',Interval(-3,3),Interval(-2,2)),queue_b=ResourceRegion('qb',Interval(-3,3),Interval(4,8)),**kw)

def test_native_physical_empty_and_observation():
    p=NativeParent(SupportAtom('e',StateBounds.point((0,0,0,0,0,0))),controller(),(),('silence','msg'),(True,))
    s,out,tubes=run((p,));assert s=='NEVER' and set(out)=={'silence','msg'} and len(tubes)==1
    c=out['silence'][0];assert c.clearance.empty and c.flow.occupants==0 and c.flow.queue_a==1 and c.atom.ego.contains((0,0,0,0,0,0))
    with pytest.raises(ValueError):run((p,),max_cases=1)

def test_native_physical_occupancy():
    p=NativeParent(SupportAtom('e',StateBounds.point((15,0,0,0,0,0))),controller(),(),readiness=(True,))
    s,out,_=run((p,));c=out['silence'][0];assert not c.clearance.empty and c.flow.occupants==1
