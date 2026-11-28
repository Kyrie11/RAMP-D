"""Reusable two-direction interlock with version-bound signal readback.
No inference of ACK from command or occupancy. Input evidence is trusted only in
its declared adapter domain. Closed-set footprint contact counts as occupancy.
The controller never treats an incomplete roster as empty.
"""
from dataclasses import dataclass
from fractions import Fraction as Q

@dataclass(frozen=True)
class SignalCommand:
    version: int
    direction: str  # A, B, RED

class SharedResourceController:
    def __init__(self, roster, *, clearance_ticks=2, green_ticks=6):
        if not roster or any(d not in ('A','B') for d in roster.values()) or type(clearance_ticks) is not int or clearance_ticks<1 or type(green_ticks) is not int or green_ticks<1:
            raise ValueError('invalid controller configuration')
        self.roster=dict(roster);self.clearance=clearance_ticks;self.green=green_ticks
        self.command=SignalCommand(0,'RED');self.target='A';self.empty=0;self.age=0;self.tick=-1;self.confirmed=False
    def _command(self,direction):
        self.command=SignalCommand(self.command.version+1,direction);self.confirmed=False;self.age=0;self.empty=0
    def step(self, tick, occupancy, *, prior_swept_empty, ack):
        """One tick only. ACK is independently observed command version/direction.
        Occupancy is exact Boolean per actor, or None for unknown. The swept-empty
        assertion covers the entire previous slab, not just its end samples.
        """
        if type(tick) is not int or tick!=self.tick+1:raise ValueError('nonconsecutive controller tick')
        if set(occupancy)!=set(self.roster) or any(x is not None and type(x) is not bool for x in occupancy.values()) or prior_swept_empty is not None and type(prior_swept_empty) is not bool:raise ValueError('incomplete occupancy evidence')
        if ack is not None and (not isinstance(ack,SignalCommand) or type(ack.version) is not int):raise ValueError('invalid ACK')
        self.tick=tick; known=all(v is not None for v in occupancy.values());occ={self.roster[a] for a,v in occupancy.items() if v is True}
        prev_confirmed=self.confirmed; self.confirmed=ack==self.command
        if self.command.direction=='RED':
            # Clearance clock starts only after confirmed all-red. Never credit
            # an interval preceding the first matching readback.
            self.empty=self.empty+1 if tick>0 and prev_confirmed and self.confirmed and known and not occ and prior_swept_empty is True else 0
            if self.empty>=self.clearance:self._command(self.target)
        else:
            d=self.command.direction
            if not known or (occ-{d}):
                self.target=d;self._command('RED')
            elif self.confirmed:
                self.age=self.age+1 if prev_confirmed else 1
                if self.age>self.green:
                    self.target='B' if d=='A' else 'A';self._command('RED')
            else:
                self.age=0
        permit=self.command.direction if self.confirmed and known and self.command.direction in ('A','B') else None
        return dict(command={'version':self.command.version,'direction':self.command.direction},ack=None if ack is None else {'version':ack.version,'direction':ack.direction},permit=permit,empty_ticks=self.empty,green_age=self.age,occupancy_known=known)


def sampled_polygon_occupancy(resource_vertices, footprints, expected_roster, *, tolerance_m=0.):
    """Closed-set sampled geometry adapter, not swept clearance or proof.
    For nonzero map/measurement tolerance, near-boundary cases remain None.
    Supply actual world-coordinate footprints and declared complete roster.
    Missing/invalid geometry must never become free space.
    """
    import math
    from shapely.geometry import Polygon
    if not math.isfinite(tolerance_m) or tolerance_m<0:raise ValueError('geometry tolerance')
    ids=set(expected_roster)
    if not ids or not set(footprints)<=ids:raise ValueError('roster')
    def poly(v):
        if v is None:return None
        try:
            if len(v)<3 or any(len(p)!=2 or not all(math.isfinite(float(x)) for x in p) for p in v):return None
            q=Polygon(v);return q if q.is_valid and q.area>0 else None
        except (TypeError,ValueError):return None
    resource=poly(resource_vertices)
    if resource is None:raise ValueError('invalid resource polygon')
    out={}
    for i in sorted(ids):
        q=poly(footprints.get(i))
        if q is None:out[i]=None;continue
        if tolerance_m==0:out[i]=bool(q.intersects(resource));continue
        # With uncertain boundaries, positive only if footprint intersects
        # eroded resource interior; separated only if outside buffered resource.
        # Assumption: footprint exact and resource uncertainty bounded by these
        # two geometric sets. NOT a general bound for pose/heading error.
        inner=resource.buffer(-tolerance_m);outer=resource.buffer(tolerance_m)
        out[i]=True if not inner.is_empty and q.intersects(inner) else False if not q.intersects(outer) else None
    return dict(occupancy=out,all_known=all(v is not None for v in out.values()),sampled_empty=all(v is False for v in out.values()),prior_swept_empty=None,scope='SAMPLED_GEOMETRY_ONLY_NO_CONTINUOUS_CLEARANCE')
