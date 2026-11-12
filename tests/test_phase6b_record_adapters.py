import hashlib
import json
from pathlib import Path

import pytest

from rampd_core import (
    FourClockInjection,
    RecordParseError,
    convert_center_scene_to_rear_axle,
    localize_scene,
    parse_av2_rows,
    parse_womd_scenario_proto,
)


class Obj:
    def __init__(self, **values):
        self.__dict__.update(values)

    def SerializeToString(self):
        return json.dumps(self.__dict__, sort_keys=True, default=lambda x: x.__dict__).encode()


def _womd():
    states = [
        Obj(valid=True, center_x=10.0, center_y=2.0, heading=0.0,
            velocity_x=3.0, velocity_y=0.0, length=4.5, width=1.8, height=1.5),
        Obj(valid=False),
        Obj(valid=True, center_x=11.0, center_y=2.0, heading=0.0,
            velocity_x=3.0, velocity_y=0.0, length=4.5, width=1.8, height=1.5),
    ]
    return Obj(scenario_id="w1", timestamps_seconds=[0.0, 0.1, 0.2],
               current_time_index=1,
               tracks=[Obj(id=42, object_type=1, states=states)],
               sdc_track_index=0,
               tracks_to_predict=[Obj(track_index=0)],
               objects_of_interest=[42],
               dynamic_map_states=[Obj(), Obj(), Obj()],
               map_features=[Obj(id=7)])


def test_womd_parser_preserves_id_index_masks_and_future_boundary(tmp_path: Path):
    parsed = parse_womd_scenario_proto(_womd(), source_file=tmp_path / "x.tfrecord")
    scene = parsed.scene
    assert scene.manifest.scenario_id == "w1"
    assert scene.manifest.current_time_index == 1
    assert scene.tracks[0].track_id == "42"
    assert scene.tracks[0].metadata["source_track_index"] == 0
    assert scene.tracks[0].to_predict is True
    assert scene.tracks[0].states[1].valid is False
    assert scene.tracks[0].states[1].observed is True
    assert scene.tracks[0].states[2].observed is False
    online = scene.online_view()
    assert len(online.manifest.timestamps) == 2
    assert all(len(track.states) == 2 for track in online.tracks)
    assert online.manifest.future_available is False
    assert scene.map_ids == ("7",)
    assert parsed.content_sha256 == hashlib.sha256(_womd().SerializeToString()).hexdigest()


def test_womd_parser_rejects_state_length_mismatch():
    scenario = _womd()
    scenario.tracks[0].states = scenario.tracks[0].states[:2]
    with pytest.raises(RecordParseError):
        parse_womd_scenario_proto(scenario)


def test_four_clocks_do_not_infer_relations():
    clocks = FourClockInjection(1.0, 0.2, 0.3, 0.4)
    trace = clocks.to_clock_trace()
    assert trace.change.lo == trace.change.hi
    assert trace.relation_proved("change", "receipt") is False
    declared = FourClockInjection(1.0, 1.1, 1.2, 1.3,
                                  declared_relations=(("activation", "issue"),))
    assert declared.to_clock_trace().relation_proved("change", "issue") is True


def _av2_rows():
    rows = []
    for track_id, category, x0 in (("ego", "FOCAL_TRACK", 0.0), ("a", "SCORED_TRACK", 5.0)):
        for timestep in (0, 1, 2):
            if track_id == "a" and timestep == 1:
                continue
            rows.append({
                "scenario_id": "av2-1", "track_id": track_id,
                "object_type": "vehicle", "object_category": category,
                "timestep": timestep, "position_x": x0 + timestep,
                "position_y": 0.0, "heading": 0.0,
                "velocity_x": 1.0, "velocity_y": 0.0,
                "observed": timestep <= 1,
                "start_timestamp": 1_000_000_000,
                "end_timestamp": 1_200_000_000,
                "num_timestamps": 3,
                "focal_track_id": "ego",
            })
    return rows


def test_av2_parser_reconstructs_dense_axis_and_map(tmp_path: Path):
    parquet = tmp_path / "scenario_av2-1.parquet"
    parquet.write_bytes(b"fixture")
    map_file = tmp_path / "log_map_archive_av2-1.json"
    map_file.write_text(json.dumps({"lane_segments": {"l1": {}}}))
    parsed = parse_av2_rows(_av2_rows(), source_file=parquet, map_file=map_file)
    scene = parsed.scene
    assert scene.manifest.current_time_index == 1
    assert scene.manifest.future_available is True
    other = next(t for t in scene.tracks if t.track_id == "a")
    assert other.states[1].valid is False
    assert other.states[1].observed is None
    assert next(t for t in scene.tracks if t.track_id == "ego").is_sdc is True
    assert parsed.map_file == str(map_file)
    assert parsed.map_content_sha256


def test_av2_test_split_hides_future_labels():
    parsed = parse_av2_rows(_av2_rows(), split="test")
    assert parsed.scene.manifest.future_available is False


def test_av2_focal_category_fallback_is_explicit():
    rows = _av2_rows()
    for row in rows:
        row.pop("focal_track_id", None)
    parsed = parse_av2_rows(rows)
    assert parsed.scene.manifest.metadata["focal_track_id"] == "ego"
    assert parsed.scene.manifest.metadata["focal_track_id_source"] == "object_category"
    assert parsed.scene.manifest.metadata["current_index_source"] == "focal_track_observed"


def test_localize_scene_and_center_to_rear_axle_math():
    scene = parse_av2_rows(_av2_rows()).scene
    local = localize_scene(scene, origin_xy=(0.0, 0.0), yaw_rad=0.0)
    ego = next(t for t in local.tracks if t.track_id == "ego")
    assert ego.states[0].x == 0.0
    rear = convert_center_scene_to_rear_axle(scene, offset_body=(1.0, 0.0),
                                              yaw_rates={("ego", 0): 0.5})
    ego_rear = next(t for t in rear.tracks if t.track_id == "ego")
    assert ego_rear.states[0].x == -1.0
    assert ego_rear.states[0].vx == 1.0
    assert rear.manifest.position_reference == "rear_axle_center"


def test_missing_observed_mask_fails_closed():
    rows = _av2_rows()
    rows[0] = {k: v for k, v in rows[0].items() if k != "observed"}
    with pytest.raises(RecordParseError):
        parse_av2_rows(rows)


def test_womd_missing_center_downgrades_valid_without_erasing_observed_slot():
    scenario = _womd()
    scenario.current_time_index = 1
    scenario.tracks[0].states[1] = Obj(valid=True, center_x=float("nan"), center_y=2.0)
    parsed = parse_womd_scenario_proto(scenario)
    state = parsed.scene.tracks[0].states[1]
    assert state.valid is False
    assert state.x is None and state.y is None
    assert state.observed is True
    assert state.metadata["invalid_reason"] == "missing_center"


def test_womd_testing_split_withholds_future_labels():
    parsed = parse_womd_scenario_proto(_womd(), split="testing")
    assert parsed.scene.manifest.future_available is False


def test_partial_center_to_rear_axle_velocity_is_not_certified_as_rear_axle():
    scene = parse_av2_rows(_av2_rows()).scene
    converted = convert_center_scene_to_rear_axle(
        scene, offset_body=(1.0, 0.0), yaw_rates={("ego", 0): 0.5},
    )
    assert converted.manifest.metadata["velocity_reference"] == "center_unconverted"
    ego = next(track for track in converted.tracks if track.track_id == "ego")
    assert ego.metadata["velocity_reference"] == "center_unconverted"
