"""A59/1b-0H independent tests: prevent false CARLA calibration labels."""
from __future__ import annotations
import importlib.util, json, math, sys
from pathlib import Path
from types import SimpleNamespace as NS
import pytest
from rampd_core.a62_carla_readiness import ground_window, projected_lane_footprint, inspect_readiness_log, wheel_road_height_proxy

SCRIPT=Path(__file__).resolve().parents[1]/'scripts'/'a60_carla_actor_trials.py'
spec=importlib.util.spec_from_file_location('a62_carla_script',SCRIPT)
script=importlib.util.module_from_spec(spec);spec.loader.exec_module(script)


def row(k,z=0.3,vz=0,vx=0,vy=0):
    return (k,.05*k,491.,-24.,z,vx,vy,vz)


def test_first_frame_gravity_not_grounded():
    ok,why=ground_window([row(k,z=.5-k*.03,vz=-.5) for k in range(5)])
    assert not ok and why=='MOVING_OR_FALLING_AT_SETTLING_GATE'


def test_grounding_requires_stable_height_and_velocity():
    assert ground_window([row(k,z=.30) for k in range(10)])[0]
    assert not ground_window([row(k,z=.30+k*.01) for k in range(5)])[0]
    assert not ground_window([row(k,vx=.3) for k in range(5)])[0]
    assert not ground_window([row(1),row(2),row(4),row(5),row(6)])[0]
    assert not ground_window([row(k) for k in range(4)])[0]


def test_lane_2d_footprint_does_not_accept_nearest_waypoint_automatically():
    kw=dict(bbox_center_x=.03,bbox_center_y=0,bbox_half_length=2.396,
            bbox_half_width=1.082,lane_x=0,lane_y=0,lane_yaw_deg=0,lane_width=3.5)
    good=projected_lane_footprint(0,0,0,**kw)
    assert good['status']=='DESCRIPTIVE_RECTANGLE_WITHIN_LANE' and not good['safety_certified']
    bad=projected_lane_footprint(0,1.5,0,**kw)
    assert bad['reason']=='LANE_RECTANGLE_EXCEEDS_WIDTH'
    assert projected_lane_footprint(0,0,35,**kw)['status']=='REVIEW'
    assert projected_lane_footprint(0,0,0,**kw,expected_lane=(1,0,-1),observed_lane=(1,0,-2))['reason']=='LANE_IDENTITY_CHANGED'
    assert projected_lane_footprint(0,0,0,**{**kw,'lane_width':-1})['status']=='REVIEW'


def test_script_lane_check_uses_projected_waypoint_but_explicit_width(monkeypatch):
    called=[]
    class Map:
        def get_waypoint(self,loc,*,project_to_road,lane_type):
            called.append(project_to_road)
            return NS(is_junction=False,road_id=48,section_id=0,lane_id=-7,lane_width=3.5,
                      transform=NS(location=NS(x=1.,y=0.),rotation=NS(yaw=0.)))
    class Actor:
        bounding_box=NS(location=NS(x=0.,y=0.),extent=NS(x=2.4,y=1.1))
        def get_transform(self):return NS(location=NS(x=1.,y=1.5,z=.5),rotation=NS(yaw=0.))
    out=script.lane_audit(NS(get_map=lambda: Map()),Actor(),NS(LaneType=NS(Driving='driving')),expected_lane=(48,0,-7))
    assert called==[True] and out['reason']=='LANE_RECTANGLE_EXCEEDS_WIDTH'


def test_grounding_failure_cannot_issue_throttle(monkeypatch):
    monkeypatch.setattr(script,'settle_vehicle',lambda *args,**kw:{'status':'REVIEW_NO_STABLE_GROUNDING_EVIDENCE'})
    class Vehicle:
        def apply_control(self,*args):raise AssertionError('MUST_NOT_DRIVE_UNSETTLED')
    trial=script.drive_trial(None,Vehicle(),None,speed=5,kind='brake',repeat=0,step_s=.05)
    assert trial['status']=='REVIEW_PRETRIAL_GROUNDING_FAILED' and not trial['samples']


def test_planar_speed_not_freefall_3d_speed_can_trigger(monkeypatch):
    monkeypatch.setattr(script,'settle_vehicle',lambda *args,**kw:{'status':'DESCRIPTIVE_STATIONARY_HEIGHT_STABLE'})
    monkeypatch.setattr(script,'observe',lambda *args,**kw:{'speed_mps':10.,'planar_speed_mps':0.1})
    monkeypatch.setattr(script,'lane_audit',lambda *args,**kw:{'status':'DESCRIPTIVE_RECTANGLE_WITHIN_LANE'})
    class W:
        frame=10
        def get_snapshot(self):return NS(frame=self.frame,timestamp=NS(elapsed_seconds=self.frame*.05))
        def tick(self):self.frame+=1;return self.frame
    v=NS(apply_control=lambda c:None)
    out=script.drive_trial(W(),v,NS(VehicleControl=lambda **kw: NS(**kw)),
                           speed=5,kind='brake',repeat=0,step_s=.05,max_accel_s=.1)
    assert out['status']=='REVIEW_TARGET_NOT_REACHED' and len(out['samples'])==2


def test_shortpulse_uploaded_is_pretrigger_and_cannot_calibrate():
    path=Path(__file__).resolve().parent/'fixtures'/'a62_shortpulse_excerpt.json'
    doc=json.loads(path.read_text())
    assert doc['trial_attempt_count']==9 and doc['trial_captured_count']==0
    assert all(x['trigger_frame']==-1 and len(x['samples'])==1 for x in doc['trials'])
    assert all(x['samples'][0]['velocity_xyz_carla']['z']<-.4 for x in doc['trials'])
    report=inspect_readiness_log(doc)
    assert report['status']=='REVIEW' and not report['physical_certified']


def test_new_readiness_record_never_produces_certificate():
    doc={'capture_protocol_version':'a62_grounding_lane_v1','trials':[
        {'status':'DESCRIPTIVE_PRETRIAL_READY_NOT_CALIBRATED',
         'settling':{'status':'DESCRIPTIVE_STATIONARY_HEIGHT_STABLE',
                     'ground_height_proxy':{'status':'DESCRIPTIVE_WHEEL_HEIGHT_NEAR_ROAD'}}}]}
    out=inspect_readiness_log(doc)
    assert out['status']=='DESCRIPTIVE_PRETRIAL_EVIDENCE_COMPLETE_NOT_CERTIFIED'
    assert not out['physical_certified'] and not out['actuator_calibrated']
    doc['trials'][0]['settling']['status']='REVIEW'
    assert inspect_readiness_log(doc)['status']=='REVIEW'


def test_readiness_no_implicit_world_mutation_without_two_consents(tmp_path):
    import subprocess
    cmd=[sys.executable,str(SCRIPT),'--mode','readiness','--output',str(tmp_path/'no.json')]
    a=subprocess.run(cmd,capture_output=True,text=True)
    assert a.returncode!=0 and 'ISOLATED_WORLD_ACK' in a.stderr
    cmd.insert(-2,'--confirm-isolated-world')
    b=subprocess.run(cmd,capture_output=True,text=True)
    assert b.returncode!=0 and 'EXCLUSIVE_TICK_ACK' in b.stderr


def test_wheel_ground_clearance_rejects_uploaded_initial_freefall():
    raw=json.loads((Path(__file__).resolve().parent/'fixtures'/'a62_shortpulse_excerpt.json').read_text())
    wheels=[]
    for w in raw['physics']['wheels']:
        pos=w['position_raw']
        wheels.append(NS(position=NS(x=pos['x'],y=pos['y'],z=pos['z']),
                         radius=w['radius_cm_raw']))
    body=raw['physics']['body_transform']['location']
    out=wheel_road_height_proxy(wheels,(body['x'],body['y'],body['z']),[0]*4)
    assert out['reason']=='WHEEL_HEIGHT_ABOVE_OR_BELOW_ROAD'
    assert all(x>.3 for x in out['wheel_bottom_to_road_m'])


def test_nominal_wheel_road_proxy_is_not_contact_force_certificate():
    wheels=[NS(position=NS(x=1000.,y=0.,z=37.),radius=37.) for _ in range(4)]
    good=wheel_road_height_proxy(wheels,(10.,0.,0.),[0]*4)
    assert good['status']=='DESCRIPTIVE_WHEEL_HEIGHT_NEAR_ROAD'
    assert not good['physical_contact_certified']
    wheels[0].position.x=100000.
    assert wheel_road_height_proxy(wheels,(10.,0.,0.),[0]*4)['reason']=='WHEEL_COORDINATE_FRAME_UNVERIFIED'
