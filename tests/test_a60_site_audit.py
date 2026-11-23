"""Offline CARLA-map doubles: the audit must not weaken actor trial controls."""
import importlib.util
from pathlib import Path
from types import SimpleNamespace as NS

import pytest


SCRIPT = Path(__file__).resolve().parents[1] / 'scripts' / 'a60_carla_actor_trials.py'
spec = importlib.util.spec_from_file_location('a60_carla_site_audit_under_test', SCRIPT)
script = importlib.util.module_from_spec(spec)
spec.loader.exec_module(script)


class FakeWaypoint:
    def __init__(self, index, *, yaw=0, is_junction=False):
        self.index = index
        self.is_junction = is_junction
        self.lane_type = 'Driving'
        self.road_id = 4
        self.section_id = 0
        self.lane_id = 1
        self.transform = NS(location=NS(x=float(index * 5), y=0., z=1.),
                            rotation=NS(yaw=yaw))
        self.following = []

    def next(self, distance):
        assert distance == 5.0
        return self.following


def lane(n, *, bend_at=None, junction_at=None, branching_at=None):
    points = [FakeWaypoint(i, yaw=8.0 if bend_at is not None and i >= bend_at else 0.,
                           is_junction=(i == junction_at)) for i in range(n)]
    for i, point in enumerate(points[:-1]):
        point.following = [points[i+1]]
        if branching_at == i:
            point.following.append(points[i+1])
    return points


class FakeMap:
    name = 'Carla/Maps/Town10HD_Opt'

    def __init__(self, spawn_points, sampled_points):
        self._spawn_points = spawn_points
        self._sampled_points = sampled_points
        self._spawns = [NS(location=p.transform.location) for p in spawn_points]

    def get_spawn_points(self):
        return self._spawns

    def get_waypoint(self, location, project_to_road, lane_type):
        assert project_to_road and lane_type == 'Driving'
        return next(p for p in self._spawn_points if p.transform.location is location)

    def generate_waypoints(self, spacing_m):
        assert 0.5 <= spacing_m <= 10.0
        return self._sampled_points


class FakeCarla:
    LaneType = NS(Driving='Driving')

    @staticmethod
    def Location(**kwargs):
        return NS(**kwargs)

    @staticmethod
    def Transform(location, rotation):
        return NS(location=location, rotation=rotation)


def test_original_geometry_gate_and_cause_reporting():
    assert script._site_trace(lane(23)[0], FakeCarla) == (110., 'ELIGIBLE')
    assert script._site_trace(lane(7)[0], FakeCarla) == (30., 'NO_NEXT_WAYPOINT')
    assert script._site_trace(lane(23, bend_at=9)[0], FakeCarla) == (40., 'HEADING_DELTA_OVER_5_DEG')
    assert script._site_trace(lane(23, junction_at=9)[0], FakeCarla) == (40., 'JUNCTION_IN_WINDOW')
    assert script._site_trace(lane(23, branching_at=4)[0], FakeCarla) == (20., 'MULTIPLE_NEXT_WAYPOINTS')


def test_read_only_audit_and_sampled_site_fallback():
    m = FakeMap([lane(7)[0]], [lane(23)[0]])
    world = NS(get_map=lambda: m)
    pose, report = script.survey_sites(world, FakeCarla, exhaustive=True)
    assert report['spawn_points_total'] == 1
    assert report['sampled_lane_waypoints_total'] == 1
    assert report['eligible_candidates_checked'] == 1
    assert report['best_verified_step_distance_m'] == 110.
    assert report['rejection_counts']['NO_NEXT_WAYPOINT'] == 1
    assert report['chosen_waypoint']['source'] == 'sampled_lane'
    assert pose.location.z == 1.5


def test_failure_preserves_gate_and_exposes_reasons():
    m = FakeMap([lane(7)[0]], [lane(15)[0]])
    world = NS(get_map=lambda: m)
    report = {}
    with pytest.raises(RuntimeError, match='REVIEW_NO_STRAIGHT_DRIVING_LANE'):
        script.spot(world, FakeCarla, report=report)
    assert report['best_verified_step_distance_m'] == 70.
    assert report['verified_step_distance_counts_ge_m']['110'] == 0
    assert report['rejection_counts']['NO_NEXT_WAYPOINT'] == 2


def test_spawn_point_keeps_precedence():
    first = lane(23)[0]
    later = lane(23)[0]
    m = FakeMap([first], [later])
    world = NS(get_map=lambda: m)
    report = {}
    pose = script.spot(world, FakeCarla, report=report)
    assert pose.location is first.transform.location
    assert report['chosen_waypoint']['source'] == 'spawn'


def test_opt_in_longest_site_selection_does_not_relax_110m_gate():
    short_eligible = lane(23)[0]  # exactly 110m, valid baseline
    long_eligible = lane(51)[0]  # 250m, same 5-degree conditions
    m = FakeMap([short_eligible, long_eligible], [])
    world = NS(get_map=lambda: m)
    report = {}
    pose = script.spot(world, FakeCarla, prefer_longest=True, report=report)
    assert pose.location is long_eligible.transform.location
    assert report['chosen_extended_straight_probe_m'] == 250.
    assert report['eligible_candidates_checked'] == 2
    assert report['required_straight_m'] == 110.


def test_read_only_audit_identifies_no_110m_site_without_actor_commands():
    m = FakeMap([lane(14)[0]], [lane(19, bend_at=15)[0]])
    _, report = script.survey_sites(NS(get_map=lambda:m), FakeCarla,
                                    exhaustive=True, prefer_longest=True)
    assert report['eligible_candidates_checked'] == 0
    assert report['best_verified_step_distance_m'] < 110
    assert report['rejection_counts']['HEADING_DELTA_OVER_5_DEG'] >= 1


def test_site_audit_cli_never_requires_exclusive_flags_or_mutates_world(tmp_path, monkeypatch):
    import json
    import sys
    world = NS(get_map=lambda: FakeMap([lane(7)[0]], [lane(16)[0]]),
               get_settings=lambda: NS(synchronous_mode=False),
               get_actors=lambda: [])
    client = NS(set_timeout=lambda timeout: None,
                get_world=lambda: world,
                get_server_version=lambda: '0.9.16')
    fake_carla = NS(Client=lambda host, port: client,
                    LaneType=FakeCarla.LaneType,
                    Location=FakeCarla.Location,
                    Transform=FakeCarla.Transform)
    monkeypatch.setitem(sys.modules, 'carla', fake_carla)
    out = tmp_path / 'site-audit.json'
    monkeypatch.setattr(sys, 'argv', [str(SCRIPT), '--mode', 'site-audit',
                                       '--output', str(out), '--site-spacing', '2'])
    assert script.main() == 0
    data = json.loads(out.read_text())
    assert data['status'] == 'READ_ONLY_SITE_AUDIT'
    assert data['site_audit']['eligible_candidates_checked'] == 0
    assert data['world_exclusive_confirmed'] is False
