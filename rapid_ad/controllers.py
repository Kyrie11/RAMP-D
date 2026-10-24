"""Privileged dynamic-control oracle used only to validate scene solvability."""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from marshal_bench.controllers.base import EpisodeController
from marshal_bench.utils.carla_api_compat import ensure_agents_on_path

log = logging.getLogger(__name__)


class DynamicDirectiveOracleController(EpisodeController):
    """Ground-truth reference that follows the live directive and control line.

    This is not a candidate method and must never be counted as a non-privileged
    baseline. It is a solvability/physics check for each generated scene.
    """

    name = "rapid_ad_oracle"
    track = "A"
    requests_privileged_gt = True

    def __init__(self, config: Optional[dict] = None, timeline: Optional[dict] = None):
        self.config = config or {}
        self.timeline = timeline if timeline is not None else {}
        self.world = None
        self.ego = None
        self.carla = None
        self.agent = None
        self.target_speed_kmh = float((self.config.get("ego") or {}).get("target_speed", 12.0))
        self._last_action = None

    def setup(self, world: Any, ego: Any, ground_truth: Dict[str, Any], carla: Any) -> None:
        self.world, self.ego, self.carla = world, ego, carla
        ensure_agents_on_path()
        from agents.navigation.basic_agent import BasicAgent

        opt = {
            "dt": 1.0 / float(self.config.get("fps", 20)),
            "target_speed": self.target_speed_kmh,
            "ignore_traffic_lights": True,
            "ignore_vehicles": True,
            "base_tlight_threshold": 0.0,
            "base_vehicle_threshold": 0.0,
            "max_throttle": 0.55,
            "max_brake": 0.85,
            "sampling_radius": 2.0,
        }
        self.agent = BasicAgent(ego, target_speed=self.target_speed_kmh, opt_dict=opt, map_inst=world.get_map())
        try:
            self.agent.ignore_traffic_lights(True)
            self.agent.ignore_vehicles(True)
            self.agent.ignore_stop_signs(True)
        except Exception:
            pass
        if str(self.timeline.get("initial_directive", "PROCEED")).upper() == "PROCEED":
            # Seed a small rolling start so a stationary vehicle does not make
            # the approach-phase manipulation impossible to trigger.
            try:
                tf = ego.get_transform()
                fwd = tf.get_forward_vector()
                ego.set_target_velocity(carla.Vector3D(x=fwd.x * 1.2, y=fwd.y * 1.2, z=0.0))
                ego.apply_control(carla.VehicleControl(throttle=0.28, brake=0.0, steer=0.0))
            except Exception:
                pass

    def step(self, observation: Dict[str, Any], dt: float) -> Any:
        carla = self.carla
        if carla is None:
            return None
        obs = observation or {}
        try:
            base = self.agent.run_step() if self.agent is not None else carla.VehicleControl()
        except Exception:
            base = carla.VehicleControl()
        # Copy the route-following steering and then apply a transparent
        # longitudinal reference policy based on privileged directive state.
        control = carla.VehicleControl(
            throttle=float(getattr(base, "throttle", 0.0) or 0.0),
            brake=float(getattr(base, "brake", 0.0) or 0.0),
            steer=float(getattr(base, "steer", 0.0) or 0.0),
            hand_brake=False,
        )
        directive = str(self.timeline.get("current_directive", "STOP")).upper()
        try:
            velocity = self.ego.get_velocity()
            speed = max(0.0, (float(velocity.x) ** 2 + float(velocity.y) ** 2 + float(velocity.z) ** 2) ** 0.5)
        except Exception:
            speed = max(0.0, float(obs.get("ego_speed") or 0.0))
        d_line = self.timeline.get("distance_to_control_line_m")
        try:
            d_line = float(d_line)
        except (TypeError, ValueError):
            d_line = float("inf")
        scene = self.config.get("scene") or {}
        max_decel = max(1.0, float(scene.get("max_brake_decel_mps2", 4.5)))
        reaction = max(0.0, float(scene.get("reaction_budget_s", 0.10)))
        buffer = max(0.1, float(scene.get("safety_buffer_m", 1.0)))
        half_length = 2.4
        try:
            half_length = float(self.ego.bounding_box.extent.x)
        except Exception:
            pass
        stop_envelope = half_length + buffer + (speed * speed) / (2.0 * max_decel) + speed * reaction
        target_mps = self.target_speed_kmh / 3.6

        if directive in {"STOP", "HOLD"}:
            if d_line <= stop_envelope:
                control.throttle = 0.0
                control.brake = 1.0 if speed > 0.20 else 0.75
            elif speed > target_mps:
                control.throttle = 0.0
                control.brake = 0.10
            else:
                control.throttle = min(control.throttle, 0.22)
                control.brake = 0.0
            if speed < 0.20 and d_line > half_length + 0.25:
                control.throttle = 0.0
                control.brake = 0.65
        else:
            control.brake = 0.0
            if speed < target_mps - 0.25:
                control.throttle = max(control.throttle, 0.38)
            elif speed > target_mps + 0.5:
                control.throttle = 0.0
                control.brake = 0.05
        self._last_action = directive
        return control

    def teardown(self) -> None:
        self.agent = None


__all__ = ["DynamicDirectiveOracleController"]
