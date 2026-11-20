from fractions import Fraction as Q
from dataclasses import replace
from math import sin,cos,pi,dist
import pytest
from rampd_core.a57_motion import rear_from_center,center_from_rear,first_contact_distance,polyline_projection,brake_screen,bicycle_reference
from rampd_core.a57_physical_guard import Box,Actor,World,post
from rampd_core.a57_lifecycle import PhysicalLifecycle,unique_windows
from rampd_core.a57_interlock import advance_monitored
from test_phase6c_a56 import controller
from test_phase6c_a53b_interlock import pending,advance,ack
from rampd_core.a53b_interlock import ClearanceObservation
from audit_a57_511ny import audit
from audit_a57_roadwork import group

def box(x,y=None):return Box(Q(x),Q(x if y is None else y))
def actor(id,front,speed=0,dir='A'):return Actor(id,dir,box(front),box(speed),Q(2),box(0))
def run(worlds,**kw):return post(worlds,box(0),entry=Q(10),exit=Q(20),detector_start=Q(0),**kw)

def test_reference_round_trip():
    for yaw in (-pi,-.2,0,1.2,pi):
        p=center_from_rear(4,3,yaw,8,.3,1.3,-.1)
        assert rear_from_center(p[0],p[1],yaw,p[2],p[3],.3,1.3,-.1)==pytest.approx((4,3,8,0),abs=1e-12)

def test_contact_sizes_and_wrong_lane():
    a=(0,0,0,4.5,2)
    assert first_contact_distance(a,(15,0,0,4.5,2))==10.5
    assert first_contact_distance(a,(15,0,0,12,2.5))==6.75
    assert first_contact_distance(a,(15,4,0,4.5,2)) is None
    assert first_contact_distance(a,(-15,0,0,4.5,2)) is None
    assert first_contact_distance(a,(15,0,pi/2,4.5,2))==pytest.approx(11.75)

def test_polyline_projection_and_tie():
    d,s,p=polyline_projection((8,3),[(0,0),(10,0),(10,10)]);assert (d,s,*p)==pytest.approx((2,13,10,3))
    with pytest.raises(ValueError):polyline_projection((8,2),[(0,0),(10,0),(10,10)])

def test_bicycle_reference_analytic_and_convergence():
    x=(0,0,0,8,0,.1);k=__import__('math').tan(.1)/2.8;th=8*k
    assert bicycle_reference(x,(0,0),1,2.8,256)==pytest.approx((sin(th)/k,(1-cos(th))/k,th,8,0,.1),abs=1e-9)
    x=(0,0,.2,8,.1,.1);u=(-.4,.2);ref=bicycle_reference(x,u,1.5,2.8,4096);errs=[dist(bicycle_reference(x,u,1.5,2.8,n),ref) for n in (8,16,32)]
    assert errs[0]>12*errs[1]>144*errs[2]
    with pytest.raises(ValueError):bicycle_reference((0,0,0,1,-4,0),(4,0),2,2.8,16)

def test_brake_reserve():
    assert brake_screen(8,reaction=.5,accel_upper=2,comfort=4,standstill_gap=2,extra=1)==pytest.approx(17.375)
    with pytest.raises(ValueError):brake_screen(8,reaction=.5,accel_upper=2,comfort=0,standstill_gap=2)

def test_guard_physical_joint_and_obs():
    a=World('a',controller(),(actor('ego',0),actor('b',5,dir='B')),('silence','msg'),(True,))
    b=World('b',controller(),(actor('ego',0),actor('b',-5,dir='B')),('silence',),(True,))
    s,out=run((a,b));assert s=='NEVER' and len(out['silence'])==2 and len(out['msg'])==1
    assert {(c.flow.queue_a,c.flow.queue_b) for c in out['silence']}=={(1,1),(1,0)}
    with pytest.raises(ValueError):run((a,b),max_cases=2)

def test_guard_physical_crossing_and_exit():
    a=World('a',controller(),(actor('ego',9,15),),('silence',),(True,))
    s,out=run((a,),exit_open=(False,True));c=out['silence'][0]
    assert not c.clearance.empty and c.flow.occupants==0 and c.possible_entries==c.possible_exits==c.unresolved_permissions==('ego',)

def test_guard_ambiguous_and_reverse():
    a=replace(actor('ego',9),front=box(9,11));w=World('a',controller(),(a,),switch_ready=(True,))
    _,o=run((w,));assert {c.clearance.empty for c in o['silence']}=={True,False} and {c.flow.occupants for c in o['silence']}=={0,1}
    with pytest.raises(ValueError):post((w,),box(-1),entry=Q(10),exit=Q(20),detector_start=Q(0))

def test_signal_phase_clock_grid():
    with pytest.raises(ValueError):replace(controller(),last_tick=Q(1,2))

def test_lifecycle_windows():
    e=PhysicalLifecycle('x',Q(100),Q(1200),Q(1205),'mechanism')
    a,b=unique_windows(e,[Q(1198),Q(1198),Q(1200)],Q(8));assert a['segments']==((Q(1198),Q(1200),'BLOCKED'),(Q(1200),Q(1205),'CLEARED_WAIT_AUTHORITY'),(Q(1205),Q(1206),'REOPENED')) and b['endpoint_phase']=='REOPENED'
    assert e.window(Q(92),Q(8))['endpoint_phase']=='BLOCKED'
    with pytest.raises(ValueError):PhysicalLifecycle('x',Q(10),Q(9),Q(12),'bad')

def test_monitored_closure():
    e,s=pending();s=advance(s,e,ack=ack(s,'PRESENT'));o=ClearanceObservation(s.last_tick,s.last_tick+1,True,True,'fixture',s.event_id,s.version,s.resource_id)
    kw=dict(tick=Q(1),clearance=Q(2))
    with pytest.raises(RuntimeError):advance_monitored(e,s,o,**kw)
    with pytest.raises(RuntimeError):advance_monitored(e,s,replace(o,empty=False),registry=ack(s,'PRESENT'),**kw)
    assert advance_monitored(e,s,o,registry=ack(s,'PRESENT'),**kw).phase=='BLOCKED'

def test_group_parser():
    assert group({'file_name':'pgh1_0001.jpg'})==('pgh:1',None)
    assert group({'file_name':'abc'})==(None,None)
    with pytest.raises(ValueError):group({'file_name':'bad','video_info':{'vid_id':'x','seq_id':'s','frame_id':'f'}})

def test_511_stratified_quarantine(tmp_path):
    p=tmp_path/'rows.csv';p.write_text('Event Type,Organization Name,State,Facility Name,Create Time,Close Time\nAccident,NY DOT,NY,I-90,2020-01-01 12:00:00,2020-01-01 11:00:00\nAccident,NY DOT,NY,I-90,2020-01-01 12:00:00,2020-01-01 12:00:00\nAccident,NY DOT,NY,I-90,2020-01-01 12:00:00,2020-01-01 13:00:00\n')
    r=audit(p);assert r['counts']['QUARANTINE_NEGATIVE']==r['counts']['ZERO_SEPARATE']==r['counts']['POSITIVE_REPORT_ONLY']==1 and r['negative_repaired']==0

def test_explicit_tim_clearance_profile():
    from test_phase6c_a53b2_data_incident import timeline
    t=timeline();assert replace(t,tim_sequential_clearance_profile=True,incident_occurrence=Q(2)).duration('normal_flow')==16
    with pytest.raises(ValueError):replace(t,tim_sequential_clearance_profile=True,incident_occurrence=Q(3))
    with pytest.raises(ValueError):replace(t,tim_sequential_clearance_profile=True,normal_flow=Q(14))

def test_site_distance_audit():
    from audit_a57_roadwork import site_audit
    a=site_audit([{'image_id':1,'gps':[40.,-80.]},{'image_id':2,'gps':[41.,-80.]},{'image_id':3}], [{'gps':[40.0001,-80.]},{'gps':None}]);assert a['train_near_image_ids']==[1] and a['train_unknown_gps']==a['val_unknown_gps']==1

def test_closure_fault_latches():
    from rampd_core.a57_interlock import ClosureMonitor
    e,s=pending();s=advance(s,e,ack=ack(s,'PRESENT'));o=ClearanceObservation(s.last_tick,s.last_tick+1,True,True,'fixture',s.event_id,s.version,s.resource_id)
    m=ClosureMonitor(s).step(e,o,tick=Q(1),clearance=Q(2));assert m.fault and m.permissions==(False,False)
    assert m.step(e,o,tick=Q(1),clearance=Q(2),registry=ack(s,'PRESENT')) is m

def test_nominal_controls_are_not_silently_clamped():
    from rampd_core.a57_motion import nominal_control_screen
    lim=dict(wheelbase=2.8,mu=.8,a_min=-8,a_max=3,jerk_max=3,steering_max=.5,steering_rate_max=.2,v_max=30)
    assert nominal_control_screen((0,0,0,8,0,.05),(0,.05),1,**lim)['screen_pass']
    r=nominal_control_screen((0,0,0,20,-7,.4),(-3,.3),1,**lim);assert not r['screen_pass'] and not r['checks']['actuator_accel'] and not r['checks']['friction'] and not r['checks']['steering_rate'] and not r['certificate']
