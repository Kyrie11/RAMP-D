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
