"""A68 model-interface audit: paper jerk/steer-rate -> Waymax a/kappa.

Waymax probe uses constant acceleration and curvature per discrete time step;
paper's state has acceleration and road-wheel steering, controls jerk and
steering rate. Only the longitudinal constant-jerk versus constant-accel
endpoint discrepancy is exact here. Lateral dynamics and physical errors are
NOT certified by this nominal adapter.
"""
from __future__ import annotations
from dataclasses import dataclass
from fractions import Fraction as Q
from math import tan,pi,isfinite

@dataclass(frozen=True)
class JerkSteerState:
    speed: Q
    acceleration: Q
    steer_angle_rad: Q
    def __post_init__(self):
        if any(type(x) is not Q for x in (self.speed,self.acceleration,self.steer_angle_rad)):
            raise TypeError('exact nominal state required')
        if self.speed<0:raise ValueError('nonnegative initial speed required')


def audit_waymax_piecewise_action(s:JerkSteerState, *,dt:Q,jerk:Q,
                                   steering_rate_radps:Q,wheelbase_m:Q) -> dict:
    if not isinstance(s,JerkSteerState) or any(type(x) is not Q for x in
             (dt,jerk,steering_rate_radps,wheelbase_m)):
        raise TypeError('explicit exact model values required')
    if dt<=0 or wheelbase_m<=0:raise ValueError('positive time and wheelbase')
    a1=s.acceleration+jerk*dt
    delta1=s.steer_angle_rad+steering_rate_radps*dt
    speed1=s.speed+s.acceleration*dt+jerk*dt*dt/2
    if speed1<0:raise ValueError('STOP_REVERSAL_UNSUPPORTED_NO_SATURATION')
    # Even positive endpoint speeds can hide an interior reversal for a jerk
    # that changes a negative acceleration into a positive one. Waymax's
    # nonnegative-speed state is not the signed integrator being approximated.
    if jerk != 0:
        tstar=-s.acceleration/jerk
        if Q(0)<tstar<dt:
            vstar=s.speed+s.acceleration*tstar+jerk*tstar*tstar/2
            if vstar<0:raise ValueError('INTERIOR_STOP_REVERSAL_UNSUPPORTED_NO_SATURATION')
    if max(abs(float(s.steer_angle_rad)),abs(float(delta1)))>=pi/2-1e-3:
        raise ValueError('STEERING_NEAR_SINGULAR_CURVATURE')
    am=(s.acceleration+a1)/2
    dm=(s.steer_angle_rad+delta1)/2
    k0=tan(float(s.steer_angle_rad))/float(wheelbase_m)
    k1=tan(float(delta1))/float(wheelbase_m)
    km=tan(float(dm))/float(wheelbase_m)
    if not all(isfinite(x) for x in (k0,k1,km)):raise ValueError('nonfinite curvature')
    return dict(schema='rampd.a68.waymax_input_contract.v1',
                status='NOMINAL_DISCRETE_ACTION_ADAPTER_WITH_EXPLICIT_MISMATCH',
                waymax_action_accel_mps2=float(am),
                waymax_action_curvature_per_m=km,
                acceleration_range_mps2=(float(min(s.acceleration,a1)),float(max(s.acceleration,a1))),
                curvature_range_per_m=(min(k0,k1),max(k0,k1)),
                exact_nominal_terminal_speed_mps=str(speed1),
                nominal_longitudinal_position_discrepancy_abs_m=str(abs(jerk)*dt**3/12),
                control_semantics='MIDPOINT_CONSTANT_A_AND_CURVATURE_FOR_DISCRETE_WAYMAX_ONLY',
                coordinate_frame_alignment_verified=False,
                lateral_discretization_error_bounded=False,
                other_actor_response_support_complete=False,
                physical_enclosure_certified=False,safe_training_labels_allowed=False)
