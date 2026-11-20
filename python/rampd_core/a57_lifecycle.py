"""Physical lifecycle slices from explicit mechanism clocks, NOT 511 report rows."""
from dataclasses import dataclass
from fractions import Fraction as Q

@dataclass(frozen=True)
class PhysicalLifecycle:
    event_id:str
    blocked_on:Q
    clear:Q
    reopen:Q
    source_ref:str
    def __post_init__(self):
        if not self.event_id or not self.source_ref or any(type(t) is not Q for t in (self.blocked_on,self.clear,self.reopen)) or not 0<=self.blocked_on<self.clear<=self.reopen:raise ValueError('declared physical lifecycle required')
    def phase(self,t):
        if type(t) is not Q or t<0:raise ValueError('exact clock required')
        return 'PRE_BLOCK' if t<self.blocked_on else 'BLOCKED' if t<self.clear else 'CLEARED_WAIT_AUTHORITY' if t<self.reopen else 'REOPENED'
    def window(self,start,horizon):
        if type(start) is not Q or type(horizon) is not Q or start<0 or horizon<=0:raise ValueError('invalid local window')
        end=start+horizon;points=sorted({start,end,*[t for t in (self.blocked_on,self.clear,self.reopen) if start<t<end]})
        return dict(event_id=self.event_id,source_ref=self.source_ref,start=start,end=end,segments=tuple((a,b,self.phase(a)) for a,b in zip(points,points[1:])),endpoint_phase=self.phase(end),time_scale=Q(1))

def unique_windows(event,starts,horizon):
    """Exact duplicates merged only. Distinct overlapping windows preserved;
    group by source event for train/validation and same event clock in pairs.
    """
    return tuple(event.window(t,horizon) for t in sorted(set(starts)))
