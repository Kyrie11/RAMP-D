"""Explicit body-centre -> rear-axle calibration and lateral-slip preflight.

Geometric box centre, mass centre (CG), and wheelbase are DIFFERENT quantities.
A nominal CG offset is never sufficient to certify the geometric body centre.
"""
from dataclasses import dataclass
from math import sin,cos,isfinite

@dataclass(frozen=True)
class FrameCalibration:
    body_x_from_rear:float
    body_y_from_rear:float
    wheelbase_m:float
    provenance:str
    lateral_residual_max_mps:float
    def __post_init__(self):
        z=(self.body_x_from_rear,self.body_y_from_rear,self.wheelbase_m,self.lateral_residual_max_mps)
        if not all(isfinite(x) for x in z) or self.wheelbase_m<=0 or self.lateral_residual_max_mps<0 or not self.provenance:
            raise ValueError('calibration and provenance required')


def transform_observed_center(x,y,yaw,vx,vy,yaw_rate,calibration:FrameCalibration):
    if not isinstance(calibration,FrameCalibration) or not all(isfinite(t) for t in (x,y,yaw,vx,vy,yaw_rate)):
        raise ValueError('finite state and explicit calibration required')
    c,s=cos(yaw),sin(yaw)
    ox,oy=calibration.body_x_from_rear,calibration.body_y_from_rear
    dx,dy=c*ox-s*oy,s*ox+c*oy
    rx,ry=vx+yaw_rate*dy,vy-yaw_rate*dx
    longitudinal=c*rx+s*ry
    lateral=-s*rx+c*ry
    return {'rear_px':x-dx,'rear_py':y-dy,'rear_speed_model':longitudinal,
            'lateral_velocity_residual_mps':lateral,
            'status':'KINEMATIC_REFERENCE_NOMINAL_PASS' if longitudinal>=0 and abs(lateral)<=calibration.lateral_residual_max_mps else 'UNKNOWN_NO_SLIP_MODEL',
            'certified_physical':False,'calibration_ref':calibration.provenance}
