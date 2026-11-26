"""Exact rational, piecewise-constant-jerk longitudinal reference.

Not a full bicycle dynamics certificate: turning, steering-rate, lateral tyre
forces, parameter uncertainty and exogenous disturbances require native Picard
and calibrated bounds.  No speed clipping or implicit zero-speed reset.
"""
from __future__ import annotations
from dataclasses import dataclass
from fractions import Fraction as Q


def _q(x):
    if type(x) is not Q: raise TypeError('use exact Fraction, not float or integer')
    return x

@dataclass(frozen=True)
class Longitudinal:
    x: Q
    v: Q
    a: Q
    def __post_init__(self):
        for v in (self.x,self.v,self.a):_q(v)
        if self.v<0:raise ValueError('negative velocity')

@dataclass(frozen=True)
class JerkLeg:
    duration: Q
    jerk: Q
    def __post_init__(self):
        if _q(self.duration)<=0:_q(self.jerk);raise ValueError('positive duration required')
        _q(self.jerk)

@dataclass(frozen=True)
class StopReference:
    initial:Longitudinal
    after_delay:Longitudinal
    delay:Q
    legs:tuple[JerkLeg,...]
    states:tuple[Longitudinal,...]
    model_scope:str='EXACT_LONGITUDINAL_NOMINAL_ONLY'
    @property
    def final(self):return self.states[-1]
    @property
    def total_time(self):return self.delay+sum((x.duration for x in self.legs),Q(0))
    @property
    def stopping_distance(self):return self.final.x-self.initial.x
    @property
    def holds_invariant_nominally(self):
        # only longitudinal state with zero disturbance, zero jerk in all future time
        return self.final.v==self.final.a==0


def propagate(x:Longitudinal,leg:JerkLeg)->Longitudinal:
    """Integrate exact x,v,a and reject any negative velocity on full leg."""
    h,j=leg.duration,leg.jerk
    times=[Q(0),h]
    if j and Q(0)<-x.a/j<h:times.append(-x.a/j)
    if min(x.v+x.a*t+j*t*t/2 for t in times)<0:
        raise ValueError('speed crosses zero in a jerk leg; no hidden saturation')
    return Longitudinal(x.x+x.v*h+x.a*h*h/2+j*h*h*h/6,
                        x.v+x.a*h+j*h*h/2,x.a+j*h)


def plan_stop(initial:Longitudinal, *,comfort_decel:Q,jerk_limit:Q,delay:Q=Q(0),
              accel_min:Q|None=None,accel_max:Q|None=None):
    """Analytical jerk-ramp / plateau / release stop, without speed reset.

    Handles arbitrary initial acceleration within stated envelope if there is
    sufficient speed for the full desired plateau profile. A short-distance
    triangular profile is not guessed; report UNKNOWN via ValueError.
    During delay j=0 and initial acceleration remains unchanged (explicit
    assumption), which is NOT a guarantee about arbitrary actual actuators.
    """
    b,J,d=_q(comfort_decel),_q(jerk_limit),_q(delay)
    if b<=0 or J<=0 or d<0:raise ValueError('invalid comfort/jerk/delay')
    if accel_min is not None and initial.a<_q(accel_min):raise ValueError('initial accel below actuator limit')
    if accel_max is not None and initial.a>_q(accel_max):raise ValueError('initial accel above actuator limit')
    if accel_min is not None and -b<_q(accel_min):raise ValueError('requested plateau exceeds actuator braking capability')
    if initial.a < -b:raise ValueError('desired plateau below current braking level; dedicated profile required')
    if initial.v==0 and initial.a==0 and d==0:
        return StopReference(initial,initial,d,(),(initial,))
    after=propagate(initial,JerkLeg(d,Q(0))) if d else initial
    if after.v==0 and after.a==0:
        return StopReference(initial,after,d,(),(after,))
    t1=(after.a+b)/J
    # Determine whether a full comfort plateau is feasible BEFORE executing
    # any segment. Short-stop cases need a distinct triangular construction.
    dv1=after.a*t1-J*t1*t1/2
    t3=b/J
    dv3=-b*t3+J*t3*t3/2
    th=(after.v+dv1+dv3)/b
    if th<0:raise ValueError('UNKNOWN_TRIANGULAR_STOP_PROFILE')
    legs=[];s=after;states=[after]
    if t1:
        first=JerkLeg(t1,-J);s=propagate(s,first);legs.append(first);states.append(s)
    if th:
        middle=JerkLeg(th,Q(0));s=propagate(s,middle);legs.append(middle);states.append(s)
    last=JerkLeg(t3,J);s=propagate(s,last);legs.append(last);states.append(s)
    if s.v or s.a:raise ArithmeticError('exact profile failed to stop')
    return StopReference(initial,after,d,tuple(legs),tuple(states))


def nominal_stop_invariant(ref:StopReference, *,jerk_after:Q,steering_rate_after:Q,
                            disturbances_zero:bool)->bool:
    """Only kinematic stationary state under zero disturbance and zero control.
    Real steering actuator dynamics and a safe physical footprint not proved.
    """
    return (ref.holds_invariant_nominally and _q(jerk_after)==0 and
            _q(steering_rate_after)==0 and disturbances_zero is True)
