import hashlib
import json
import sys
import types
from pathlib import Path

import pytest

from rampd_core import (
    FourClockInjection,
    RecordParseError,
    convert_center_scene_to_rear_axle,
    localize_scene,
    build_scene_forecast_sample,
    parse_av2_rows,
    parse_womd_scenario_proto,
)
from rampd_core import record_adapters


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
    sample = build_scene_forecast_sample(scene)
    assert sample.benchmark_target_track_ids == ("42",)
    assert sample.history_tracks[0].is_sdc is True
    assert sample.sdc_track_id == "42"
    assert tuple(x.track_id for x in sample.ego_future_targets) == ("42",)
    assert sample.agent_response_targets == ()


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
    for track_id, category, x0 in (("AV", "UNSCORED_TRACK", -5.0),
                                   ("ego", "FOCAL_TRACK", 0.0),
                                   ("a", "SCORED_TRACK", 5.0)):
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
    focal = next(t for t in scene.tracks if t.track_id == "ego")
    assert focal.is_focal is True
    assert focal.is_sdc is False
    av = next(t for t in scene.tracks if t.track_id == "AV")
    assert av.is_sdc is True
    assert av.is_focal is False
    sample = build_scene_forecast_sample(scene)
    assert sample.sdc_track_id == "AV"
    assert {x.track_id for x in sample.agent_response_targets} == {"ego", "a"}
    assert tuple(x.track_id for x in sample.ego_future_targets) == ("AV",)
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
    assert ego_rear.states[0].vy == -0.5
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
    assert converted.manifest.metadata["velocity_reference"] == "mixed_center_and_rear_axle"
    ego = next(track for track in converted.tracks if track.track_id == "ego")
    assert ego.metadata["velocity_reference"] == "mixed"


def test_av2_observed_mask_rejects_truthy_strings_and_nan():
    rows = _av2_rows()
    rows[0]["observed"] = "False"
    with pytest.raises(RecordParseError):
        parse_av2_rows(rows)


def test_in_memory_av2_rows_digest_is_not_mislabeled_as_source_file_hash():
    parsed = parse_av2_rows(_av2_rows())
    assert parsed.content_sha256
    assert parsed.source_file_sha256 is None
    rows = _av2_rows()
    rows[0]["observed"] = float("nan")
    with pytest.raises(RecordParseError):
        parse_av2_rows(rows)


def test_av2_fast_sample_does_not_hash_entire_source_file(tmp_path: Path, monkeypatch):
    source = tmp_path / "scenario_fast.parquet"
    source.write_bytes(b"placeholder parquet bytes")

    def forbidden_full_file_hash(*args, **kwargs):
        raise AssertionError("fast sample must not read/hash the entire parquet file")

    monkeypatch.setattr(record_adapters, "sha256_file", forbidden_full_file_hash)
    parsed = parse_av2_rows(
        _av2_rows(), source_file=source, hash_source_file=False,
    )
    assert parsed.source_file_sha256 is None
    assert parsed.content_sha256
    assert parsed.scene.manifest.metadata["source_file_hash_status"] == "not_computed"
    assert parsed.scene.manifest.metadata["content_sha256_semantics"] == "canonical_parsed_rows_sha256"
    fully_fingerprinted = parse_av2_rows(
        _av2_rows(), source_file=source, content_sha256="b" * 64,
        source_file_sha256="b" * 64, hash_source_file=False,
    )
    assert parsed.scenario_content_sha256 == fully_fingerprinted.scenario_content_sha256


def test_av2_parquet_reader_projects_used_columns_and_hashes_source_once(
    tmp_path: Path, monkeypatch,
):
    source = tmp_path / "scenario_projection.parquet"
    source.write_bytes(b"parquet")
    rows = _av2_rows()
    available_columns = list(rows[0].keys())
    read_calls = []
    hash_calls = []

    class Schema:
        names = available_columns

    class FakeParquetFile:
        schema = Schema()

    # This is a unit test of our adapter's column projection and call contract,
    # not of pandas itself.  Use a minimal pandas stub so importing real pandas
    # cannot inspect the intentionally incomplete fake pyarrow package (newer
    # pandas releases read pyarrow.__version__ during pandas import).
    def fake_read_parquet(path, *, columns, engine):
        read_calls.append((tuple(columns), engine))
        return rows

    fake_pandas = types.ModuleType("pandas")
    fake_pandas.read_parquet = fake_read_parquet
    fake_parquet = types.ModuleType("pyarrow.parquet")
    fake_parquet.ParquetFile = lambda path: FakeParquetFile()
    fake_pyarrow = types.ModuleType("pyarrow")
    fake_pyarrow.__path__ = []
    fake_pyarrow.parquet = fake_parquet
    monkeypatch.setitem(sys.modules, "pandas", fake_pandas)
    monkeypatch.setitem(sys.modules, "pyarrow", fake_pyarrow)
    monkeypatch.setitem(sys.modules, "pyarrow.parquet", fake_parquet)
    digest = "a" * 64

    def counted_hash(path, **kwargs):
        hash_calls.append(str(path))
        return digest

    monkeypatch.setattr(record_adapters, "sha256_file", counted_hash)
    parsed = record_adapters.parse_av2_parquet(
        source, require_map=False, hash_source_file=True,
    )
    fast_parsed = record_adapters.parse_av2_parquet(
        source, require_map=False, hash_source_file=False,
    )
    assert parsed.source_file_sha256 == digest
    assert fast_parsed.source_file_sha256 is None
    assert hash_calls == [str(source)]
    assert parsed.scenario_content_sha256 == fast_parsed.scenario_content_sha256
    assert len(read_calls) == 2
    for projected, engine in read_calls:
        assert engine == "pyarrow"
        assert set(projected) == set(available_columns)
        assert "unused_column_not_in_adapter" not in projected


def test_womd_fast_sample_hashes_record_without_hashing_full_shard(
    tmp_path: Path, monkeypatch,
):
    payload = b"serialized scenario payload"

    class FakeScenario(Obj):
        def ParseFromString(self, value):
            assert value == payload
            self.__dict__.update(_womd().__dict__)

    scenario_pb2 = types.SimpleNamespace(Scenario=FakeScenario)
    waymo_pkg = types.ModuleType("waymo_open_dataset")
    waymo_pkg.__path__ = []
    protos_pkg = types.ModuleType("waymo_open_dataset.protos")
    protos_pkg.scenario_pb2 = scenario_pb2
    monkeypatch.setitem(sys.modules, "waymo_open_dataset", waymo_pkg)
    monkeypatch.setitem(sys.modules, "waymo_open_dataset.protos", protos_pkg)
    monkeypatch.setattr(record_adapters, "_iter_tfrecord", lambda path: iter([payload]))

    def forbidden_full_file_hash(*args, **kwargs):
        raise AssertionError("fast sample must not read/hash the entire TFRecord shard")

    monkeypatch.setattr(record_adapters, "sha256_file", forbidden_full_file_hash)
    parsed = next(record_adapters.iter_womd_scenario_file(
        tmp_path / "validation.tfrecord-00000-of-00150",
        max_records=1, hash_source_file=False,
    ))
    assert parsed.source_file_sha256 is None
    assert parsed.record_sha256 == hashlib.sha256(payload).hexdigest()
    assert parsed.content_sha256 == parsed.record_sha256
    assert parsed.scene.manifest.metadata["source_file_hash_status"] == "not_computed"


def test_av2_row_timestamps_must_agree_with_scenario_axis():
    rows = _av2_rows()
    for row in rows:
        row["timestamp_ns"] = 1_000_000_000 + row["timestep"] * 100_000_000
    rows[-1]["timestamp_ns"] += 5_000_000
    with pytest.raises(RecordParseError):
        parse_av2_rows(rows)


def test_center_to_rear_axle_refuses_mixed_position_reference_inside_a_track():
    scene = parse_av2_rows(_av2_rows()).scene
    tracks = list(scene.tracks)
    focal = tracks[0]
    states = list(focal.states)
    states[0] = type(states[0])(
        timestamp=states[0].timestamp, x=states[0].x, y=states[0].y,
        heading=None, vx=states[0].vx, vy=states[0].vy, valid=True,
        observed=states[0].observed,
    )
    tracks[0] = type(focal)(focal.track_id, focal.category, tuple(states),
                            focal.is_sdc, focal.to_predict, focal.metadata, focal.is_focal)
    malformed = type(scene)(scene.manifest, tuple(tracks), scene.map_ids, scene.map_metadata)
    with pytest.raises(RecordParseError):
        convert_center_scene_to_rear_axle(malformed, offset_body=(1.0, 0.0))


def test_partial_track_reference_conversion_is_explicitly_mixed():
    scene = parse_av2_rows(_av2_rows()).scene
    converted = convert_center_scene_to_rear_axle(
        scene, offset_body=(1.0, 0.0), track_ids=("ego",),
        yaw_rates={("ego", 0): 0.5, ("ego", 1): 0.5},
    )
    assert converted.manifest.position_reference == "mixed_center_and_rear_axle"
    assert converted.manifest.metadata["converted_track_ids"] == ["ego"]
    other = next(track for track in converted.tracks if track.track_id == "a")
    assert other.metadata.get("reference_conversion") is None


def test_womd_source_shard_and_record_digests_are_separate():
    shard = "a" * 64
    record = "b" * 64
    parsed = parse_womd_scenario_proto(
        _womd(), source_file="validation.tfrecord-00000-of-00150",
        content_sha256=shard, source_file_sha256=shard, record_sha256=record,
    )
    assert parsed.content_sha256 == shard
    assert parsed.source_file_sha256 == shard
    assert parsed.record_sha256 == record
    assert parsed.scenario_content_sha256 != shard


    fast_parsed = parse_womd_scenario_proto(
        _womd(), source_file="validation.tfrecord-00000-of-00150",
        record_sha256=record,
    )
    assert fast_parsed.source_file_sha256 is None
    assert fast_parsed.scenario_content_sha256 == parsed.scenario_content_sha256


def test_av2_scenario_digest_is_independent_of_map_archive_path(tmp_path: Path):
    map_a = tmp_path / "a" / "log_map_archive_av2-1.json"
    map_b = tmp_path / "b" / "log_map_archive_av2-1.json"
    map_a.parent.mkdir()
    map_b.parent.mkdir()
    raw = json.dumps({"lane_segments": {"lane-1": {"id": "lane-1"}}}).encode()
    map_a.write_bytes(raw)
    map_b.write_bytes(raw)
    parsed_a = parse_av2_rows(_av2_rows(), map_file=map_a)
    parsed_b = parse_av2_rows(_av2_rows(), map_file=map_b)
    assert parsed_a.map_content_sha256 == parsed_b.map_content_sha256
    assert parsed_a.scenario_content_sha256 == parsed_b.scenario_content_sha256
