import json
from pathlib import Path

from rampd_core.dataset_audit import audit_av2_motion_root, audit_womd_scenario_root
from rampd_core.scene_schema import (SceneManifest, SceneTrack, TrackState,
                                      UnifiedScene, build_scene_digest)


def _scene() -> UnifiedScene:
    timestamps = (0.0, 0.1, 0.2)
    states = tuple(TrackState(t, t, 0.0, 0.0, 1.0, 0.0, True,
                              observed=i < 2) for i, t in enumerate(timestamps))
    manifest = SceneManifest(
        "synthetic", "v1", "validation", "scene-1", "scene.bin", timestamps, 1,
        "local_xy", "bounding_box_center", True, sample_rate_hz=10.0)
    return UnifiedScene(manifest, (SceneTrack("42", "vehicle", states, to_predict=True),))


def test_scene_schema_digest_is_deterministic_and_online_view_has_no_future():
    scene = _scene()
    scene.assert_valid()
    assert build_scene_digest(scene) == build_scene_digest(scene)
    online = scene.online_view()
    assert len(online.manifest.timestamps) == 2
    assert all(len(track.states) == 2 for track in online.tracks)
    assert not online.manifest.future_available
    assert online.tracks[0].states[-1].observed is True


def test_scene_schema_rejects_track_index_identity_and_bad_time_axis():
    scene = _scene()
    bad_manifest = SceneManifest("synthetic", "v1", "validation", "scene-1", "x",
                                 (0.0, 0.2, 0.1), 1, "local", "center", True)
    bad = UnifiedScene(bad_manifest, scene.tracks)
    assert any("timestamps:not_strictly_increasing" in x for x in bad.validate())
    invalid = TrackState(0.2, None, None, None, None, None, False)
    sparse = UnifiedScene(
        _scene().manifest,
        (SceneTrack("42", "vehicle", _scene().tracks[0].states[:2] + (invalid,),
                    to_predict=True),),
    )
    assert not any("missing_for_valid_state" in x for x in sparse.validate())


def test_womd_manifest_audit_is_read_only_and_globs_shards(tmp_path: Path):
    root = tmp_path / "scenario" / "Validation"
    root.mkdir(parents=True)
    (root / "a.tfrecord-00000-of-00002").write_bytes(b"a")
    (root / "b.tfrecord-00001-of-00002").write_bytes(b"bb")
    before = sorted(p.relative_to(tmp_path).as_posix() for p in tmp_path.rglob("*"))
    report = audit_womd_scenario_root(tmp_path / "scenario", "validation")
    after = sorted(p.relative_to(tmp_path).as_posix() for p in tmp_path.rglob("*"))
    assert report.resolved_split == "Validation"
    assert report.file_count == 2
    assert report.manifest_digest.startswith("manifest-sha256:")
    assert before == after


def test_av2_audit_handles_case_split_and_unpaired_map(tmp_path: Path):
    root = tmp_path / "motion" / "Validation"
    root.mkdir(parents=True)
    (root / "scenario_001.parquet").write_bytes(b"parquet")
    (root / "log_map_archive_999.json").write_text("{}")
    report = audit_av2_motion_root(tmp_path / "motion", "validation")
    assert report.resolved_split == "Validation"
    assert report.file_count == 2
    assert report.future_labels_available is True
    assert any(x.code == "SCENARIO_MAP_UNPAIRED" for x in report.issues)


def test_missing_dataset_is_skip_with_explicit_reason(tmp_path: Path):
    report = audit_womd_scenario_root(tmp_path / "missing", "validation")
    assert report.status == "SKIP"
    assert any(x.code == "SPLIT_PATH_MISSING" for x in report.issues)

