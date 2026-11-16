"""Leakage, forecast wiring, soft ranking and clock tests independent of native MPFR."""
from dataclasses import replace
import pytest

from rampd_core.forecast import PredictionProposal, ProposalSet, hard_support_from_prediction, ProposalStatus
from rampd_core.phase6c import (
    ForecastJob, constant_velocity_proposals, offline_forecast_metrics,
    soft_rank_proposals, stable_split_fingerprint)
from rampd_core.scene_schema import SceneManifest, SceneTrack, TrackState, UnifiedScene


def _scene(*, split="validation", v=2.0):
    ts = tuple(i*0.1 for i in range(5))
    states = tuple(TrackState(t, v*t, 0.0, 0.0, v, 0.0,
                              True, observed=i <= 2) for i, t in enumerate(ts))
    manifest = SceneManifest("synthetic", "v1", split, "s1", "synthetic.bin", ts, 2,
                             "local_xy", "bounding_box_center", split != "test", 10.0)
    return UnifiedScene(manifest, (SceneTrack("target", "vehicle", states, to_predict=True),))


def test_baseline_only_uses_history_and_matches_logged_future():
    scene = _scene()
    job = ForecastJob.from_scene(scene)
    assert not job.scene.manifest.future_available
    assert not job.scene.tracks[0].to_predict
    sets = constant_velocity_proposals(job, horizon_steps=2)
    assert len(sets) == 1
    assert sets[0].proposals[0].positions[0] == pytest.approx((0.6, 0.0))
    assert sets[0].proposals[0].positions[1] == pytest.approx((0.8, 0.0))
    metrics = offline_forecast_metrics(scene, sets)
    assert metrics["rows"][0]["ade_m"] == pytest.approx(0.0)
    assert metrics["rows"][0]["fde_m"] == pytest.approx(0.0)
    assert hard_support_from_prediction(sets[0]).status == ProposalStatus.UNKNOWN_UNBOUNDED_TAIL


def test_change_all_future_coordinates_no_change_to_prediction():
    scene = _scene()
    tr = scene.tracks[0]
    altered = replace(tr, states=tr.states[:3] + (
        replace(tr.states[3], x=300.0, y=-400.0),
        replace(tr.states[4], x=-999.0, y=999.0)))
    altered_scene = replace(scene, tracks=(altered,))
    a = constant_velocity_proposals(ForecastJob.from_scene(scene), horizon_steps=2)
    b = constant_velocity_proposals(ForecastJob.from_scene(altered_scene), horizon_steps=2)
    assert [ps.digest() for ps in a] == [ps.digest() for ps in b]
    assert offline_forecast_metrics(altered_scene, b)["rows"][0]["ade_m"] > 100


def test_prediction_never_fills_current_missing_state():
    scene = _scene()
    tr = scene.tracks[0]
    invalid = replace(tr.states[2], valid=False, x=None, y=None)
    scene = replace(scene, tracks=(replace(tr, states=tr.states[:2]+(invalid,)+tr.states[3:]),))
    assert constant_velocity_proposals(ForecastJob.from_scene(scene), horizon_steps=2) == ()


def test_no_evaluation_on_test_and_no_training_label_leak():
    scene = _scene(split="test")
    assert not scene.manifest.future_available
    with pytest.raises(ValueError, match="withheld future"):
        ForecastJob.from_scene(scene)
    with pytest.raises(ValueError, match="future labels withheld"):
        offline_forecast_metrics(scene, ())


def test_soft_rank_preserves_all_modes_and_has_no_support_promotion():
    scene = _scene()
    first = constant_velocity_proposals(ForecastJob.from_scene(scene), horizon_steps=2)[0].proposals[0]
    second = replace(first, mode_id="alternate", score=-1.0)
    set_ = ProposalSet("target", "local_xy", (first, second), "fixture")
    scores = soft_rank_proposals(set_, rule_scores={"alternate": 3.0},
                                 rule_score_source="synthetic_only")
    assert [s.mode_id for s in scores] == ["alternate", "constant_velocity"]
    assert {s.mode_id for s in scores} == {p.mode_id for p in set_.proposals}
    assert hard_support_from_prediction(set_).status == ProposalStatus.UNKNOWN_UNBOUNDED_TAIL
    with pytest.raises(ValueError, match="provenance"):
        soft_rank_proposals(set_, rule_scores={"alternate": 3.0})
    with pytest.raises(ValueError, match="nonexistent"):
        soft_rank_proposals(set_, rule_scores={"alien": 2.0},rule_score_source="fixture")


def test_split_fingerprint_reproducible_and_detects_duplicate():
    keys = [("womd","train","a"),("av2","validation","c")]
    assert stable_split_fingerprint(keys) == stable_split_fingerprint(list(reversed(keys)))
    with pytest.raises(ValueError, match="duplicate"):
        stable_split_fingerprint(keys+keys)


def test_metrics_do_not_report_fde_when_horizon_endpoint_missing():
    scene = _scene()
    tr = scene.tracks[0]
    missing = replace(tr.states[4], valid=False, x=None, y=None)
    scene = replace(scene, tracks=(replace(tr, states=tr.states[:4]+(missing,)),))
    sets = constant_velocity_proposals(ForecastJob.from_scene(scene), horizon_steps=2)
    m = offline_forecast_metrics(scene, sets)["rows"][0]
    assert m["valid_steps"] == 1 and m["fde_m"] is None


def test_cosim_ledger_requires_single_tick_owner_and_aligned_time():
    from rampd_core.clock_ledger import CoSimTick, CoSimLedger
    ledger = CoSimLedger(0.05)
    ledger.record(CoSimTick(0, 100, 10.0, 0.05, 1, 1, 1, 0))
    ledger.record(CoSimTick(1, 101, 10.05, 0.10, 1, 1, 1, 0))
    assert ledger.summary()["status"] == "PASS"
    assert not ledger.summary()["protocol_four_clocks_observed"]
    with pytest.raises(ValueError, match="frame skipped"):
        ledger.record(CoSimTick(2, 103, 10.10, 0.15, 1, 1, 1, 0))
    with pytest.raises(ValueError, match="SUMO time advance"):
        ledger.record(CoSimTick(2, 102, 10.10, 0.30, 1, 1, 1, 0))
    assert len(ledger.ticks) == 2
