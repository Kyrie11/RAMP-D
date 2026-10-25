"""Controlled visual-evidence interventions and a transparent controller proxy."""
from __future__ import annotations

from pathlib import Path
from typing import Any


class EvidenceFrameHold:
    """Replay the last unmasked front-RGB image during a scheduled evidence gap.

    This is an image-input staleness intervention, not physical occlusion. The
    CARLA world, directive ground truth, and non-image observation fields remain
    live. Only camera-only policies should be interpreted as directly exposed to
    this intervention unless their complete sensor interface is explicitly wired.
    """

    def __init__(self, controller: Any, timeline: dict, logger: Any, fps: float = 20.0,
                 save_diagnostic_frames: bool = True, max_diagnostic_frames: int = 8):
        self._controller = controller
        self._timeline = timeline
        self._logger = logger
        self._fps = max(float(fps), 1.0)
        self._frame_guard_s = 1.0 / self._fps
        self._cached_image = None
        self._cached_image_time = None
        self._last_mask_active = False
        self._last_decision_count = None
        self._save_frames = bool(save_diagnostic_frames)
        self._max_frames = max(0, int(max_diagnostic_frames))
        self._saved_frame_labels: set[str] = set()

    def __getattr__(self, name: str) -> Any:
        return getattr(self._controller, name)

    def setup(self, world: Any, ego: Any, ground_truth: dict, carla: Any) -> None:
        self._controller.setup(world, ego, ground_truth, carla)
        hist = getattr(self._controller, "decision_history", None)
        self._last_decision_count = len(hist) if isinstance(hist, list) else None

    def _save_image(self, label: str, image: Any, sim_time: float) -> None:
        if not self._save_frames or label in self._saved_frame_labels or len(self._saved_frame_labels) >= self._max_frames or image is None:
            return
        try:
            import numpy as np
            from PIL import Image

            pil = None
            # CARLA Image objects expose raw BGRA bytes; convert them explicitly
            # so STOP red remains visually interpretable.
            if hasattr(image, "raw_data") and hasattr(image, "width") and hasattr(image, "height"):
                arr = np.frombuffer(image.raw_data, dtype=np.uint8).reshape(int(image.height), int(image.width), 4)
                pil = Image.fromarray(arr[:, :, [2, 1, 0]], mode="RGB")
            elif isinstance(image, Image.Image):
                pil = image.convert("RGB")
            else:
                arr = np.asarray(image)
                if arr.ndim != 3 or arr.shape[2] not in (3, 4):
                    return
                if arr.shape[2] == 4:
                    arr = arr[:, :, :3]
                pil = Image.fromarray(arr.astype("uint8", copy=False), mode="RGB")

            max_w, max_h = 640, 360
            if pil.width > max_w or pil.height > max_h:
                pil.thumbnail((max_w, max_h), getattr(Image, "Resampling", Image).LANCZOS)
            out_dir = Path(self._logger.episode_dir) / "diagnostic_frames"
            out_dir.mkdir(parents=True, exist_ok=True)
            path = out_dir / f"{len(self._saved_frame_labels):02d}_{label}_t{sim_time:.2f}.jpg"
            pil.save(str(path), format="JPEG", quality=86, optimize=True)
            self._saved_frame_labels.add(label)
            self._timeline.setdefault("diagnostic_frames", []).append({"label": label, "path": str(path), "sim_time": float(sim_time)})
        except Exception as exc:
            self._timeline.setdefault("diagnostic_frame_errors", []).append(f"{label}: {exc!r}")

    def step(self, observation: dict, dt: float) -> Any:
        obs = dict(observation or {})
        sim_time = float(obs.get("sim_time", self._timeline.get("last_sim_time", 0.0)) or 0.0)
        raw_image = obs.get("image")
        gap_active = bool(self._timeline.get("evidence_gap_active", False))
        transition_time = self._timeline.get("transition_time")
        frame_guard = transition_time is not None and sim_time < float(transition_time) + self._frame_guard_s - 1e-6
        mask_active = gap_active or frame_guard

        if raw_image is not None and not mask_active:
            try:
                self._cached_image = raw_image.copy()
            except Exception:
                self._cached_image = raw_image
            self._cached_image_time = sim_time
        elif mask_active and self._cached_image is not None:
            obs["image"] = self._cached_image
            self._timeline["mask_substitution_count"] = int(self._timeline.get("mask_substitution_count", 0)) + 1
            self._timeline["last_mask_delivered_image_time"] = self._cached_image_time
            self._timeline["last_mask_raw_image_time"] = sim_time if raw_image is not None else None
        elif mask_active and self._cached_image is None:
            # Do not silently treat a requested intervention as realized if no
            # pre-intervention frame exists. The raw image is passed through so
            # the controller can keep running, but this episode is invalid for
            # causal analysis and will be marked mask_cache_miss.
            self._timeline["mask_cache_miss"] = True

        age = None
        if mask_active and self._cached_image_time is not None:
            age = max(0.0, sim_time - float(self._cached_image_time))
        elif raw_image is not None:
            age = 0.0

        if raw_image is not None and "first_raw_frame" not in self._saved_frame_labels:
            self._save_image("first_raw_frame", raw_image, sim_time)
        if mask_active and not self._last_mask_active:
            self._timeline["input_mask_start_time"] = sim_time
            self._save_image("first_mask_raw", raw_image, sim_time)
            self._save_image("first_mask_delivered", obs.get("image"), sim_time)
            self._logger.log_event(
                "rapid_ad_input_mask_started", t=sim_time,
                image_cache_time=self._cached_image_time,
                transition_time=transition_time,
                planned_gap_active=gap_active,
                frame_guard_active=bool(frame_guard),
                cache_available=self._cached_image is not None,
            )
        if not mask_active and self._last_mask_active:
            self._timeline["input_mask_end_time"] = sim_time
            self._save_image("first_fresh_raw", raw_image, sim_time)
            self._save_image("first_fresh_delivered", obs.get("image"), sim_time)
            self._logger.log_event(
                "rapid_ad_input_mask_ended", t=sim_time,
                image_age_s=age,
                transition_time=transition_time,
                actual_mask_duration_s=(float(sim_time) - float(self._timeline.get("input_mask_start_time", sim_time))),
                mask_substitution_count=int(self._timeline.get("mask_substitution_count", 0)),
            )
        if transition_time is not None and abs(sim_time - float(transition_time)) <= self._frame_guard_s * 0.51:
            self._save_image("transition_raw", raw_image, sim_time)
            self._save_image("transition_delivered", obs.get("image"), sim_time)

        self._logger.log_metric_row(
            t=sim_time,
            rapid_ad_evidence_gap_planned=int(gap_active),
            rapid_ad_input_mask_active=int(mask_active),
            rapid_ad_input_image_age_s=age if age is not None else "",
        )
        self._last_mask_active = mask_active

        # Only an actual control transition creates a new cue. Static placebo
        # cells deliberately have no evidence_available_time.
        if (transition_time is not None and not mask_active and raw_image is not None
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
                summary_keys = ("action", "parsed_action", "reasoning", "rationale", "text", "response", "plan", "trajectory", "instruction", "state")
                decision_summary = {}
                for key in summary_keys:
                    if key in decision:
                        value = decision.get(key)
                        if isinstance(value, (str, int, float, bool)) or value is None:
                            decision_summary[key] = value if not isinstance(value, str) else value[:1200]
                        else:
                            decision_summary[key] = str(value)[:1200]
                self._logger.log_event(
                    "rapid_ad_decision_input", t=sim_time,
                    action=decision.get("action", decision.get("parsed_action")),
                    decision_fields=list(decision.keys()) if isinstance(decision, dict) else [],
                    decision_summary=decision_summary,
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
