import math

import pytest

from rampd_core.forecast import PredictionProposal, ProposalSet, hard_support_from_prediction
from rampd_core.phase6c import (
    ActorIdentityRegistry,
    BranchPriorityCandidate,
    CoSimulationConfig,
    FutureTrackTarget,
    HistoryTrackInput,
    JointModeProposal,
    JointModeSet,
    ObservationEventProposal,
    ObservationHistoryProposal,
    Phase6CContractError,
    RuleInteractionTrace,
    RuleNetThresholds,
    RuleNetSoftRanker,
    SceneForecastSample,
    SensorDeliveryRecord,
    SynchronizedFrameLedger,
    SynchronizedFrameStamp,
    build_scene_forecast_sample,
    hard_support_from_joint_modes,
    radial_ttc_s,
    rank_policy_branches,
)
from rampd_core.scene_schema import SceneManifest, SceneTrack, TrackState, UnifiedScene


def test_radial_ttc_matches_rule_net_expression_and_guards_nonclosing_cases():
    assert radial_ttc_s((0, 0), (10, 0), (2, 0), (0, 0)) == pytest.approx(5.0)
    assert math.isinf(radial_ttc_s((0, 0), (10, 0), (-2, 0), (0, 0)))
    assert radial_ttc_s((0, 0), (0, 0), (0, 0), (0, 0)) == 0.0


def test_rulenet_normalized_stl_risk_uses_max_over_time():
    trace = RuleInteractionTrace(
        actor_i_id="ego", actor_j_id="ped",
        interaction_kind="vehicle_vru",
        ttc_s=(5.0, 1.0),
        longitudinal_gap_m=(20.0, 5.0),
        speed_i_mps=(5.0, 5.0),
        lateral_gap_m=(3.0, 0.75),
    )
    report = RuleNetSoftRanker().score((trace,), interaction_coverage_complete=True)
    assert report.complete is True
    assert report.ordering_only is True
    assert report.support_pruned is False
    assert report.interaction_scores[0].worst_step_index == 1
    assert report.interaction_scores[0].longitudinal_component == pytest.approx(0.5)
    assert report.interaction_scores[0].lateral_component == pytest.approx(0.5)
    assert report.branch_score == pytest.approx(0.5)
    assert report.actor_step_scores[0][0] == "ego"
    assert report.actor_step_scores[0][1] == pytest.approx((0.0, 0.5))


def test_rulenet_threshold_epsilons_keep_time_and_distance_units_separate():
    thresholds = RuleNetThresholds(epsilon_ttc_s=1e-6, epsilon_distance_m=1e-4)
    assert thresholds.epsilon_ttc_s == pytest.approx(1e-6)
    assert thresholds.epsilon_distance_m == pytest.approx(1e-4)
    with pytest.raises(Phase6CContractError):
        RuleNetThresholds(epsilon_ttc_s=0.0)


def test_rulenet_score_does_not_turn_nonclosing_ttc_into_violation():
    trace = RuleInteractionTrace(
        actor_i_id="ego", actor_j_id="car",
        interaction_kind="vehicle_vehicle",
        ttc_s=(math.inf,), longitudinal_gap_m=(50.0,), speed_i_mps=(5.0,),
    )
    report = RuleNetSoftRanker().score((trace,), interaction_coverage_complete=True)
    assert report.branch_score == 0.0


def test_rulenet_actor_score_averages_directed_peer_interactions():
    traces = (
        RuleInteractionTrace("ego", "a", "vehicle_vehicle", (0.5,), (0.0,), (5.0,)),
        RuleInteractionTrace("ego", "b", "vehicle_vehicle", (10.0,), (100.0,), (5.0,)),
    )
    report = RuleNetSoftRanker().score(traces, interaction_coverage_complete=True)
    assert report.actor_scores[0][0] == "ego"
    assert report.actor_scores[0][1] == pytest.approx(0.5)


def test_rulenet_eq20_averages_peers_per_step_before_branch_worst_case():
    traces = (
        RuleInteractionTrace("ego", "a", "vehicle_vehicle", (0.5, 10.0), (0.0, 100.0), (5.0, 5.0)),
        RuleInteractionTrace("ego", "b", "vehicle_vehicle", (10.0, 0.5), (100.0, 0.0), (5.0, 5.0)),
    )
    report = RuleNetSoftRanker().score(traces, interaction_coverage_complete=True)
    # Each pair has a peak violation of 1 at a different step. Eq. (20) first
    # averages peers at each step, producing (0.5, 0.5), not 1.0.
    assert report.actor_step_scores[0][0] == "ego"
    assert report.actor_step_scores[0][1] == pytest.approx((0.5, 0.5))
    assert report.actor_scores[0][0] == "ego"
    assert report.actor_scores[0][1] == pytest.approx(0.5)
    assert report.branch_score == pytest.approx(0.5)


def test_branch_ordering_preserves_all_protocol_branches_and_unknown_first():
    candidates = (
        BranchPriorityCandidate("b-low", "p1", "obs1", 0.99, 0.1, True),
        BranchPriorityCandidate("b-unknown", "p2", "obs2", 0.01, None, False),
        BranchPriorityCandidate("b-high", "p3", "obs3", 0.2, 0.9, True),
    )
    result = rank_policy_branches(candidates)
    assert [x.branch_id for x in result.ordered_candidates] == [
        "b-unknown", "b-high", "b-low"
    ]
    assert set(result.retained_branch_ids) == {"b-low", "b-unknown", "b-high"}
    assert result.ordering_only is True
    assert result.support_pruned is False


def test_branch_ordering_rejects_duplicates_and_invalid_probability_range():
    item = BranchPriorityCandidate("b", "p", "obs", 0.5, 0.2, True)
    with pytest.raises(Phase6CContractError):
        rank_policy_branches((item, item))
    with pytest.raises(Phase6CContractError):
        BranchPriorityCandidate("x", "p", "obs", 0.5, 1.2, True)


def test_prediction_modes_are_not_physical_support_even_if_all_model_outputs_retained():
    proposal = PredictionProposal.from_mtr_row(
        "actor", "m0", "frame", 0.0, 0.1,
        ((0, 0, -1, -1, 0, 0, 0),), 0.8,
    )
    proposal_set = ProposalSet("actor", "frame", (proposal,), "MTR",
                               all_emitted_modes_retained=True)
    assert proposal_set.all_emitted_modes_retained is True
    assert proposal_set.complete_modes is True  # legacy alias only
    assert proposal_set.behavior_support_complete is False
    assert hard_support_from_prediction(proposal_set).status.value == "UNKNOWN_UNBOUNDED_TAIL"


def test_cosimulation_config_checks_fixed_step_and_physics_substep_budget():
    config = CoSimulationConfig()
    assert config.carla_fixed_delta_s == config.sumo_step_length_s
    assert config.sensors_available is True
    with pytest.raises(Phase6CContractError):
        CoSimulationConfig(carla_fixed_delta_s=0.05, sumo_step_length_s=0.1)
    with pytest.raises(Phase6CContractError):
        CoSimulationConfig(carla_fixed_delta_s=0.2, sumo_step_length_s=0.2,
                           max_substep_delta_s=0.01, max_substeps=10)
    with pytest.raises(Phase6CContractError):
        CoSimulationConfig(traffic_manager_sync=False)
    CoSimulationConfig(uses_traffic_manager=False, traffic_manager_sync=False)
    no_render = CoSimulationConfig(render_mode="no_rendering")
    assert no_render.sensors_available is False


def test_synchronized_frame_ledger_rejects_dropped_or_misaligned_ticks():
    ledger = SynchronizedFrameLedger(CoSimulationConfig())
    ledger.append(SynchronizedFrameStamp(1, 10, 0.05, 0.05))
    ledger.append(SynchronizedFrameStamp(2, 11, 0.10, 0.10))
    with pytest.raises(Phase6CContractError):
        ledger.append(SynchronizedFrameStamp(4, 13, 0.20, 0.20))
    with pytest.raises(Phase6CContractError):
        SynchronizedFrameLedger(CoSimulationConfig()).append(
            SynchronizedFrameStamp(1, 10, 0.05, 0.10)
        )


def test_sensor_production_and_delivery_clocks_are_separate():
    item = SensorDeliveryRecord("front_camera", 102, 10, 12, 0.50, 0.60)
    assert item.production_step == 10
    assert item.delivery_step == 12
    with pytest.raises(Phase6CContractError):
        SensorDeliveryRecord("front_camera", 102, 12, 10, 0.60, 0.50)


def test_actor_identity_registry_enforces_one_to_one_cross_simulator_mapping():
    registry = ActorIdentityRegistry()
    registry.bind("actor-1", carla_id="42", sumo_id="veh42")
    assert registry.resolve_carla("42") == "actor-1"
    assert registry.resolve_sumo("veh42") == "actor-1"
    with pytest.raises(Phase6CContractError):
        registry.bind("actor-2", carla_id="42", sumo_id="veh43")


def _forecast_scene(future_available=True):
    timestamps = (0.0, 0.1, 0.2, 0.3)
    ego_states = tuple(
        TrackState(t, float(i), 0.0, 0.0, 1.0, 0.0, True,
                   observed=i <= 1)
        for i, t in enumerate(timestamps)
    )
    other_states = (
        TrackState(0.0, 2.0, 0.0, 0.0, 0.0, 0.0, True, observed=True),
        TrackState(0.1, 2.0, 0.0, 0.0, 0.0, 0.0, False, observed=True),
        TrackState(0.2, 2.0, 0.0, 0.0, 0.0, 0.0, True, observed=False),
        TrackState(0.3, None, None, None, None, None, False, observed=False),
    )
    manifest = SceneManifest(
        "av2_motion", "2", "validation", "scene-x", "scenario_scene-x.parquet",
        timestamps, 1, "av2_city_xy", "bounding_box_center", future_available,
        sample_rate_hz=10.0, source_digest="a" * 64,
    )
    return UnifiedScene(manifest, (
        SceneTrack("focal", "vehicle", ego_states, is_sdc=False,
                   to_predict=True, is_focal=True),
        SceneTrack("context", "pedestrian", other_states),
    ))


def test_scene_forecast_sample_separates_history_inputs_from_future_labels():
    sample = build_scene_forecast_sample(_forecast_scene())
    assert len(sample.history_timestamps_s) == 2
    assert len(sample.future_timestamps_s) == 2
    focal_history = next(x for x in sample.history_tracks if x.track_id == "focal")
    assert len(focal_history.states) == 2
    assert not hasattr(focal_history, "future_states")
    assert "future_targets" not in sample.encoder_inputs
    assert focal_history.is_focal is True
    assert focal_history.is_sdc is False
    assert sample.focal_track_ids == ("focal",)
    assert sample.sdc_track_id is None
    context_target = next(x for x in sample.future_targets if x.track_id == "context")
    assert context_target.valid_future_mask == (True, False)
    assert context_target.has_observed_history is True
    assert sample.benchmark_target_track_ids == ("focal",)
    assert set(sample.supervised_track_ids) == {"focal", "context"}
    assert sample.has_explicit_sdc_identity is False
    assert sample.agent_response_targets == ()
    assert set(x.track_id for x in sample.symmetric_agent_targets) == {"focal", "context"}
    assert sample.ego_future_targets == ()


def test_test_split_forecast_sample_does_not_expose_future_labels():
    sample = build_scene_forecast_sample(_forecast_scene(future_available=False))
    assert sample.future_available is False
    assert sample.future_timestamps_s == ()
    assert sample.future_targets == ()


def _actor_proposal(actor_id, mode_id="m0", length=2):
    rows = tuple((float(i), 0.0, -1.0, -1.0, 0.0, 1.0, 0.0) for i in range(length))
    return PredictionProposal.from_mtr_row(
        actor_id, mode_id, "frame-1", 0.0, 0.1, rows, 0.5,
        source="MTR++", model_version="test-v1",
    )


def test_joint_mode_keeps_correlated_agents_and_observation_history_together():
    observation = ObservationHistoryProposal(
        "obs-class-1",
        (ObservationEventProposal("msg-1", 1, "ego", "message_receipt",
                                  subject_id="rule-v2", production_step=0,
                                  delivery_step=1),),
        score=0.7,
    )
    mode = JointModeProposal(
        "joint-0", "frame-1", 0.0, 0.1,
        (_actor_proposal("ego"), _actor_proposal("car-1")),
        observation, 0.8, "MTR++", "test-v1", "ego-prefix-digest", "protocol-digest",
    )
    modes = JointModeSet("frame-1", (mode,), "MTR++")
    assert len(modes.modes[0].actor_trajectories) == 2
    assert modes.modes[0].observation_history.observation_class_id == "obs-class-1"
    assert modes.behavior_support_complete is False
    assert hard_support_from_joint_modes(modes).status.value == "UNKNOWN_UNBOUNDED_TAIL"


def test_joint_mode_rejects_misaligned_actor_horizons_and_observation_steps():
    obs = ObservationHistoryProposal("obs", ())
    with pytest.raises(Phase6CContractError):
        JointModeProposal(
            "joint", "frame-1", 0.0, 0.1,
            (_actor_proposal("ego", length=2), _actor_proposal("car", length=3)),
            obs, 0.5, "MTR++", "v1", "prefix", "protocol",
        )
    late_obs = ObservationHistoryProposal(
        "late", (ObservationEventProposal("event", 2, "ego", "silence"),)
    )
    with pytest.raises(Phase6CContractError):
        JointModeProposal(
            "joint", "frame-1", 0.0, 0.1,
            (_actor_proposal("ego"),), late_obs, 0.5, "MTR++", "v1", "prefix", "protocol",
        )
