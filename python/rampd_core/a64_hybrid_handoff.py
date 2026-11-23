"""A59/1b-0J: exact-rational *necessary* interval handoff checks.

This auditor does not call MPFR, validate Picard inclusion, check a Guard,
prove resource nonintersection, or certify a task. It checks only that every
specified hidden world has a handoff on every clock slab and that the NEXT
slab's initial outer box CONTAINS the preceding slab's endpoint outer box.
This is a useful anti-unsoundness gate before attaching real native substeps.
"""
from __future__ import annotations
from dataclasses import dataclass
from fractions import Fraction as Q
from .a61_hybrid_partition import HybridClockGate


@dataclass(frozen=True)
class SlabHandoff:
    world_id: str
    start: Q
    end: Q
    start_outer_box: tuple[tuple[Q,Q],...]
    end_outer_box: tuple[tuple[Q,Q],...]
    native_witness_digest: str = ''

    def __post_init__(self):
        if not isinstance(self.world_id,str) or not self.world_id:
            raise ValueError('world_id required')
        if type(self.start) is not Q or type(self.end) is not Q or self.start>=self.end:
            raise ValueError('exact nonempty time interval required')
        for box in (self.start_outer_box,self.end_outer_box):
            if type(box) is not tuple or not box:
                raise ValueError('nonempty typed state interval box required')
            for pair in box:
                if (type(pair) is not tuple or len(pair)!=2 or
                        type(pair[0]) is not Q or type(pair[1]) is not Q or pair[0]>pair[1]):
                    raise TypeError('exact rational finite state bounds required')
        if len(self.start_outer_box)!=len(self.end_outer_box):
            raise ValueError('start/end state dimension mismatch')
        if not isinstance(self.native_witness_digest,str):
            raise ValueError('witness digest must be a string')


def audit_slab_handoffs(gate:HybridClockGate, entries:tuple[SlabHandoff,...]):
    if not isinstance(gate,HybridClockGate):raise TypeError('exact hybrid clock gate required')
    if any(not isinstance(x,SlabHandoff) for x in entries):
        raise TypeError('typed handoffs required')
    issues=[]
    if gate.status!='CONDITIONAL_EXACT_MODEL_HYBRID_PARTITION_READY':
        issues.append('HYBRID_PARTITION_NOT_READY')
    required={(w,lo,hi) for lo,hi,groups in gate.posterior_worlds_by_slab
              for _,worlds in groups for w in worlds}
    table={}
    for item in entries:
        k=(item.world_id,item.start,item.end)
        if k in table:issues.append('DUPLICATE_SLAB:'+str(k))
        if k not in required:issues.append('UNEXPECTED_SLAB:'+str(k))
        table[k]=item
    for k in required-set(table):issues.append('MISSING_SLAB:'+str(k))
    worlds={w for w,_,_ in required}
    for w in worlds:
        chain=sorted((x for x in entries if x.world_id==w),key=lambda x:(x.start,x.end))
        for prev,nxt in zip(chain,chain[1:]):
            if prev.end!=nxt.start:
                issues.append('NONCONTIGUOUS_WORLD_TIME:'+w)
                continue
            if len(prev.end_outer_box)!=len(nxt.start_outer_box):
                issues.append('STATE_DIMENSION_CHANGED:'+w)
                continue
            for i,((prev_low,prev_high),(next_low,next_high)) in enumerate(
                    zip(prev.end_outer_box,nxt.start_outer_box)):
                if next_low>prev_low or next_high<prev_high:
                    issues.append(f'ENDPOINT_NOT_ENCLOSED_BY_NEXT_START:{w}:state_{i}')
    # Complete time/interval bookkeeping is *not* a validation of the
    # numerical intervals. A caller could fabricate arbitrarily small boxes.
    return {'status':'CONDITIONAL_RATIONAL_SLAB_HANDOFFS_CONSISTENT_NOT_CERTIFIED'
             if not issues else 'UNKNOWN',
            'reasons':sorted(set(issues)),
            'declared_world_slab_count':len(entries),'expected_world_slab_count':len(required),
            'native_picard_replayed':False,'complete_protocol_replayed':False,
            'safety_certified':False,'sc_certified':False,
            'training_viability_labels_allowed':False}
