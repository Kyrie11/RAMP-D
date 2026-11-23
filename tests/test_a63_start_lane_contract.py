"""A59/1b-0I: independence of continuous lane trace vs CARLA projection.

Regression for Town06_Opt: 2164 mathematically straight candidates but the
selected one subsequently fails `get_waypoint(...).is_junction` / None.
"""
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace as NS
import pytest
from rampd_core.a63_carla_site_contract import audit_start_waypoint,wp_identity
from rampd_core.a62_carla_readiness import inspect_readiness_log

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('a63_trial_script', ROOT/'scripts/a60_carla_actor_trials.py')
script=importlib.util.module_from_spec(spec);spec.loader.exec_module(script)


class Wp:
    def __init__(self, road, section, lane, index, junction=False):
        self.road_id,self.section_id,self.lane_id=road,section,lane
        self.is_junction=junction
        self.lane_type='Driving'
        self.transform=NS(location=NS(x=float(index*5+road*200),y=float(lane*3.5),z=0.),rotation=NS(yaw=0.))
        self.following=[]
    def next(self, d):
        assert d==5.0
        return self.following


def chain(road, n=65):
    pts=[Wp(road,0,-2,i) for i in range(n)]
    for i in range(n-1):pts[i].following=[pts[i+1]]
    return pts[0]

CARLA=NS(LaneType=NS(Driving='Driving'),
         Location=lambda **kwargs:NS(**kwargs),
         Transform=lambda a,b:NS(location=a,rotation=b))

class Map:
    name='Carla/Maps/Town06_Opt'
    def __init__(self, items, rejected_roads=(), projected_junction_roads=()):
        self.items=items
        self.rejected_roads=set(rejected_roads)
        self.projected_junction_roads=set(projected_junction_roads)
    def get_spawn_points(self):return []
    def generate_waypoints(self, s):return self.items
    def get_waypoint(self,loc,project_to_road=True,lane_type=None):
        for w in self.items:
            if abs(w.transform.location.x-loc.x)<1e-6:
                if w.road_id in self.rejected_roads:return None
                if w.road_id in self.projected_junction_roads:
                    return Wp(w.road_id,0,w.lane_id,0,junction=True)
                return w
        return None


def test_independent_projection_can_be_junction_with_valid_300m_trace():
    wp=chain(48)
    pose=NS(location=NS(x=wp.transform.location.x,y=wp.transform.location.y,z=.5))
    out=audit_start_waypoint(Map([wp],projected_junction_roads=[48]),CARLA,wp,pose)
    assert out['reason']=='PROJECTED_START_IS_JUNCTION'
    assert out['candidate_identity']==(48,0,-2)
    assert not out['certified']
    assert script._site_trace(wp,CARLA)==(110.,'ELIGIBLE')


def test_strict_selection_skips_invalid_first_site_and_chooses_valid_second():
    bad, good=chain(48),chain(52)
    world=NS(get_map=lambda:Map([bad,good],projected_junction_roads=[48]))
    report={}
    pose=script.spot(world,CARLA,prefer_longest=True,report=report,
                     require_start_identity=True)
    assert pose.location.x==good.transform.location.x
    assert report['eligible_candidates_checked']==2
    assert report['projected_start_usable_candidates']==1
    assert report['projected_start_rejections']=={'PROJECTED_START_IS_JUNCTION':1}
    assert report['chosen_waypoint']['road_id']==52
    assert report['chosen_start_projection_audit']['status']=='DESCRIPTIVE_LANE_IDENTITY_REPRODUCED'
    assert report['projected_start_rejection_examples'][0]['candidate']['road_id']==48


def test_all_eligible_sites_ambiguous_stays_review():
    w=chain(48)
    world=NS(get_map=lambda:Map([w],rejected_roads=[48]))
    report={}
    with pytest.raises(RuntimeError,match='REVIEW_NO_STRAIGHT_DRIVING_LANE'):
        script.spot(world,CARLA,report=report,require_start_identity=True)
    assert report['eligible_candidates_checked']==1
    assert report['projected_start_usable_candidates']==0
    assert report['projected_start_rejections']=={'NO_PROJECTED_DRIVING_WAYPOINT':1}


def test_identity_mismatch_even_when_projected_is_not_junction():
    original=chain(48)
    class Wrong(Map):
        def get_waypoint(self,*args,**kwargs):
            wp=super().get_waypoint(*args,**kwargs)
            wp2=Wp(wp.road_id,0,wp.lane_id+1,0)
            wp2.transform.location=wp.transform.location
            return wp2
    pose=NS(location=NS(x=original.transform.location.x,y=original.transform.location.y,z=.5))
    r=audit_start_waypoint(Wrong([original]),CARLA,original,pose)
    assert r['reason']=='PROJECTED_LANE_IDENTITY_MISMATCH'


def test_xy_discrepancy_not_silently_accepted():
    w=chain(48)
    pose=NS(location=NS(x=w.transform.location.x,y=w.transform.location.y+2,z=.5))
    r=audit_start_waypoint(Map([w]),CARLA,w,pose)
    # Custom stub cannot project offset locations; real CARLA may return a
    # different lane. Either is a refusal rather than a false usable site.
    assert r['status']=='REVIEW'


def test_readiness_review_retains_uploaded_abort_reason():
    data=json.loads((ROOT/'tests/fixtures/a63_readiness_abort_excerpt.json').read_text())
    out=inspect_readiness_log(data)
    assert out['status']=='REVIEW'
    assert 'NO_TRIALS' in out['reasons']
    assert any('REVIEW_INVALID_START_LANE' in reason for reason in out['reasons'])
    assert not out['physical_certified']
