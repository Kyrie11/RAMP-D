"""Explicit, reproducible SUMO stress profiles.

Changing a random seed alone DOES NOT create distinct traffic scenarios if
sigma and speedDev are zero and departures/routes are deterministic.
"""
from dataclasses import dataclass
from math import ceil

@dataclass(frozen=True)
class TrafficProfile:
    name:str
    car_speed:float
    accel:float
    decel:float
    emergency_decel:float
    min_gap:float
    tau:float
    sigma:float
    speed_dev:float
    period_a:float
    period_b:float
    horizon:float=120.
    def __post_init__(self):
        from math import isfinite
        numbers=(self.car_speed,self.accel,self.decel,self.emergency_decel,
                 self.min_gap,self.tau,self.sigma,self.speed_dev,self.period_a,self.period_b,self.horizon)
        if (not self.name or not all(isfinite(x) for x in numbers) or
            min(self.car_speed,self.accel,self.decel,self.emergency_decel,self.min_gap,
                self.tau,self.period_a,self.period_b,self.horizon)<=0 or
            not 0<=self.sigma<=1 or not 0<=self.speed_dev<=1 or
            self.decel>self.emergency_decel or self.horizon<=1):
            raise ValueError('invalid physical/test profile')
    @property
    def expected_vehicles(self):
        return ceil(self.horizon/self.period_a)+ceil((self.horizon-1)/self.period_b)

PROFILES={
    'baseline':TrafficProfile('baseline',8,2,4,8,2,1.5,0,0,3,4),
    'dense':TrafficProfile('dense',8,2,4,8,2,1.5,.3,.08,2.5,3.3),
    'slow_reaction':TrafficProfile('slow_reaction',7,1.7,3,8,2.5,2.2,.2,.08,3,4),
    'lower_friction_proxy':TrafficProfile('lower_friction_proxy',6,1.6,2.8,6,2.5,1.7,.25,.05,3.3,4.5),
}

def get_profile(name):
    if name not in PROFILES:raise ValueError('unknown SUMO profile '+str(name))
    return PROFILES[name]
