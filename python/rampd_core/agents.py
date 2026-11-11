"""Conservative other-agent reachable tubes used by the Phase 4 verifier."""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math
from .interval import Interval
from .model import StateBounds, ControlBounds, BicycleParameters
from .reachability import PicardOptions, TubeResult, integrate
from .footprint import VehicleGeometry


def _shift(base: Interval, gain: float, source: Interval) -> Interval:
    return base + Interval.point(float(gain)) * source


@dataclass(frozen=True)
class OtherAgentModel:
    """A declared response envelope for one other bicycle agent.

    ``base_control`` covers autonomous input and ``ego_control_gain`` widens
    it for every ego command in the supplied image.  The model is sound only
    for the declared bounded-response class; an unsupported actor must be
    represented as UNKNOWN by the caller rather than replaced by a learned
    nominal trajectory.
    """

    actor_id: str
    initial_state: StateBounds
    geometry: VehicleGeometry
    params: BicycleParameters
    base_control: ControlBounds
    derivative_disturbance: tuple[Interval, ...]
    ego_control_gain: tuple[float, float] = (0.0, 0.0)
    options: PicardOptions = PicardOptions(max_step_s=0.03125)
    supports_ego_response: bool = True

    def __post_init__(self):
        if not self.actor_id or len(self.derivative_disturbance) != 6:
            raise ValueError("other agent requires id and six disturbance intervals")
        if any(not isinstance(x, Interval) for x in self.derivative_disturbance):
            raise TypeError("disturbance intervals required")
        if len(self.ego_control_gain) != 2:
            raise ValueError("ego control gain must have two entries")
        gains = tuple(float(x) for x in self.ego_control_gain)
        if any(not math.isfinite(x) for x in gains):
            raise ValueError("ego response gains must be finite")
        object.__setattr__(self, "ego_control_gain", gains)

    def response_control(self, ego_control: ControlBounds | None) -> ControlBounds:
        if ego_control is None:
            return self.base_control
        if not self.supports_ego_response and any(self.ego_control_gain):
            raise ValueError("model disables declared ego response")
        return ControlBounds(
            _shift(self.base_control.jerk, self.ego_control_gain[0], ego_control.jerk),
            _shift(self.base_control.steering_rate, self.ego_control_gain[1], ego_control.steering_rate),
        )

    def reachable(self, horizon_s: float, *, ego_control: ControlBounds | None = None,
                  options: PicardOptions | None = None) -> TubeResult:
        """Integrate the complete allowed response envelope over the interval."""
        control = self.response_control(ego_control)
        return integrate(self.initial_state, control, self.params, horizon_s,
                         options or self.options, self.derivative_disturbance)

    @property
    def digest(self):
        def state(value):
            return [[x.lo, x.hi] for x in value.as_tuple()]
        def control(value):
            return [[x.lo, x.hi] for x in value.as_tuple()]
        payload = {
            "actor_id": self.actor_id, "initial_state": state(self.initial_state),
            "geometry": {"length": self.geometry.length_m, "width": self.geometry.width_m,
                          "offset_x": self.geometry.center_offset_x_m,
                          "offset_y": self.geometry.center_offset_y_m},
            "wheelbase": self.params.wheelbase_m,
            "friction": self.params.friction_coefficient,
            "gravity": self.params.gravity_mps2,
            "base_control": control(self.base_control),
            "disturbance": [[x.lo, x.hi] for x in self.derivative_disturbance],
            "ego_control_gain": list(self.ego_control_gain),
            "supports_ego_response": self.supports_ego_response,
            "options": self.options.__dict__,
        }
        raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
        return "agent-model-sha256:" + hashlib.sha256(raw).hexdigest()


@dataclass(frozen=True)
class AgentTubeEvidence:
    actor_id: str
    horizon_s: float
    result: TubeResult
    source_model_digest: str

    def __post_init__(self):
        horizon = float(self.horizon_s)
        if not self.actor_id or not math.isfinite(horizon) or horizon <= 0:
            raise ValueError("agent tube evidence needs a positive horizon")
        object.__setattr__(self, "horizon_s", horizon)
        if not isinstance(self.result, TubeResult):
            raise TypeError("agent tube evidence result must be TubeResult")
        if not isinstance(self.source_model_digest, str) or not self.source_model_digest:
            raise ValueError("agent model digest is required")


def validate_agent_model(model: OtherAgentModel) -> tuple[bool, str]:
    """Reject malformed/unsupported models before they enter a certificate."""
    try:
        if any(not isinstance(x, Interval) for x in model.derivative_disturbance):
            return False, "DISTURBANCE_NOT_INTERVAL"
        if any(not math.isfinite(g) for g in model.ego_control_gain):
            return False, "NONFINITE_EGO_RESPONSE_GAIN"
        return True, "MODEL_DECLARED"
    except Exception as exc:
        return False, f"MODEL_INVALID:{type(exc).__name__}"
