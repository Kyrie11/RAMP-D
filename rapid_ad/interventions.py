"""Controlled observation interventions and transparent controller proxy."""
from __future__ import annotations

from typing import Any


class EvidenceFrameHold:
    """Proxy that replays the last pre-gap RGB frame during a scheduled evidence gap.

    The CARLA world and ground-truth directive keep evolving. Only the image
    delivered to the controller is held; ego state and other observation fields
    remain live. This is an intervention on visual evidence availability, not
    a claim that the scene itself is physically occluded.
    """

    def __init__(self, controller: Any, timeline: dict, logger: Any, fps: float = 20.0):
        self._controller = controller
        self._timeline = timeline
        self._logger = logger
        self._frame_guard_s = 1.0 / max(float(fps), 1.0)
        self._cached_image = None
        self._cached_image_time = None
        self._last_mask_active = False
        self._last_decision_count = None

    def __getattr__(self, name: str) -> Any:
        return getattr(self._controller, name)

    def setup(self, world: Any, ego: Any, ground_truth: dict, carla: Any) -> None:
        self._controller.setup(world, ego, ground_truth, carla)
        hist = getattr(self._controller, "decision_history", None)
        self._last_decision_count = len(hist) if isinstance(hist, list) else None

    def step(self, observation: dict, dt: float) -> Any:
        obs = dict(observation or {})
        sim_time = float(obs.get("sim_time", self._timeline.get("last_sim_time", 0.0)) or 0.0)
        image = obs.get("image")
        gap_active = bool(self._timeline.get("evidence_gap_active", False))
        transition_time = self._timeline.get("transition_time")
        # One sensor-frame guard accounts for the fact that the scenario hook
        # changes the gesture after the current synchronous sensor frame exists.
        frame_guard = transition_time is not None and sim_time < float(transition_time) + self._frame_guard_s - 1e-6
        mask_active = gap_active or frame_guard

        if image is not None and not mask_active:
            try:
                self._cached_image = image.copy()
            except Exception:
                self._cached_image = image
            self._cached_image_time = sim_time
        elif mask_active and self._cached_image is not None:
            obs["image"] = self._cached_image
        # If the first frame is already masked, do not manufacture an image;
        # let the underlying controller handle a missing image normally.
        age = None
        if mask_active and self._cached_image_time is not None:
            age = max(0.0, sim_time - float(self._cached_image_time))
        elif image is not None:
            age = 0.0

        self._logger.log_metric_row(
            t=sim_time,
            rapid_ad_evidence_gap_planned=int(gap_active),
            rapid_ad_input_mask_active=int(mask_active),
            rapid_ad_input_image_age_s=age if age is not None else "",
        )
        if mask_active and not self._last_mask_active:
            self._logger.log_event(
                "rapid_ad_evidence_mask_started", t=sim_time,
                image_cache_time=self._cached_image_time,
                transition_time=transition_time,
            )
        if not mask_active and self._last_mask_active:
            self._logger.log_event(
                "rapid_ad_evidence_mask_ended", t=sim_time,
                image_age_s=age,
                transition_time=transition_time,
            )
        self._last_mask_active = mask_active
        # Record the first frame that is genuinely available after the phase
        # anchor. For a transition, the one-frame guard prevents counting the
        # pre-transition camera frame as fresh evidence.
        if (not mask_active and self._timeline.get("anchor_triggered")
                and self._timeline.get("raw_evidence_available_time") is None):
            self._timeline["raw_evidence_available_time"] = sim_time
            self._timeline["evidence_available_time"] = sim_time
            self._timeline["first_fresh_image_time"] = sim_time

        control = self._controller.step(obs, dt)
        try:
            self._logger.log_metric_row(
                t=sim_time,
                rapid_ad_command_throttle=float(getattr(control, "throttle", 0.0)),
                rapid_ad_command_brake=float(getattr(control, "brake", 0.0)),
                rapid_ad_command_steer=float(getattr(control, "steer", 0.0)),
            )
        except Exception:
            pass

        history = getattr(self._controller, "decision_history", None)
        if isinstance(history, list):
            now_count = len(history)
            if self._last_decision_count is not None and now_count > self._last_decision_count:
                decision = history[-1] if history else {}
                self._logger.log_event(
                    "rapid_ad_decision_input", t=sim_time,
                    action=decision.get("action"),
                    image_age_s=age,
                    mask_active=mask_active,
                    query_sim_time=decision.get("sim_time", sim_time),
                )
            self._last_decision_count = now_count
        return control

    def teardown(self) -> None:
        teardown = getattr(self._controller, "teardown", None)
        if callable(teardown):
            teardown()
