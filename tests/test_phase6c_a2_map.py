"""Contract regressions for WOMD/AV2 static geometry, dynamic labels and leak guards."""
import json
import math
from pathlib import Path
from dataclasses import replace

import pytest

from rampd_core import (MapVertex, MapContractError, MapPrimitive, MapContext,
                        from_womd_scenario, from_av2_map_json,
                        parse_womd_scenario_proto, parse_av2_rows,
                        build_scene_forecast_sample, localize_scene)


class Obj:
    def __init__(self, **values):
        self.__dict__.update(values)

    def SerializeToString(self, *args, **kwargs):
        return json.dumps(self.__dict__, sort_keys=True,
                          default=lambda x: x.__dict__).encode()


def _womd():
    times = (0.0, .1, .2, .3)
    states = [Obj(valid=True, center_x=float(i), center_y=0., heading=0.,
                  velocity_x=1., velocity_y=0.) for i in range(4)]
    return Obj(scenario_id="w-map", timestamps_seconds=times, current_time_index=1,
               sdc_track_index=0, tracks=[Obj(id=5, object_type=1, states=states)],
               tracks_to_predict=[], objects_of_interest=[],
               map_features=[
                   Obj(id=11, lane=Obj(polyline=[Obj(x=0., y=0., z=0.),
                                                       Obj(x=10., y=0., z=0.)],
                                       exit_lanes=[12], entry_lanes=[],
                                       type=2, speed_limit_mph=25.)),
                   Obj(id=12, lane=Obj(polyline=[Obj(x=10., y=0., z=0.),
                                                       Obj(x=20., y=0., z=0.)],
                                       entry_lanes=[11], exit_lanes=[])),
                   Obj(id=13, crosswalk=Obj(polygon=[Obj(x=1.,y=2.), Obj(x=3.,y=2.),
                                                        Obj(x=3.,y=4.), Obj(x=1.,y=4.)]))
               ],
               dynamic_map_states=[
                   Obj(lane_states=[Obj(lane=11, state=4, stop_point=Obj(x=1.,y=0.))]),
                   Obj(lane_states=[Obj(lane=11, state=6, stop_point=Obj(x=1.,y=0.))]),
                   Obj(lane_states=[Obj(lane=11, state=4, stop_point=Obj(x=1.,y=0.))]),
                   Obj(lane_states=[Obj(lane=11, state=6, stop_point=Obj(x=1.,y=0.))]),
               ])


def _av2_map():
    return {"lane_segments": {"7": {
        "id": 7, "lane_type": "VEHICLE", "is_intersection": False,
        "right_lane_mark_type": "DASHED_WHITE", "left_lane_mark_type": "SOLID_WHITE",
        "left_lane_boundary": [{"x": 0., "y": 2., "z": 0.},
                               {"x": 10., "y": 2., "z": 0.}],
        "right_lane_boundary": [{"x": 0., "y": 0., "z": 0.},
                                {"x": 10., "y": 0., "z": 0.}],
        "predecessors": [], "successors": [8],
        "left_neighbor_id": None, "right_neighbor_id": 8,
    }}, "drivable_areas": {"9": {"id": 9, "area_boundary": [
        {"x": 0, "y": -1, "z": 0}, {"x": 10, "y": -1, "z": 0},
        {"x": 10, "y": 3, "z": 0}, {"x": 0, "y": 3, "z": 0},
    ]}}, "pedestrian_crossings": {"10": {"id": 10,
        "edge1": [{"x": 2, "y": -1, "z": 0}, {"x": 2, "y": 3, "z": 0}],
        "edge2": [{"x": 4, "y": -1, "z": 0}, {"x": 4, "y": 3, "z": 0}],
    }}}


def _av2_rows():
    return [dict(scenario_id="av-map", track_id="AV", object_type="VEHICLE",
                 object_category="UNSCORED_TRACK", timestep=i,
                 position_x=float(i), position_y=0., heading=0.,
                 velocity_x=1., velocity_y=0., observed=i <= 1,
                 start_timestamp=0, end_timestamp=200_000_000,
                 num_timestamps=3) for i in range(3)]


def test_womd_feature_geometry_types_topology_signal_enum():
    m = from_womd_scenario(_womd())
    assert m.complete_geometry
    assert m.coordinate_frame == "womd_global_xy"
    assert [(p.feature_id,p.kind) for p in m.primitives] == [
        ("11", "lane"), ("12", "lane"), ("13", "crosswalk")]
    assert m.primitives[0].successors == ("12",)
    assert m.primitives[1].predecessors == ("11",)
    assert m.primitives[2].geometry_type == "polygon"
    assert [s.state for s in m.signals] == [
        "LANE_STATE_STOP", "LANE_STATE_GO", "LANE_STATE_STOP", "LANE_STATE_GO"]
    assert all(s.visibility == "recorded_not_proven_observed" for s in m.signals)


def test_logged_future_signal_is_not_encoder_input_even_when_future_available():
    source = _womd()
    sample = build_scene_forecast_sample(parse_womd_scenario_proto(source).scene)
    assert len(sample.future_signal_targets) == 2
    assert len(sample.map_context_history.signals) == 2
    payload = sample.encoder_inputs
    assert "future_signal_targets" not in payload
    assert payload["static_map"].signals == ()
    assert len(payload["static_map"].primitives) == 3
    source.dynamic_map_states[2].lane_states[0].state = 6
    changed = build_scene_forecast_sample(parse_womd_scenario_proto(source).scene)
    assert changed.encoder_inputs["static_map"] == payload["static_map"]
    assert changed.map_context_history == sample.map_context_history
    assert changed.future_signal_targets != sample.future_signal_targets


def test_womd_test_does_not_expose_future_signals():
    scene = parse_womd_scenario_proto(_womd(), split="testing").scene
    sample = build_scene_forecast_sample(scene)
    assert sample.future_signal_targets == ()
    assert len(scene.online_view().map_context.signals) == 2
    assert "dynamic_map_states_digest" not in scene.online_view().manifest.metadata
    assert "dynamic_map_states" not in scene.online_view().map_metadata


def test_av2_map_archive_has_lane_polygons_and_crossing_correct_order():
    m = from_av2_map_json(_av2_map(), scenario_id="av-map")
    assert m.complete_geometry
    assert len(m.primitives) == 5
    lane = next(x for x in m.primitives if x.feature_id == "lane_segment:7")
    assert lane.geometry_type == "polygon"
    assert [(v.x, v.y) for v in lane.vertices] == [
        (0, 2), (10, 2), (10, 0), (0, 0)]
    assert lane.successors == ("lane_segment:8",)
    crossing = next(x for x in m.primitives if x.kind == "pedestrian_crossing")
    assert [(v.x, v.y) for v in crossing.vertices] == [
        (2, -1), (2, 3), (4, 3), (4, -1)]
    assert m.signals == ()  # AV2 Motion map has no controller timeline.


def test_av2_map_is_attached_and_localized_with_tracks(tmp_path: Path):
    p = tmp_path / "log_map_archive_av-map.json"
    p.write_text(json.dumps(_av2_map()))
    parsed = parse_av2_rows(_av2_rows(), map_file=p)
    scene = parsed.scene
    assert scene.map_context.complete_geometry
    assert scene.map_context.source_map_sha256 == parsed.map_content_sha256
    local = localize_scene(scene, origin_xy=(1., 0.), yaw_rad=math.pi/2)
    assert local.validate() == ()
    assert local.map_context.coordinate_frame == "local_xy"
    lane = next(x for x in local.map_context.primitives if x.feature_id == "lane_segment:7")
    assert lane.vertices[0].x == pytest.approx(2.)
    assert lane.vertices[0].y == pytest.approx(1.)
    # A second localization is relative to the already transformed positions.
    sample = build_scene_forecast_sample(local)
    assert sample.encoder_inputs["static_map"].coordinate_frame == "local_xy"


def test_womd_stop_point_transforms_exactly_with_map_and_ego():
    scene = parse_womd_scenario_proto(_womd()).scene
    new_scene = localize_scene(scene, origin_xy=(2., 1.), yaw_rad=0.)
    assert new_scene.map_context.signals[0].stop_point.x == -1.
    assert new_scene.map_context.signals[0].stop_point.y == -1.
    assert new_scene.map_context.coordinate_frame == new_scene.manifest.coordinate_frame


def test_unknown_map_features_mark_incomplete_not_fake_coordinates():
    src = _womd()
    src.map_features.append(Obj(id=99))
    m = from_womd_scenario(src)
    assert not m.complete_geometry
    assert m.primitives[-1].geometry_type == "missing"
    bad = from_av2_map_json({"lane_segments": {"7": {}}}, scenario_id="test")
    assert not bad.complete_geometry


def test_duplicate_map_id_nonfinite_and_mismatched_id_fail():
    src = _womd()
    src.map_features.append(src.map_features[0])
    with pytest.raises(MapContractError, match="duplicate"):
        from_womd_scenario(src)
    with pytest.raises(MapContractError, match="finite"):
        MapVertex(float("nan"), 2)
    bad = _av2_map()
    bad["lane_segments"]["7"]["id"] = 6
    with pytest.raises(MapContractError, match="disagree"):
        from_av2_map_json(bad, scenario_id="av-map")


def test_scene_map_frame_mismatch_fails_closed():
    scene = parse_womd_scenario_proto(_womd()).scene
    inconsistent = replace(scene, map_context=replace(scene.map_context,
                                                      coordinate_frame="local_xy"))
    assert "map_context:coordinate_frame_mismatch" in inconsistent.validate()


def test_map_polygon_geometry_is_not_formal_collision_certificate():
    m = from_av2_map_json(_av2_map(), scenario_id="av-map")
    assert not hasattr(m, "certified_safe")
    assert not hasattr(m, "formal_resource_permissions")


def test_online_view_does_not_expose_full_future_time_axis_in_metadata():
    source = _womd()
    scene = parse_womd_scenario_proto(source).scene
    obs = scene.online_view()
    assert obs.manifest.timestamps == (0., .1)
    assert "source_timestamps" not in obs.manifest.metadata
    assert not any(s.timestep > 1 for s in obs.map_context.signals)


def test_optional_proto_stop_point_presence_avoids_invented_zero_coordinate():
    class LaneState(Obj):
        def HasField(self, key):
            return False if key == "stop_point" else True

    src = _womd()
    src.dynamic_map_states[0].lane_states[0] = LaneState(
        lane=11, state=4, stop_point=Obj(x=0., y=0., z=0.))
    m = from_womd_scenario(src)
    assert m.signals[0].stop_point is None


def test_av2_official_numeric_track_category_maps_to_benchmark_targets():
    rows = _av2_rows()
    for row in rows:
        row['object_category'] = 3
        row['focal_track_id'] = 'AV'
    parsed = parse_av2_rows(rows)
    focal = parsed.scene.tracks[0]
    assert focal.track_id == 'AV'
    assert focal.is_focal and focal.to_predict
    assert focal.metadata['object_category'] == 'FOCAL_TRACK'
    # Explicit category fallback must work when focal_track_id isn't supplied.
    for row in rows:
        row.pop('focal_track_id')
    inferred = parse_av2_rows(rows)
    assert inferred.scene.manifest.metadata['focal_track_id_source'] == 'object_category'
    assert inferred.scene.tracks[0].to_predict


def test_av2_unknown_track_category_rejected_instead_of_erasing_score_mask():
    rows = _av2_rows()
    for row in rows:
        row['object_category'] = 8
    from rampd_core import RecordParseError
    with pytest.raises(RecordParseError, match='object_category'):
        parse_av2_rows(rows)
