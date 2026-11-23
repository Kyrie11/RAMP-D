"""A68 independent exact-rational affine slab reference checker.

The check is *mathematically sound relative to* x'=v, v'=a with fixed
interval-valued acceleration on each declared slab. It is not the CARLA
vehicle, MPFR/Picard, hidden-world exhaustiveness, resource, or SC verifier.
This reference oracle is intended to catch interval direction, time-slab and
nonanticipativity defects in later native integration.
"""
from __future__ import annotations
from dataclasses import dataclass
from fractions import Fraction as Q
from .a61_hybrid_partition import HybridClockGate

@dataclass(frozen=True)
class QInterval:
    lo: Q
    hi: Q
    def __post_init__(self):
        if type(self.lo) is not Q or type(self.hi) is not Q or self.lo>self.hi:
            raise ValueError('ordered exact rational interval required')
    def covers(self, other: 'QInterval') -> bool:
        return isinstance(other,QInterval) and self.lo<=other.lo and self.hi>=other.hi

@dataclass(frozen=True)
class AffineSlab:
    world_id: str
    start: Q
    end: Q
    public_control_id: str
    x_start: QInterval
    v_start: QInterval
    a_set: QInterval
    x_end: QInterval
    v_end: QInterval
    x_tube: QInterval
    v_tube: QInterval
    def __post_init__(self):
        if not isinstance(self.world_id,str) or not self.world_id or not self.public_control_id:
            raise ValueError('world and public control must be identified')
        if type(self.start) is not Q or type(self.end) is not Q or self.end<=self.start:
            raise ValueError('valid exact rational slab endpoints required')
        if any(not isinstance(getattr(self,k),QInterval) for k in
               ('x_start','v_start','a_set','x_end','v_end','x_tube','v_tube')):
            raise TypeError('typed exact interval fields required')


def analytic_reach(s:AffineSlab) -> tuple[QInterval,QInterval,QInterval,QInterval]:
    """Exact interval supersets over all t in [start,end]. No float rounding.

    Endpoints use monotonicity of x0 + v0*t + a*t**2/2 for FIXED t>=0.
    The whole-tube interval conservatively integrates a velocity hull over
    [0,dt] and therefore covers possible interior turning points as well.
    """
    d=s.end-s.start
    xe=QInterval(s.x_start.lo+s.v_start.lo*d+s.a_set.lo*d*d/2,
                 s.x_start.hi+s.v_start.hi*d+s.a_set.hi*d*d/2)
    ve=QInterval(s.v_start.lo+s.a_set.lo*d,s.v_start.hi+s.a_set.hi*d)
    vt=QInterval(s.v_start.lo+min(Q(0),s.a_set.lo*d),
                 s.v_start.hi+max(Q(0),s.a_set.hi*d))
    xt=QInterval(s.x_start.lo+min(Q(0),vt.lo*d,vt.hi*d),
                 s.x_start.hi+max(Q(0),vt.lo*d,vt.hi*d))
    return xe,ve,xt,vt


def audit_affine_slab_replay(gate:HybridClockGate, rows:tuple[AffineSlab,...]) -> dict:
    if not isinstance(gate,HybridClockGate) or any(not isinstance(r,AffineSlab) for r in rows):
        raise TypeError('typed clock gate and affine slab records required')
    reasons=[]
    if gate.status!='CONDITIONAL_EXACT_MODEL_HYBRID_PARTITION_READY':
        reasons.append('CLOCK_PARTITION_NOT_READY')
    declared=[(s.start,s.end) for s in gate.slabs]
    group_slabs=[(lo,hi) for lo,hi,_ in gate.posterior_worlds_by_slab]
    if not declared or declared!=group_slabs or any(a>=b for a,b in declared) or any(
            a[1]!=b[0] for a,b in zip(declared,declared[1:])):
        reasons.append('CLOCK_SLAB_DECLARATION_INCONSISTENT')
    expected={(w,lo,hi) for lo,hi,groups in gate.posterior_worlds_by_slab
              for _,worlds in groups for w in worlds}
    if not expected:reasons.append('EMPTY_DECLARED_HIDDEN_SUPPORT')
    provided={}
    for r in rows:
        key=(r.world_id,r.start,r.end)
        if key in provided:reasons.append('DUPLICATE_WORLD_SLAB')
        provided[key]=r
        xe,ve,xt,vt=analytic_reach(r)
        for name,calc,declared in (
            ('X_ENDPOINT',xe,r.x_end),('V_ENDPOINT',ve,r.v_end),
            ('X_TUBE',xt,r.x_tube),('V_TUBE',vt,r.v_tube),
            ('X_START_IN_TUBE',r.x_start,r.x_tube),
            ('V_START_IN_TUBE',r.v_start,r.v_tube)):
            if not declared.covers(calc):reasons.append('UNDERAPPROXIMATED_'+name+':'+r.world_id)
    if set(provided)!=expected:reasons.append('INCOMPLETE_OR_EXTRA_WORLD_SLABS')
    for lo,hi,groups in gate.posterior_worlds_by_slab:
        for _,worlds in groups:
            controls={provided[(w,lo,hi)].public_control_id for w in worlds
                      if (w,lo,hi) in provided}
            if len(controls)>1:reasons.append('PUBLIC_NONANTICIPATIVITY_VIOLATION')
    for w in {key[0] for key in provided}:
        chain=sorted((r for r in provided.values() if r.world_id==w),key=lambda x:x.start)
        for a,b in zip(chain,chain[1:]):
            if a.end!=b.start:reasons.append('NONCONTIGUOUS_SLAB_HANDOFF:'+w)
            if not b.x_start.covers(a.x_end):reasons.append('X_HANDOFF_UNDERAPPROXIMATION:'+w)
            if not b.v_start.covers(a.v_end):reasons.append('V_HANDOFF_UNDERAPPROXIMATION:'+w)
    reasons=sorted(set(reasons))
    return dict(schema='rampd.a68.exact_affine_replay.v1',
                status=('CONDITIONAL_EXACT_AFFINE_MODEL_REPLAY_PASS' if not reasons else 'UNKNOWN'),
                reasons=reasons,world_slabs_expected=len(expected),world_slabs_received=len(rows),
                exact_rational_affine_model_replayed=not reasons,
                acceleration_support_physically_justified=False,
                native_mpfr_picard_replayed=False,full_ego_vehicle_certified=False,
                traffic_guard_resource_certified=False,sc_task_tail_certified=False,
                safe_training_labels_allowed=False)
