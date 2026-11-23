"""A59/1b-0H: complete audit *obligation inventory*, not a safety verifier.

A valid table means every declared hidden-world/time-slab pair is present and
pre-observation controls are nonanticipative. Explicit native/resource/guard
references are pointers to proof obligations, NOT self-authenticating proofs.
Every result is deliberately non-certifying.
"""
from __future__ import annotations
from dataclasses import dataclass
from fractions import Fraction as Q
from .a61_hybrid_partition import HybridClockGate


@dataclass(frozen=True)
class WorldSlabEvidence:
    world_id: str
    start: Q
    end: Q
    public_control_id: str
    native_tube_ref: str = ''
    guard_snapshot_ref: str = ''
    resource_audit_ref: str = ''
    observation_update_ref: str = ''
    tube_replayed: bool = False
    guard_authority_replayed: bool = False
    resource_topology_replayed: bool = False
    observation_support_replayed: bool = False
    task_tail_replayed: bool = False

    def __post_init__(self):
        if not self.world_id or type(self.start) is not Q or type(self.end) is not Q or self.start>=self.end:
            raise ValueError('typed exact world/time slab required')
        if not isinstance(self.public_control_id,str) or not self.public_control_id:
            raise ValueError('explicit control identity required')
        for key in ('tube_replayed','guard_authority_replayed','resource_topology_replayed',
                    'observation_support_replayed','task_tail_replayed'):
            if type(getattr(self,key)) is not bool:raise TypeError('boolean evidence flags only')


def audit_world_slab_ledger(gate: HybridClockGate, rows: tuple[WorldSlabEvidence,...]):
    """Conservative join of exact event partition and declared physical records.

    The check neither dereferences native proof references nor validates
    continuous reachable tubes; never produce CERTIFIED or supervised labels.
    """
    if not isinstance(gate,HybridClockGate):raise TypeError('typed exact partition required')
    rows=tuple(rows)
    if any(not isinstance(row,WorldSlabEvidence) for row in rows):
        raise TypeError('typed per-world per-slab evidence required')
    reasons=[];open_obligations=[]
    if gate.status!='CONDITIONAL_EXACT_MODEL_HYBRID_PARTITION_READY':
        reasons.append('PARTITION_NOT_READY')
    expected=set()
    for lo,hi,groups in gate.posterior_worlds_by_slab:
        for hist,ids in groups:
            expected.update((world_id,lo,hi) for world_id in ids)
    table={}
    for r in rows:
        k=(r.world_id,r.start,r.end)
        if k in table:reasons.append('DUPLICATE_WORLD_SLAB:'+r.world_id)
        table[k]=r
        if k not in expected:reasons.append('EXTRANEOUS_OR_WRONG_TIME_WORLD_SLAB:'+r.world_id)
        for name in ('native_tube_ref','guard_snapshot_ref','resource_audit_ref','observation_update_ref'):
            if not isinstance(getattr(r,name),str) or not getattr(r,name):
                open_obligations.append('MISSING_'+name.upper()+':'+r.world_id)
        for label,field in (
            ('M1_NATIVE_PICARD_PROOF_REPLAY','tube_replayed'),
            ('M2_M6_M7_RULE_AUTHORITY_AND_ACK','guard_authority_replayed'),
            ('M5_M6_RESOURCE_TOPOLOGY_SWEEP','resource_topology_replayed'),
            ('M8_M9_FULL_PUBLIC_OBSERVATION_SUPPORT','observation_support_replayed'),
            ('M10_ACCEPTING_TASK_TAIL','task_tail_replayed')):
            if not getattr(r,field):open_obligations.append(label+':'+r.world_id)
    for world_id,lo,hi in expected-set(table):
        reasons.append('MISSING_WORLD_SLAB:'+world_id+':'+str(lo)+':'+str(hi))
    for lo,hi,groups in gate.posterior_worlds_by_slab:
        for history,worlds in groups:
            controls={table[(w,lo,hi)].public_control_id for w in worlds if (w,lo,hi) in table}
            if len(controls)>1:
                reasons.append('NONANTICIPATIVE_PUBLIC_CONTROL_VIOLATION:'+str(lo)+':'+str(hi))
    # Table completeness and replay verification are independent; both must
    # later hold along with terminal acceptance for real SC certification.
    return {'status':'CONDITIONAL_COMPLETE_WORLD_SLAB_OBLIGATION_TABLE_NOT_CERTIFIED'
            if not reasons and not open_obligations else 'UNKNOWN',
            'reasons':sorted(set(reasons)),
            'unclosed_obligations':sorted(set(open_obligations)),
            'rows_received':len(rows),'world_slabs_required':len(expected),
            'all_replays_independently_authenticated':False,
            'sc_certified':False,'label_viability_allowed':False,
            'label_deadline_allowed':False,'label_margin_allowed':False}
