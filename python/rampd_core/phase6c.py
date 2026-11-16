"""Phase 6C-A proposal ordering and co-simulation contracts.

This module intentionally contains no CARLA, SUMO, TensorFlow or Torch
imports.  It defines deterministic, testable contracts before simulator or
learned-model dependencies are introduced.

RuleNet-derived scores are heuristic ordering signals only.  They must never
prune protocol branches, narrow belief support, or be passed to the full
support verifier as physical evidence.
"""
from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
import math
from typing import Iterable, Mapping, Sequence

from .scene_schema import UnifiedScene, TrackState
from .map_context import MapContext, SignalRecord
from .forecast import PredictionProposal


class Phase6CContractError(ValueError):
    """A prediction/ranking/simulator record violates the Phase 6C contract."""


@dataclass(frozen=True)
class HistoryTrackInput:
    """Encoder-side track data; it contains no future target fields."""

    track_id: str
    category: str
    states: tuple[TrackState, ...]
    valid_observation_mask: tuple[bool, ...]
    benchmark_target: bool
    is_focal: bool
    is_sdc: bool

    def __post_init__(self):
        if not self.track_id or not self.category:
            raise Phase6CContractError("history track requires ID and category")
        if any(not isinstance(x, bool) for x in
               (self.benchmark_target, self.is_focal, self.is_sdc)):
            raise Phase6CContractError("history track identity flags must be boolean")
        if len(self.states) != len(self.valid_observation_mask):
            raise Phase6CContractError("history states and observation mask must align")
        if any(not isinstance(x, bool) for x in self.valid_observation_mask):
            raise Phase6CContractError("history observation mask must be boolean")
        if any(mask and not state.valid for state, mask in zip(self.states, self.valid_observation_mask)):
            raise Phase6CContractError("invalid states cannot be marked as valid observations")


@dataclass(frozen=True)
class FutureTrackTarget:
    """Label-side future trajectory; never included in encoder-side inputs."""

    track_id: str
    category: str
    states: tuple[TrackState, ...]
    valid_future_mask: tuple[bool, ...]
    benchmark_target: bool
    is_focal: bool
    is_sdc: bool
    has_observed_history: bool = False

    def __post_init__(self):
        if not self.track_id or not self.category:
            raise Phase6CContractError("future target requires ID and category")
        if any(not isinstance(x, bool) for x in
               (self.benchmark_target, self.is_focal, self.is_sdc,
                self.has_observed_history)):
            raise Phase6CContractError("future target identity flags must be boolean")
        if len(self.states) != len(self.valid_future_mask):
            raise Phase6CContractError("future states and mask must align")
        if any(not isinstance(x, bool) for x in self.valid_future_mask):
            raise Phase6CContractError("future mask must be boolean")
        if any(mask and not state.valid for state, mask in zip(self.states, self.valid_future_mask)):
            raise Phase6CContractError("invalid states cannot be marked as valid future labels")


@dataclass(frozen=True)
class SceneForecastSample:
    """Leakage-safe supervised sample with physically separate input/label sides."""

    scenario_id: str
    dataset: str
    split: str
    current_timestamp_s: float
    history_timestamps_s: tuple[float, ...]
    future_timestamps_s: tuple[float, ...]
    history_tracks: tuple[HistoryTrackInput, ...]
    future_targets: tuple[FutureTrackTarget, ...]
    future_available: bool
    coordinate_frame: str
    position_reference: str
    map_ids: tuple[str, ...]
    map_digest: str | None
    source_digest: str
    # Full logged map/timeline is kept outside model-facing inputs. Only static
    # geometry is exposed by default; dynamic records are supervision, not
    # proof of actual ego observations.
    map_context_history: MapContext | None = None
    future_signal_targets: tuple[SignalRecord, ...] = ()

    def __post_init__(self):
        if not self.scenario_id or not self.dataset or not self.split:
            raise Phase6CContractError("forecast sample identity is incomplete")
        if not self.history_timestamps_s:
            raise Phase6CContractError("forecast sample must have an observed history")
        if not math.isfinite(float(self.current_timestamp_s)):
            raise Phase6CContractError("current timestamp must be finite")
        all_times = (*self.history_timestamps_s, *self.future_timestamps_s)
        if any(not math.isfinite(float(x)) for x in all_times):
            raise Phase6CContractError("all forecast timestamps must be finite")
        if any(b <= a for a, b in zip(self.history_timestamps_s, self.history_timestamps_s[1:])):
            raise Phase6CContractError("history timestamps must be strictly increasing")
        if not math.isclose(self.history_timestamps_s[-1], self.current_timestamp_s,
                            rel_tol=0.0, abs_tol=1e-9):
            raise Phase6CContractError("history must end at the declared current timestamp")
        if any(b <= a for a, b in zip(self.future_timestamps_s, self.future_timestamps_s[1:])):
            raise Phase6CContractError("future timestamps must be strictly increasing")
        if self.future_timestamps_s and self.future_timestamps_s[0] <= self.current_timestamp_s:
            raise Phase6CContractError("future timestamps must follow the current timestamp")
        if not isinstance(self.future_available, bool):
            raise Phase6CContractError("future_available must be bool")
        if not self.future_available and (self.future_timestamps_s or self.future_targets):
            raise Phase6CContractError("test/no-label samples must not expose future targets")
        if self.future_available and self.future_targets and not self.future_timestamps_s:
            raise Phase6CContractError("future target states require future timestamps")
        if len({x.track_id for x in self.history_tracks}) != len(self.history_tracks):
            raise Phase6CContractError("duplicate history track IDs")
        if len({x.track_id for x in self.future_targets}) != len(self.future_targets):
            raise Phase6CContractError("duplicate future target IDs")
        if self.map_context_history is not None:
            if self.map_context_history.coordinate_frame != self.coordinate_frame:
                raise Phase6CContractError("map/track coordinate frames differ")
            if any(s.timestamp_s > self.current_timestamp_s for s in self.map_context_history.signals):
                raise Phase6CContractError("future dynamic signals in map history")
        if any(s.timestamp_s <= self.current_timestamp_s for s in self.future_signal_targets):
            raise Phase6CContractError("signal labels must follow current time")
        if not self.future_available and self.future_signal_targets:
            raise Phase6CContractError("test/no-future samples cannot expose future signals")
        if sum(1 for x in self.history_tracks if x.is_sdc) > 1:
            raise Phase6CContractError("a scene cannot contain multiple explicit SDC tracks")
        if any(len(x.states) != len(self.history_timestamps_s) for x in self.history_tracks):
            raise Phase6CContractError("history track lengths must match the history time axis")
        if any(len(x.states) != len(self.future_timestamps_s) for x in self.future_targets):
            raise Phase6CContractError("future target lengths must match the future time axis")

    @property
    def benchmark_target_track_ids(self) -> tuple[str, ...]:
        return tuple(x.track_id for x in self.future_targets if x.benchmark_target)

    @property
    def focal_track_ids(self) -> tuple[str, ...]:
        return tuple(x.track_id for x in self.history_tracks if x.is_focal)

    @property
    def sdc_track_ids(self) -> tuple[str, ...]:
        return tuple(x.track_id for x in self.history_tracks if x.is_sdc)

    @property
    def sdc_track_id(self) -> str | None:
        ids = self.sdc_track_ids
        return ids[0] if len(ids) == 1 else None

    @property
    def has_explicit_sdc_identity(self) -> bool:
        return len(self.sdc_track_ids) == 1

    @property
    def supervised_track_ids(self) -> tuple[str, ...]:
        return tuple(x.track_id for x in self.future_targets
                     if any(x.valid_future_mask))

    @property
    def ego_future_targets(self) -> tuple[FutureTrackTarget, ...]:
        """Logged SDC futures; useful for ego replay, not agent-response labels."""
        return tuple(x for x in self.future_targets if x.is_sdc)

    @property
    def agent_response_targets(self) -> tuple[FutureTrackTarget, ...]:
        """Other-agent response labels, only when an SDC identity is explicit."""
        if not self.has_explicit_sdc_identity:
            return ()
        return tuple(x for x in self.future_targets
                     if not x.is_sdc and x.has_observed_history)

    @property
    def symmetric_agent_targets(self) -> tuple[FutureTrackTarget, ...]:
        """Observed-history actor targets for datasets without an SDC identity."""
        return tuple(x for x in self.future_targets if x.has_observed_history)

    @property
    def new_agent_future_targets(self) -> tuple[FutureTrackTarget, ...]:
        """Future-visible agents with no valid observed history at current time."""
        if not self.has_explicit_sdc_identity:
            return ()
        return tuple(x for x in self.future_targets
                     if not x.is_sdc and not x.has_observed_history)

    @property
    def encoder_inputs(self) -> dict:
        """Model-facing payload: deliberately contains no future target data."""
        return {
            "scenario_id": self.scenario_id,
            "dataset": self.dataset,
            "split": self.split,
            "current_timestamp_s": self.current_timestamp_s,
            "history_timestamps_s": self.history_timestamps_s,
            "history_tracks": self.history_tracks,
            "coordinate_frame": self.coordinate_frame,
            "position_reference": self.position_reference,
            "map_ids": self.map_ids,
            "map_digest": self.map_digest,
            "static_map": (self.map_context_history.static_only()
                           if self.map_context_history is not None else None),
            # Recorded traffic-signal history is not automatically ego-visible.
            # A later observation adapter may add proven-visible signals.
        }


def build_scene_forecast_sample(scene: UnifiedScene) -> SceneForecastSample:
    """Split one parsed scene into history-only inputs and future-only labels.

    All actors with at least one valid future state are retained as supervised
    joint-scene targets.  ``to_predict`` remains the benchmark/evaluation mask;
    it does not silently discard other actors' available future labels, which
    can be useful for interaction learning.  A test split with no future
    labels yields an empty ``future_targets`` tuple.
    """
    scene.assert_valid()
    manifest = scene.manifest
    current = manifest.current_time_index
    history_times = tuple(manifest.timestamps[:current + 1])
    future_times = (tuple(manifest.timestamps[current + 1:])
                    if manifest.future_available else ())
    history_tracks: list[HistoryTrackInput] = []
    future_targets: list[FutureTrackTarget] = []
    for track in scene.tracks:
        history_states = tuple(track.states[:current + 1])
        # ``observed`` is the dataset's history/current-window marker, while
        # ``valid`` says whether a measurement exists.  Both are required.
        history_mask = tuple(
            bool(state.valid and state.observed is True) for state in history_states
        )
        history_tracks.append(HistoryTrackInput(
            track.track_id, track.category, history_states, history_mask,
            track.to_predict, track.is_focal, track.is_sdc,
        ))
        if manifest.future_available:
            future_states = tuple(track.states[current + 1:])
            future_mask = tuple(bool(state.valid) for state in future_states)
            if any(future_mask):
                future_targets.append(FutureTrackTarget(
                    track.track_id, track.category, future_states, future_mask,
                    track.to_predict, track.is_focal, track.is_sdc,
                    has_observed_history=any(history_mask),
                ))
    map_digest = scene.map_metadata.get("map_content_sha256")
    return SceneForecastSample(
        scenario_id=manifest.scenario_id,
        dataset=manifest.dataset,
        split=manifest.split,
        current_timestamp_s=manifest.timestamps[current],
        history_timestamps_s=history_times,
        future_timestamps_s=future_times,
        history_tracks=tuple(history_tracks),
        future_targets=tuple(future_targets),
        future_available=manifest.future_available,
        coordinate_frame=manifest.coordinate_frame,
        position_reference=manifest.position_reference,
        map_ids=scene.map_ids,
        map_digest=None if map_digest is None else str(map_digest),
        source_digest=manifest.source_digest,
        map_context_history=(scene.map_context.prefix(current)
                             if scene.map_context is not None else None),
        future_signal_targets=(tuple(s for s in scene.map_context.signals
                                     if s.timestep > current)
                               if scene.map_context is not None and manifest.future_available else ()),
    )


@dataclass(frozen=True)
class ObservationEventProposal:
    """One proposed future observation event, not a formal protocol fact."""

    event_id: str
    step_index: int
    observer_id: str
    event_type: str
    subject_id: str = ""
    payload_class: str = ""
    score: float = 0.0
    production_step: int | None = None
    delivery_step: int | None = None

    def __post_init__(self):
        if not self.event_id or not self.observer_id:
            raise Phase6CContractError("observation event requires event and observer IDs")
        if isinstance(self.step_index, bool) or not isinstance(self.step_index, int) or self.step_index < 0:
            raise Phase6CContractError("step_index must be a nonnegative integer")
        if self.event_type not in {
            "local_detection", "message_receipt", "traffic_signal_observation",
            "occlusion", "silence",
        }:
            raise Phase6CContractError("unsupported observation event type")
        for name in ("step_index", "production_step", "delivery_step"):
            value = getattr(self, name)
            if value is not None and (isinstance(value, bool) or not isinstance(value, int) or value < 0):
                raise Phase6CContractError(f"{name} must be a nonnegative integer or null")
        if self.delivery_step is not None and self.production_step is not None:
            if self.delivery_step < self.production_step:
                raise Phase6CContractError("observation delivery cannot precede production")
        object.__setattr__(self, "score", _finite(self.score, "observation event score"))


@dataclass(frozen=True)
class ObservationHistoryProposal:
    """A candidate observation history paired with one joint traffic mode."""

    observation_class_id: str
    events: tuple[ObservationEventProposal, ...] = ()
    score: float = 0.0

    def __post_init__(self):
        if not self.observation_class_id:
            raise Phase6CContractError("observation_class_id is required")
        events = tuple(self.events)
        if len({x.event_id for x in events}) != len(events):
            raise Phase6CContractError("observation event IDs must be unique")
        object.__setattr__(self, "events", events)
        object.__setattr__(self, "score", _finite(self.score, "observation history score"))


@dataclass(frozen=True)
class JointModeProposal:
    """One correlated multi-agent mode paired with one possible observation history.

    Grouping trajectories here is essential: the planner must not form an
    artificial joint mode by taking a Cartesian product of independent
    per-agent marginal modes.  ``score`` is a learned proposal score only;
    this object is not a probability-complete support or safety certificate.
    """

    joint_mode_id: str
    frame_id: str
    t0_s: float
    dt_s: float
    actor_trajectories: tuple[PredictionProposal, ...]
    observation_history: ObservationHistoryProposal
    score: float
    source: str
    model_version: str
    ego_prefix_digest: str
    protocol_context_digest: str

    def __post_init__(self):
        if not all((self.joint_mode_id, self.frame_id, self.source,
                    self.model_version, self.ego_prefix_digest,
                    self.protocol_context_digest)):
            raise Phase6CContractError("joint mode provenance/context is incomplete")
        t0 = _finite(self.t0_s, "joint mode t0_s")
        dt = _finite(self.dt_s, "joint mode dt_s")
        if dt <= 0:
            raise Phase6CContractError("joint mode dt_s must be positive")
        actors = tuple(self.actor_trajectories)
        if not actors:
            raise Phase6CContractError("joint mode must contain at least one actor trajectory")
        if len({x.actor_id for x in actors}) != len(actors):
            raise Phase6CContractError("joint mode has duplicate actor trajectories")
        horizons = {len(x.positions) for x in actors}
        if len(horizons) != 1:
            raise Phase6CContractError("joint-mode actor trajectories must share one horizon")
        horizon = next(iter(horizons))
        for proposal in actors:
            if proposal.frame_id != self.frame_id:
                raise Phase6CContractError("actor trajectory frame differs from joint mode frame")
            if not math.isclose(proposal.t0_s, t0, rel_tol=0.0, abs_tol=1e-9):
                raise Phase6CContractError("actor trajectory start time differs from joint mode")
            if not math.isclose(proposal.dt_s, dt, rel_tol=0.0, abs_tol=1e-9):
                raise Phase6CContractError("actor trajectory step differs from joint mode")
        if not isinstance(self.observation_history, ObservationHistoryProposal):
            raise Phase6CContractError("joint mode requires an observation history proposal")
        if any(event.step_index >= horizon for event in self.observation_history.events):
            raise Phase6CContractError("observation event lies outside the joint prediction horizon")
        object.__setattr__(self, "t0_s", t0)
        object.__setattr__(self, "dt_s", dt)
        object.__setattr__(self, "actor_trajectories", actors)
        object.__setattr__(self, "score", _finite(self.score, "joint mode score"))

    @property
    def behavior_support_complete(self) -> bool:
        return False


@dataclass(frozen=True)
class JointModeSet:
    frame_id: str
    modes: tuple[JointModeProposal, ...]
    source: str
    all_emitted_modes_retained: bool = True

    def __post_init__(self):
        modes = tuple(self.modes)
        if not self.frame_id or not self.source or not modes:
            raise Phase6CContractError("joint mode set requires frame, source and at least one mode")
        if any(x.frame_id != self.frame_id for x in modes):
            raise Phase6CContractError("joint mode set contains a mode from another frame")
        if len({x.joint_mode_id for x in modes}) != len(modes):
            raise Phase6CContractError("joint_mode_id values must be unique")
        if not isinstance(self.all_emitted_modes_retained, bool):
            raise Phase6CContractError("all_emitted_modes_retained must be bool")
        object.__setattr__(self, "modes", modes)

    def ranked(self) -> tuple[JointModeProposal, ...]:
        return tuple(sorted(self.modes, key=lambda x: (-x.score, x.joint_mode_id)))

    def top_k(self, k: int) -> "JointModeSet":
        if isinstance(k, bool) or not isinstance(k, int) or k <= 0:
            raise Phase6CContractError("k must be a positive integer")
        return JointModeSet(self.frame_id, self.ranked()[:k], self.source,
                            all_emitted_modes_retained=(
                                self.all_emitted_modes_retained and k >= len(self.modes)))

    @property
    def behavior_support_complete(self) -> bool:
        return False


def hard_support_from_joint_modes(_modes: JointModeSet):
    """Learned joint modes and observation histories cannot certify support."""
    from .forecast import ProposalAdapterResult, ProposalStatus
    return ProposalAdapterResult(
        ProposalStatus.UNKNOWN_UNBOUNDED_TAIL,
        "JOINT_MODE_PROPOSALS_DO_NOT_ENCLOSE_ALL_PROTOCOL_OR_AGENT_RESPONSES",
    )


def _finite(value: float, name: str) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise Phase6CContractError(f"{name} must be numeric") from exc
    if not math.isfinite(result):
        raise Phase6CContractError(f"{name} must be finite")
    return result


def _nonnegative(value: float, name: str) -> float:
    result = _finite(value, name)
    if result < 0:
        raise Phase6CContractError(f"{name} must be nonnegative")
    return result


def radial_ttc_s(
    position_i: Sequence[float], position_j: Sequence[float],
    velocity_i: Sequence[float], velocity_j: Sequence[float], *,
    closing_speed_epsilon_mps: float = 1e-6,
    coincident_epsilon_m: float = 1e-9,
) -> float:
    """Return constant-radial-velocity TTC, or +inf if not closing.

    This is the generalized radial TTC proxy used by RuleNet (its Eq. 5):

        TTC = -||p_i-p_j||^2 / ((p_i-p_j) dot (v_i-v_j)).

    The expression is defined as a future collision-time proxy only while the
    radial range is decreasing.  Returning a negative TTC for receding agents
    would incorrectly create a *larger* violation in ``max(delta-TTC, 0)``;
    we therefore return +inf when radial closing speed is not positive.  This
    guard is a semantic clarification for ranking, not a collision proof.
    Intersecting paths with initially non-closing radial motion still require
    trajectory/footprint analysis elsewhere.
    """
    if any(len(v) != 2 for v in (position_i, position_j, velocity_i, velocity_j)):
        raise Phase6CContractError("radial TTC inputs must be 2D vectors")
    pi = tuple(_finite(x, "position_i") for x in position_i)
    pj = tuple(_finite(x, "position_j") for x in position_j)
    vi = tuple(_finite(x, "velocity_i") for x in velocity_i)
    vj = tuple(_finite(x, "velocity_j") for x in velocity_j)
    eps_v = _nonnegative(closing_speed_epsilon_mps, "closing_speed_epsilon_mps")
    eps_p = _nonnegative(coincident_epsilon_m, "coincident_epsilon_m")
    dx, dy = pi[0] - pj[0], pi[1] - pj[1]
    dvx, dvy = vi[0] - vj[0], vi[1] - vj[1]
    distance = math.hypot(dx, dy)
    if distance <= eps_p:
        return 0.0
    radial_closing_speed = -(dx * dvx + dy * dvy) / distance
    if radial_closing_speed <= eps_v:
        return math.inf
    return distance / radial_closing_speed


@dataclass(frozen=True)
class RuleNetThresholds:
    """Thresholds reported in RuleNet, exposed as explicit config values."""

    vehicle_vehicle_ttc_s: float = 1.5
    vehicle_vru_ttc_s: float = 1.6
    vru_lateral_gap_m: float = 1.5
    longitudinal_headway_s: float = 2.0
    epsilon_ttc_s: float = 1e-7
    epsilon_distance_m: float = 1e-7

    def __post_init__(self):
        for name in ("vehicle_vehicle_ttc_s", "vehicle_vru_ttc_s",
                     "vru_lateral_gap_m", "longitudinal_headway_s",
                     "epsilon_ttc_s", "epsilon_distance_m"):
            value = _finite(getattr(self, name), name)
            if value <= 0:
                raise Phase6CContractError(f"{name} must be positive")
            object.__setattr__(self, name, value)


@dataclass(frozen=True)
class RuleInteractionTrace:
    """A directed predicted interaction trace for one subject and one peer.

    Distances must already be computed by a geometry adapter in an explicitly
    chosen subject-relative frame. For ``vehicle_vru``, actor_i is the vehicle
    subject and actor_j is the VRU. This class deliberately does not infer
    longitudinal/lateral axes from velocity direction or silently substitute
    heading, because those conventions are not fully specified in the
    RuleNet paper and differ for pedestrians/cyclists.
    """

    actor_i_id: str
    actor_j_id: str
    interaction_kind: str  # "vehicle_vehicle" or "vehicle_vru"
    ttc_s: tuple[float, ...]
    longitudinal_gap_m: tuple[float, ...]
    speed_i_mps: tuple[float, ...]
    lateral_gap_m: tuple[float, ...] = ()
    geometry_frame: str = "actor_i_heading"
    source: str = "predicted_trajectory"

    def __post_init__(self):
        if not self.actor_i_id or not self.actor_j_id or self.actor_i_id == self.actor_j_id:
            raise Phase6CContractError("interaction requires two distinct actor IDs")
        if self.interaction_kind not in {"vehicle_vehicle", "vehicle_vru"}:
            raise Phase6CContractError("unsupported interaction_kind")
        if not self.geometry_frame or not self.source:
            raise Phase6CContractError("geometry frame and metric source must be explicit")
        ttc = tuple(float(x) for x in self.ttc_s)
        longitudinal = tuple(_nonnegative(x, "longitudinal_gap_m") for x in self.longitudinal_gap_m)
        speed = tuple(_nonnegative(x, "speed_i_mps") for x in self.speed_i_mps)
        lateral = tuple(_nonnegative(x, "lateral_gap_m") for x in self.lateral_gap_m)
        if not ttc or len(ttc) != len(longitudinal) or len(ttc) != len(speed):
            raise Phase6CContractError("TTC, longitudinal gap and speed traces must be nonempty and aligned")
        if any(math.isnan(x) or x < 0 for x in ttc):
            raise Phase6CContractError("TTC values must be nonnegative or +inf")
        if self.interaction_kind == "vehicle_vru" and len(lateral) != len(ttc):
            raise Phase6CContractError("vehicle-VRU interactions require an aligned lateral-gap trace")
        if self.interaction_kind == "vehicle_vehicle" and lateral and len(lateral) != len(ttc):
            raise Phase6CContractError("optional lateral-gap trace must align with TTC")
        object.__setattr__(self, "ttc_s", ttc)
        object.__setattr__(self, "longitudinal_gap_m", longitudinal)
        object.__setattr__(self, "speed_i_mps", speed)
        object.__setattr__(self, "lateral_gap_m", lateral)


@dataclass(frozen=True)
class InteractionRisk:
    actor_i_id: str
    actor_j_id: str
    score: float
    ttc_component: float
    longitudinal_component: float
    lateral_component: float
    worst_step_index: int
    step_scores: tuple[float, ...]

    def __post_init__(self):
        if not self.actor_i_id or not self.actor_j_id:
            raise Phase6CContractError("interaction risk requires actor IDs")
        for name in ("score", "ttc_component", "longitudinal_component", "lateral_component"):
            value = _finite(getattr(self, name), name)
            if not 0.0 <= value <= 1.0:
                raise Phase6CContractError(f"{name} must lie in [0,1]")
        if isinstance(self.worst_step_index, bool) or not isinstance(self.worst_step_index, int) or self.worst_step_index < 0:
            raise Phase6CContractError("worst_step_index must be a nonnegative integer")
        step_scores = tuple(_finite(x, "interaction step score") for x in self.step_scores)
        if not step_scores or any(not 0.0 <= x <= 1.0 for x in step_scores):
            raise Phase6CContractError("interaction step scores must be a nonempty [0,1] sequence")
        if self.worst_step_index >= len(step_scores):
            raise Phase6CContractError("worst_step_index is outside the interaction horizon")
        if not math.isclose(self.score, max(step_scores), rel_tol=0.0, abs_tol=1e-12):
            raise Phase6CContractError("interaction score must equal its maximum per-step score")
        object.__setattr__(self, "step_scores", step_scores)


@dataclass(frozen=True)
class RulePriorityReport:
    """RuleNet-inspired priority with an explicit heuristic-only boundary."""

    actor_scores: tuple[tuple[str, float], ...]
    actor_step_scores: tuple[tuple[str, tuple[float, ...]], ...]
    interaction_scores: tuple[InteractionRisk, ...]
    branch_score: float | None
    complete: bool
    method: str = "rulenet_eq16_20_per_step_mean_branch_max_v2"
    ordering_only: bool = True
    support_pruned: bool = False

    def __post_init__(self):
        if not isinstance(self.complete, bool):
            raise Phase6CContractError("priority report complete flag must be bool")
        if self.complete and self.branch_score is None:
            raise Phase6CContractError("complete priority report requires a branch score")
        if self.branch_score is not None:
            score = _finite(self.branch_score, "branch_score")
            if not 0.0 <= score <= 1.0:
                raise Phase6CContractError("branch_score must lie in [0,1]")
        actor_score_map = dict(self.actor_scores)
        step_score_map = dict(self.actor_step_scores)
        if set(actor_score_map) != set(step_score_map):
            raise Phase6CContractError("actor scalar and per-step scores must cover the same actors")
        for actor, values in step_score_map.items():
            if not values or any(not 0.0 <= _finite(x, "actor step score") <= 1.0 for x in values):
                raise Phase6CContractError(f"actor {actor} has invalid per-step scores")
            if not math.isclose(actor_score_map[actor], max(values), rel_tol=0.0, abs_tol=1e-12):
                raise Phase6CContractError("actor score must be the maximum of its Eq. (20) time series")
        if not self.ordering_only or self.support_pruned:
            raise Phase6CContractError("RuleNet scores cannot prune hard support")


class RuleNetSoftRanker:
    """Compute bounded [0,1] interaction-risk scores for search ordering.

    Per-frame violations follow RuleNet's normalized forms (Eqs. 16--19).
    Equation (20) averages pairwise interaction scores over other agents at
    each time step.  For the scalar RAMP-D branch ordering only, we then take
    the maximum over each actor's time series and the maximum over actors.
    That final scalarization is an explicit RAMP-D ordering adaptation; the
    per-step Eq. (20) series is retained in the report. This is not a claim to
    reproduce the complete RuleNet neural architecture.
    """

    def __init__(self, thresholds: RuleNetThresholds | None = None):
        self.thresholds = thresholds or RuleNetThresholds()

    @staticmethod
    def _violation(threshold: float, value: float, epsilon: float) -> float:
        if math.isinf(value):
            return 0.0
        raw = max(threshold - value, 0.0) / (threshold + epsilon)
        return min(1.0, max(0.0, raw))

    def score_interaction(self, trace: RuleInteractionTrace) -> InteractionRisk:
        th = self.thresholds
        ttc_threshold = (th.vehicle_vru_ttc_s if trace.interaction_kind == "vehicle_vru"
                         else th.vehicle_vehicle_ttc_s)
        per_step = []
        for k, (ttc, longitudinal, speed) in enumerate(
            zip(trace.ttc_s, trace.longitudinal_gap_m, trace.speed_i_mps)
        ):
            v_ttc = self._violation(ttc_threshold, ttc, th.epsilon_ttc_s)
            longitudinal_threshold = speed * th.longitudinal_headway_s
            v_long = (self._violation(longitudinal_threshold, longitudinal, th.epsilon_distance_m)
                      if longitudinal_threshold > 0 else 0.0)
            v_lat = 0.0
            if trace.interaction_kind == "vehicle_vru":
                v_lat = self._violation(th.vru_lateral_gap_m, trace.lateral_gap_m[k],
                                        th.epsilon_distance_m)
            per_step.append((max(v_ttc, v_long, v_lat), v_ttc, v_long, v_lat, k))
        worst = max(per_step, key=lambda x: (x[0], -x[4]))
        return InteractionRisk(trace.actor_i_id, trace.actor_j_id,
                               worst[0], worst[1], worst[2], worst[3], worst[4],
                               tuple(x[0] for x in per_step))

    def score(self, traces: Iterable[RuleInteractionTrace], *,
              interaction_coverage_complete: bool = False) -> RulePriorityReport:
        interactions = tuple(self.score_interaction(x) for x in traces)
        if not interactions:
            if not isinstance(interaction_coverage_complete, bool):
                raise Phase6CContractError("interaction_coverage_complete must be bool")
            return RulePriorityReport((), (), (), None, False)
        by_actor: dict[str, list[InteractionRisk]] = {}
        for item in interactions:
            by_actor.setdefault(item.actor_i_id, []).append(item)
        actor_step_scores_list = []
        actor_scores_list = []
        for actor, actor_interactions in by_actor.items():
            horizons = {len(x.step_scores) for x in actor_interactions}
            if len(horizons) != 1:
                raise Phase6CContractError(
                    f"actor {actor} has interaction traces with different horizons"
                )
            horizon = next(iter(horizons))
            # RuleNet Eq. (20): average over interacting agents at each t/f.
            per_step_mean = tuple(
                sum(x.step_scores[k] for x in actor_interactions) / len(actor_interactions)
                for k in range(horizon)
            )
            actor_step_scores_list.append((actor, per_step_mean))
            actor_scores_list.append((actor, max(per_step_mean)))
        actor_step_scores = tuple(sorted(actor_step_scores_list))
        actor_scores = tuple(sorted(actor_scores_list))
        branch_score = max(score for _, score in actor_scores)
        if not isinstance(interaction_coverage_complete, bool):
            raise Phase6CContractError("interaction_coverage_complete must be bool")
        return RulePriorityReport(actor_scores, actor_step_scores, interactions, branch_score,
                                  interaction_coverage_complete)


@dataclass(frozen=True)
class BranchPriorityCandidate:
    branch_id: str
    protocol_branch_id: str
    observation_class_id: str
    proposal_score: float
    rule_priority_score: float | None
    priority_evidence_complete: bool
    payload_digest: str = ""

    def __post_init__(self):
        if not self.branch_id or not self.protocol_branch_id or not self.observation_class_id:
            raise Phase6CContractError("branch and observation identities are required")
        object.__setattr__(self, "proposal_score", _finite(self.proposal_score, "proposal_score"))
        if self.rule_priority_score is not None:
            score = _finite(self.rule_priority_score, "rule_priority_score")
            if not 0.0 <= score <= 1.0:
                raise Phase6CContractError("rule_priority_score must lie in [0,1]")
            object.__setattr__(self, "rule_priority_score", score)
        if not isinstance(self.priority_evidence_complete, bool):
            raise Phase6CContractError("priority_evidence_complete must be bool")
        if self.priority_evidence_complete and self.rule_priority_score is None:
            raise Phase6CContractError("complete priority evidence requires a score")


@dataclass(frozen=True)
class BranchOrderingResult:
    ordered_candidates: tuple[BranchPriorityCandidate, ...]
    original_branch_ids: tuple[str, ...]
    retained_branch_ids: tuple[str, ...]
    ordering_only: bool = True
    support_pruned: bool = False

    def __post_init__(self):
        original = tuple(self.original_branch_ids)
        retained = tuple(self.retained_branch_ids)
        ordered = tuple(x.branch_id for x in self.ordered_candidates)
        if (len(original) != len(set(original)) or len(retained) != len(set(retained)) or
                set(original) != set(retained) or set(original) != set(ordered)):
            raise Phase6CContractError("branch ordering must preserve the complete input branch set")
        if len(self.ordered_candidates) != len(original):
            raise Phase6CContractError("branch ordering changed candidate cardinality")
        if not self.ordering_only or self.support_pruned:
            raise Phase6CContractError("branch ordering cannot alter hard support")


def rank_policy_branches(candidates: Iterable[BranchPriorityCandidate]) -> BranchOrderingResult:
    """Order all branches; incomplete metric evidence is explored first.

    The stable key is: incomplete priority evidence first, then descending
    RuleNet risk, descending model proposal score, and branch ID.  No branch is
    dropped, even if its learned score is tiny.
    """
    items = tuple(candidates)
    ids = tuple(x.branch_id for x in items)
    if len(ids) != len(set(ids)):
        raise Phase6CContractError("branch_id values must be unique")
    ordered = tuple(sorted(items, key=lambda x: (
        0 if not x.priority_evidence_complete else 1,
        -(x.rule_priority_score if x.rule_priority_score is not None else 0.0),
        -x.proposal_score,
        x.branch_id,
    )))
    return BranchOrderingResult(ordered, ids, ids)


def _fraction(value: float | str | Fraction, name: str) -> Fraction:
    try:
        result = value if isinstance(value, Fraction) else Fraction(str(value))
    except (TypeError, ValueError, ZeroDivisionError) as exc:
        raise Phase6CContractError(f"{name} must be a finite rational number") from exc
    return result


@dataclass(frozen=True)
class CoSimulationConfig:
    """Version-independent synchrony contract for the later CARLA/SUMO bridge."""

    carla_fixed_delta_s: Fraction | float | str = Fraction(1, 20)
    sumo_step_length_s: Fraction | float | str = Fraction(1, 20)
    max_substep_delta_s: Fraction | float | str = Fraction(1, 100)
    max_substeps: int = 10
    tls_manager: str = "sumo"
    render_mode: str = "offscreen"
    tick_owner: str = "rampd_orchestrator"
    carla_synchronous_mode: bool = True
    uses_traffic_manager: bool = True
    traffic_manager_sync: bool = True
    time_tolerance_s: float = 1e-6

    def __post_init__(self):
        carla_dt = _fraction(self.carla_fixed_delta_s, "carla_fixed_delta_s")
        sumo_dt = _fraction(self.sumo_step_length_s, "sumo_step_length_s")
        substep = _fraction(self.max_substep_delta_s, "max_substep_delta_s")
        if carla_dt <= 0 or sumo_dt <= 0 or substep <= 0:
            raise Phase6CContractError("simulation step sizes must be positive")
        if carla_dt != sumo_dt:
            raise Phase6CContractError("CARLA and SUMO step lengths must be identical")
        if isinstance(self.max_substeps, bool) or not isinstance(self.max_substeps, int) or self.max_substeps <= 0:
            raise Phase6CContractError("max_substeps must be a positive integer")
        if carla_dt > substep * self.max_substeps:
            raise Phase6CContractError("CARLA fixed step exceeds the physics substep budget")
        if self.tls_manager not in {"carla", "sumo", "none"}:
            raise Phase6CContractError("tls_manager must be carla, sumo, or none")
        if self.render_mode not in {"offscreen", "no_rendering", "onscreen"}:
            raise Phase6CContractError("unsupported render_mode")
        if self.tick_owner != "rampd_orchestrator":
            raise Phase6CContractError("only the single RAMP-D orchestrator may own simulator ticks")
        if not isinstance(self.carla_synchronous_mode, bool) or not self.carla_synchronous_mode:
            raise Phase6CContractError("CARLA synchronous_mode must be enabled for fixed-step co-simulation")
        if not isinstance(self.uses_traffic_manager, bool) or not isinstance(self.traffic_manager_sync, bool):
            raise Phase6CContractError("Traffic Manager configuration flags must be bool")
        if self.uses_traffic_manager and not self.traffic_manager_sync:
            raise Phase6CContractError("Traffic Manager must be in synchronous mode when used")
        if not math.isfinite(float(self.time_tolerance_s)) or self.time_tolerance_s < 0:
            raise Phase6CContractError("time_tolerance_s must be finite and nonnegative")
        object.__setattr__(self, "carla_fixed_delta_s", carla_dt)
        object.__setattr__(self, "sumo_step_length_s", sumo_dt)
        object.__setattr__(self, "max_substep_delta_s", substep)
        object.__setattr__(self, "time_tolerance_s", float(self.time_tolerance_s))

    @property
    def sensors_available(self) -> bool:
        return self.render_mode != "no_rendering"


@dataclass(frozen=True)
class SynchronizedFrameStamp:
    step_index: int
    carla_frame: int
    carla_elapsed_s: float
    sumo_elapsed_s: float

    def __post_init__(self):
        for name in ("step_index", "carla_frame"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise Phase6CContractError(f"{name} must be a nonnegative integer")
        object.__setattr__(self, "carla_elapsed_s", _nonnegative(self.carla_elapsed_s, "carla_elapsed_s"))
        object.__setattr__(self, "sumo_elapsed_s", _nonnegative(self.sumo_elapsed_s, "sumo_elapsed_s"))


class SynchronizedFrameLedger:
    """Validate monotonically aligned simulator frames against rational dt."""

    def __init__(self, config: CoSimulationConfig, *, start_time_s: float = 0.0):
        self.config = config
        self.start_time_s = _nonnegative(start_time_s, "start_time_s")
        self._last: SynchronizedFrameStamp | None = None

    def append(self, stamp: SynchronizedFrameStamp) -> None:
        expected_step = 1 if self._last is None else self._last.step_index + 1
        if stamp.step_index != expected_step:
            raise Phase6CContractError("simulator step_index is missing, repeated, or out of order")
        if self._last is not None and stamp.carla_frame != self._last.carla_frame + 1:
            raise Phase6CContractError("CARLA frame counter is not consecutive")
        expected_time = self.start_time_s + float(self.config.carla_fixed_delta_s * stamp.step_index)
        tol = self.config.time_tolerance_s
        if abs(stamp.carla_elapsed_s - expected_time) > tol:
            raise Phase6CContractError("CARLA elapsed time disagrees with fixed-step clock")
        if abs(stamp.sumo_elapsed_s - expected_time) > tol:
            raise Phase6CContractError("SUMO elapsed time disagrees with fixed-step clock")
        self._last = stamp

    @property
    def last(self) -> SynchronizedFrameStamp | None:
        return self._last


@dataclass(frozen=True)
class SensorDeliveryRecord:
    sensor_id: str
    sensor_frame: int
    production_step: int
    delivery_step: int
    production_time_s: float
    delivery_time_s: float

    def __post_init__(self):
        if not self.sensor_id:
            raise Phase6CContractError("sensor_id is required")
        for name in ("sensor_frame", "production_step", "delivery_step"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise Phase6CContractError(f"{name} must be a nonnegative integer")
        if self.delivery_step < self.production_step:
            raise Phase6CContractError("sensor data cannot be delivered before production")
        p = _nonnegative(self.production_time_s, "production_time_s")
        d = _nonnegative(self.delivery_time_s, "delivery_time_s")
        if d < p:
            raise Phase6CContractError("sensor delivery time cannot precede production time")
        object.__setattr__(self, "production_time_s", p)
        object.__setattr__(self, "delivery_time_s", d)


class ActorIdentityRegistry:
    """Maintain explicit SUMO/CARLA/logical actor identity correspondence."""

    def __init__(self):
        self._logical_to_carla: dict[str, str] = {}
        self._logical_to_sumo: dict[str, str] = {}
        self._carla_to_logical: dict[str, str] = {}
        self._sumo_to_logical: dict[str, str] = {}

    def bind(self, logical_id: str, *, carla_id: str, sumo_id: str) -> None:
        logical_id, carla_id, sumo_id = str(logical_id), str(carla_id), str(sumo_id)
        if not logical_id or not carla_id or not sumo_id:
            raise Phase6CContractError("logical, CARLA and SUMO actor IDs must be nonempty")
        if logical_id in self._logical_to_carla or logical_id in self._logical_to_sumo:
            raise Phase6CContractError(f"logical actor already bound: {logical_id}")
        if carla_id in self._carla_to_logical or sumo_id in self._sumo_to_logical:
            raise Phase6CContractError("CARLA or SUMO actor ID is already bound")
        self._logical_to_carla[logical_id] = carla_id
        self._logical_to_sumo[logical_id] = sumo_id
        self._carla_to_logical[carla_id] = logical_id
        self._sumo_to_logical[sumo_id] = logical_id

    def resolve_carla(self, carla_id: str) -> str | None:
        return self._carla_to_logical.get(str(carla_id))

    def resolve_sumo(self, sumo_id: str) -> str | None:
        return self._sumo_to_logical.get(str(sumo_id))

    def digest(self) -> str:
        import hashlib
        import json
        payload = sorted((k, self._logical_to_carla[k], self._logical_to_sumo[k])
                         for k in self._logical_to_carla)
        return hashlib.sha256(json.dumps(payload, separators=(",", ":")).encode()).hexdigest()


__all__ = [
    "Phase6CContractError", "HistoryTrackInput", "FutureTrackTarget",
    "SceneForecastSample", "build_scene_forecast_sample",
    "ObservationEventProposal", "ObservationHistoryProposal",
    "JointModeProposal", "JointModeSet", "hard_support_from_joint_modes",
    "radial_ttc_s", "RuleNetThresholds",
    "RuleInteractionTrace", "InteractionRisk", "RulePriorityReport",
    "RuleNetSoftRanker", "BranchPriorityCandidate", "BranchOrderingResult",
    "rank_policy_branches", "CoSimulationConfig", "SynchronizedFrameStamp",
    "SynchronizedFrameLedger", "SensorDeliveryRecord", "ActorIdentityRegistry",
]
