import pytest
from rampd_core import commonroad_bmw_320i_benchmark


def test_commonroad_bmw_nominal_geometry_and_rear_axle_reference():
    p = commonroad_bmw_320i_benchmark()
    assert p.reference_point == 'rear_axle_center'
    assert p.wheelbase_m == pytest.approx(2.5789128)
    assert p.body_length_m == pytest.approx(4.508)
    assert p.body_width_m == pytest.approx(1.610)
    assert p.geometry.center_offset_x_m == pytest.approx(1.4227170936)
    assert p.geometry.center_offset_y_m == 0.0


def test_friction_is_not_silently_assigned_by_vehicle_geometry_profile():
    p = commonroad_bmw_320i_benchmark()
    assert p.friction_coefficient is None
    with pytest.raises(ValueError, match='scenario/tire-road'):
        _ = p.bicycle


def test_vehicle_model_rejects_non_rear_axle_reference_for_current_ode():
    from rampd_core.vehicle import VehicleModelParameters
    with pytest.raises(ValueError, match='rear_axle_center'):
        VehicleModelParameters('bad', 'body_center', 2.5, 4.5, 1.8, 0.0)
