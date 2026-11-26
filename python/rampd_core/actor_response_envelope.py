"""Bounded Cartesian acceleration/yaw-rate response envelope.

This is a declared differential inclusion, not an inferred driver model.
No independence of trajectories is assumed: a product overapproximation
covers arbitrary coupled responses within all declared derivative bounds.
Position is the reference point specified by each VehicleGeometry.
"""
from dataclasses import dataclass
from fractions import Fraction
from .interval import Interval
from .model import StateBounds
from .footprint import VehicleGeometry,SweptFootprint
from .exact_time import binary64_bracket

COORDS=('px','py','vx','vy','heading')

@dataclass(frozen=True)
class ActorEnvelope:
    actor_id: str
    geometry: VehicleGeometry
    ax: Interval
    ay: Interval
    yaw_rate: Interval
    model_ref: str

    def __post_init__(self):
        if (not isinstance(self.actor_id,str) or not self.actor_id or self.actor_id=='ego' or ':' in self.actor_id or
            not isinstance(self.geometry,VehicleGeometry) or not all(isinstance(x,Interval) for x in (self.ax,self.ay,self.yaw_rate)) or
            not isinstance(self.model_ref,str) or not self.model_ref):
            raise ValueError('declared actor identity, geometry, derivative bounds and source required')

    @property
    def keys(self): return tuple(f'{self.actor_id}:{k}' for k in COORDS)

    def enclosure(self, other, lo: Fraction, hi: Fraction):
        """Enclose all trajectories on closed local [lo,hi] from step start.

        Integral p(t)=p0+v0*t+int_0^t (t-s)a(s)ds. Kernel >=0;
        interval multiplication by t^2/2 covers even time-varying acceleration.
        Heading is unwrapped. Geometry uses only px,py,heading.
        """
        if type(lo) is not Fraction or type(hi) is not Fraction or not 0<=lo<=hi:
            raise ValueError('bad exact subslab')
        p,q,vx,vy,heading=(other[k] for k in self.keys)
        t=Interval(binary64_bracket(lo)[0],binary64_bracket(hi)[1]); half=t*t/2
        return dict(zip(self.keys,(p+vx*t+self.ax*half,q+vy*t+self.ay*half,
                                     vx+self.ax*t,vy+self.ay*t,heading+self.yaw_rate*t)))

    def footprint(self, box, lo, hi):
        px,py,_,_,heading=(box[k] for k in self.keys)
        z=Interval.point(0)
        return SweptFootprint(StateBounds(px,py,heading,z,z,z),self.geometry,lo,hi,self.actor_id)


def actor_keys(models):
    models=tuple(models)
    if (not all(isinstance(m,ActorEnvelope) for m in models) or
        len({m.actor_id for m in models})!=len(models)):
        raise ValueError('unique declared actor models required')
    return {k for m in models for k in m.keys}


def propagate_other(models, atom, lo, hi):
    if set(atom.other_dict)!=actor_keys(models):
        raise ValueError('actor support incomplete or unexpected coordinates')
    return {k:v for m in models for k,v in m.enclosure(atom.other_dict,lo,hi).items()}
