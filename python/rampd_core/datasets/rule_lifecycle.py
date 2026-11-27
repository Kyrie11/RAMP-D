"""Versioned public rule notices, distinct from actual legal/physical state.
Plan updates/cancellations change an actor's public report, not physical clearance.
This adapter does not assert that a real driver received or understood a notice.
"""
from dataclasses import dataclass
from fractions import Fraction as Q
import hashlib,math

@dataclass(frozen=True)
class Notice:
    event_id:str
    authority:str
    version:int
    kind:str
    scope:tuple
    issue:str
    publication:str
    planned_on:str
    planned_off:str
    cancelled:bool=False
    speed_limit_mps:float|None=None
    direction:str|None=None
    def validate(self):
        if not self.event_id or not self.authority or type(self.version) is not int or self.version<1 or not self.scope or len(set(self.scope))!=len(self.scope) or type(self.cancelled) is not bool:raise ValueError('notice identity')
        if not 0<=Q(self.issue)<=Q(self.publication) or not 0<=Q(self.planned_on)<Q(self.planned_off):raise ValueError('notice clocks')
        if self.kind not in ('LANE_CLOSURE','TEMPORARY_SPEED_LIMIT','ALTERNATING_DIRECTION','STOP_SLOW','TURN_RESTRICTION'):raise ValueError('notice type')
        if self.kind=='TEMPORARY_SPEED_LIMIT':
            if self.speed_limit_mps is None or not math.isfinite(self.speed_limit_mps) or self.speed_limit_mps<=0:raise ValueError('speed limit payload')
        elif self.speed_limit_mps is not None:raise ValueError('unexpected speed limit')
        if self.kind in ('ALTERNATING_DIRECTION','STOP_SLOW'):
            if self.direction not in ('A','B','RED'):raise ValueError('direction payload')
        elif self.direction is not None:raise ValueError('unexpected direction')


def public_notices(notices,deliveries,recipient,cutoff):
    """Latest RECEIVED version per authority/event; stale packet cannot undo cancel.
    Delivery roster is the declared ledger, not a claim of actual loss. Only
    reports disclosed in received messages are returned. No actual effectivity/ACK.
    """
    table={};versions={}
    for n in notices:
        n.validate();key=(n.authority,n.event_id,n.version)
        if key in table:raise ValueError('duplicate notice version')
        table[key]=n;versions.setdefault(key[:2],[]).append(n)
    for group in versions.values():
        group.sort(key=lambda n:n.version)
        if any(Q(a.issue)>Q(b.issue) or Q(a.publication)>Q(b.publication) or a.kind!=b.kind for a,b in zip(group,group[1:])):raise ValueError('nonmonotone report versions')
    out={};seen=set()
    for d in deliveries:
        key=(d['authority'],d['event_id'],d['version']);i=d['recipient'];t=d['receipt']
        if key not in table or (key,i) in seen:raise ValueError('unknown or duplicate delivery')
        seen.add((key,i));n=table[key]
        if t is not None and Q(t)<Q(n.publication):raise ValueError('receipt before publication')
        if i!=recipient or t is None or Q(t)>Q(cutoff):continue
        if key[:2] not in out or n.version>out[key[:2]]['version']:
            out[key[:2]]=dict(n.__dict__,receipt=t)
    return [out[k] for k in sorted(out)]


def route_equipped_recipients(projected_ids,ego_id,*,source_digest,other_receipt,ego_receipt,probability=.5,seed=7):
    """Controlled device-availability cohort, stable across interventions.
    Only relevant modeled route actors are eligible; probability is a declared
    experimental factor, NOT an estimate from WOMD or WZDx. No forced recipient.
    """
    if ego_id not in projected_ids or not 0<=probability<=1 or type(seed) is not int:raise ValueError('recipient configuration')
    result={ego_id:ego_receipt}
    for i in sorted(set(projected_ids)-{ego_id}):
        u=int.from_bytes(hashlib.sha256(f'{source_digest}:{seed}:{i}'.encode()).digest()[:8],'big')/2**64
        result[i]=other_receipt if u<probability else None
    return result
