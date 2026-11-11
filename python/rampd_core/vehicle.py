"""Explicit vehicle reference-point and geometry calibration contract.

The paper's kinematic bicycle equations use the centre of the rear axle as
(px, py). Geometry is transformed from that point to the body rectangle.
The bundled BMW 320i values are a reproducible CommonRoad benchmark profile;
the CG-as-rectangle-centre offset is explicitly a nominal proxy, not a CARLA
or production-vehicle calibration.
"""
from __future__ import annotations
from dataclasses import dataclass
import math
from .model import BicycleParameters
from .footprint import VehicleGeometry


@dataclass(frozen=True)
class VehicleModelParameters:
    vehicle_id: str
    reference_point: str
    wheelbase_m: float
    body_length_m: float
    body_width_m: float
    reference_to_body_center_x_m: float
    reference_to_body_center_y_m: float = 0.0
    friction_coefficient: float | None = None
    gravity_mps2: float = 9.80665
    front_axle_to_cg_m: float | None = None
    rear_axle_to_cg_m: float | None = None
    geometry_calibration: str = "measured"

    def __post_init__(self):
        if self.reference_point != "rear_axle_center":
            raise ValueError("Phase 1 bicycle equations require rear_axle_center reference")
        if not self.vehicle_id:
            raise ValueError("vehicle_id must be nonempty")
        for name in ("wheelbase_m", "body_length_m", "body_width_m", "gravity_mps2"):
            value = float(getattr(self, name))
            if not math.isfinite(value) or value <= 0:
                raise ValueError(f"{name} must be finite and positive")
            object.__setattr__(self, name, value)
        if self.friction_coefficient is not None:
            value = float(self.friction_coefficient)
            if not math.isfinite(value) or value <= 0:
                raise ValueError("friction_coefficient must be finite and positive")
            object.__setattr__(self, "friction_coefficient", value)
        for name in ("reference_to_body_center_x_m", "reference_to_body_center_y_m"):
            value = float(getattr(self, name))
            if not math.isfinite(value):
                raise ValueError(f"{name} must be finite")
            object.__setattr__(self, name, value)
        for name in ("front_axle_to_cg_m", "rear_axle_to_cg_m"):
            value = getattr(self, name)
            if value is not None:
                value = float(value)
                if not math.isfinite(value) or value <= 0:
                    raise ValueError(f"{name} must be finite and positive")
                object.__setattr__(self, name, value)
        if (self.front_axle_to_cg_m is not None and self.rear_axle_to_cg_m is not None):
            if abs((self.front_axle_to_cg_m + self.rear_axle_to_cg_m) - self.wheelbase_m) > 1e-5:
                raise ValueError("front/rear CG axle distances do not sum to wheelbase")
        if not self.geometry_calibration:
            raise ValueError("geometry_calibration must describe provenance")

    @property
    def bicycle(self) -> BicycleParameters:
        if self.friction_coefficient is None:
            raise ValueError("mu_f is a scenario/tire-road parameter; supply a calibrated lower bound before friction verification")
        return BicycleParameters(self.wheelbase_m, self.friction_coefficient,
                                 self.gravity_mps2)

    @property
    def geometry(self) -> VehicleGeometry:
        return VehicleGeometry(self.body_length_m, self.body_width_m,
                               self.reference_to_body_center_x_m,
                               self.reference_to_body_center_y_m)

    def as_dict(self) -> dict:
        return {
            "vehicle_id": self.vehicle_id,
            "reference_point": self.reference_point,
            "wheelbase_m": self.wheelbase_m,
            "body_length_m": self.body_length_m,
            "body_width_m": self.body_width_m,
            "reference_to_body_center_x_m": self.reference_to_body_center_x_m,
            "reference_to_body_center_y_m": self.reference_to_body_center_y_m,
            "friction_coefficient": self.friction_coefficient,
            "gravity_mps2": self.gravity_mps2,
            "front_axle_to_cg_m": self.front_axle_to_cg_m,
            "rear_axle_to_cg_m": self.rear_axle_to_cg_m,
            "geometry_calibration": self.geometry_calibration,
        }


def commonroad_bmw_320i_benchmark() -> VehicleModelParameters:
    """CommonRoad BMW 320i nominal benchmark, not a universal fleet vehicle.

    Dimensions and axle-to-CG distances are from the CommonRoad BMW 320i
    parameter profile. The body rectangle centre is provisionally placed at
    the CG, so the rear-axle-to-centre offset equals b. Replace this proxy with
    the measured body bounding-box offset before any physical safety claim.
    """
    a = 1.1561957064
    b = 1.4227170936
    return VehicleModelParameters(
        vehicle_id="commonroad_bmw_320i_nominal",
        reference_point="rear_axle_center",
        wheelbase_m=a + b,
        body_length_m=4.508,
        body_width_m=1.610,
        reference_to_body_center_x_m=b,
        reference_to_body_center_y_m=0.0,
        friction_coefficient=None,
        gravity_mps2=9.81,
        front_axle_to_cg_m=a,
        rear_axle_to_cg_m=b,
        geometry_calibration="nominal_CG_as_body_rectangle_center_proxy; calibrate from actual bounding box",
    )
