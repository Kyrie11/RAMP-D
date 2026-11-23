"""A69 joint rational-time reference gate: affine reach + declared Guard snapshots.

The same WORLD/TIME/PUBLIC-CONTROL identity is checked across the two
independently implemented A68 modules. This is a *toy-model* oracle. It does
not execute Native Picard, prove physical occupancy or admit SC/labels.
"""
from __future__ import annotations
from dataclasses import dataclass
from fractions import Fraction as Q
from .a61_hybrid_partition import HybridClockGate
from .a68_affine_slab_replay import AffineSlab, audit_affine_slab_replay
from .a68_guard_resource_monitor import ZoneTick, audit_zone_transitions

@dataclass(frozen=True)
class JointSlab:
    affine: AffineSlab
    zone_at_end: ZoneTick
    def __post_init__(self):
        if not isinstance(self.affine, AffineSlab) or not isinstance(self.zone_at_end, ZoneTick):
            raise TypeError('typed affine and zone snapshots required')


def audit_joint_reference(gate:HybridClockGate, rows:tuple[JointSlab,...], *,
                          initial_occupants:dict[str,tuple[tuple[str,str],...]]|None=None,
                          roster_attested:bool=False,
                          authority_attested:bool=False)->dict:
    if not isinstance(gate,HybridClockGate):raise TypeError('HybridClockGate required')
    rows=tuple(rows)
    if any(not isinstance(r,JointSlab) for r in rows):raise TypeError('JointSlab required')
    if type(roster_attested) is not bool or type(authority_attested) is not bool:
        raise TypeError('attestation flags must be booleans')
    reasons=[]
    aff=audit_affine_slab_replay(gate,tuple(r.affine for r in rows))
    if aff['status']!='CONDITIONAL_EXACT_AFFINE_MODEL_REPLAY_PASS':
        reasons.extend('AFFINE:'+r for r in aff['reasons'])
    expected={(w,lo,hi) for lo,hi,groups in gate.posterior_worlds_by_slab for _,worlds in groups for w in worlds}
    row_map={}; worlds={}
    for r in rows:
        a=r.affine
        key=(a.world_id,a.start,a.end)
        if key in row_map:reasons.append('DUPLICATE_JOINT_WORLD_SLAB')
        row_map[key]=r
        worlds.setdefault(a.world_id,[]).append(r)
        if r.zone_at_end.time!=a.end:reasons.append('GUARD_SNAPSHOT_NOT_AT_SLAB_END:'+a.world_id)
    if set(row_map)!=expected:reasons.append('JOINT_SUPPORT_MISSING_OR_EXTRA')
    if initial_occupants is None:initial_occupants={}
    if type(initial_occupants) is not dict:raise TypeError('initial occupants map required')
    expected_worlds={w for w,_,_ in expected}
    if set(initial_occupants)!=expected_worlds:
        reasons.append('INITIAL_ROSTER_MISSING_OR_EXTRA_WORLD')
    for world,rs in sorted(worlds.items()):
        rs.sort(key=lambda r:r.affine.start)
        if any(a.affine.end!=b.affine.start for a,b in zip(rs,rs[1:])):
            reasons.append('NONCONTIGUOUS_WORLD_ZONE_SLAB:'+world)
        if len(rs)>1:
            dts={r.affine.end-r.affine.start for r in rs}
            if len(dts)>1:reasons.append('NONUNIFORM_ZONE_DT_UNSUPPORTED:'+world)
        if not rs:continue
        dt=rs[0].affine.end-rs[0].affine.start
        z=audit_zone_transitions(tuple(r.zone_at_end for r in rs),dt=dt,
             initial_occupants=initial_occupants.get(world,()),
             actor_roster_attested=roster_attested,
             controller_authority_attested=authority_attested)
        if z['status']!='CONDITIONAL_DECLARED_ZONE_TRANSITIONS_PASS':
            reasons.extend('ZONE:'+world+':'+r for r in z['reasons'])
    # The affine auditor checks within-history control consistency. This joint
    # check also disallows a missing Guard row from silently bypassing it.
    for lo,hi,groups in gate.posterior_worlds_by_slab:
        for history,ids in groups:
            present=[row_map[(w,lo,hi)] for w in ids if (w,lo,hi) in row_map]
            if len(present)!=len(ids):reasons.append('MISSING_PUBLIC_HISTORY_GUARD_ROW')
            if len({r.affine.public_control_id for r in present})>1:
                reasons.append('HIDDEN_WORLD_DEPENDENT_CONTROL')
    reasons=sorted(set(reasons))
    return dict(schema='rampd.a69.joint_affine_guard_reference.v1',
        status=('CONDITIONAL_JOINT_TOY_MODEL_REPLAY_PASS' if not reasons else 'UNKNOWN'),
        reasons=reasons,declared_world_slabs=len(expected),received_world_slabs=len(rows),
        exact_affine_reference_replayed=(aff['status']=='CONDITIONAL_EXACT_AFFINE_MODEL_REPLAY_PASS'),
        declared_guard_state_machine_replayed=(not reasons and len(rows)==len(expected)),
        external_guard_authority_verified=False,continuous_resource_occupancy_verified=False,
        native_mpfr_picard_replayed=False,complete_hidden_protocol_verified=False,
        sc_acceptance_tail_verified=False,safe_training_labels_allowed=False)
