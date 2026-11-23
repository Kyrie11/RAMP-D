"""A66: cross-artifact, world/time/protocol binding for pending hybrid proofs.

Checks identities and SHA-256 *declarations*, NOT whether referenced bytes exist,
not hashes independently, not Picard inclusions, and never awards an SC label.
Keeping exact worlds and clocks aligned prevents cross-world proof substitution.
"""
from __future__ import annotations
from dataclasses import dataclass
from fractions import Fraction as Q
from .a61_hybrid_partition import HybridClockGate
from .a62_hybrid_obligation_ledger import WorldSlabEvidence, audit_world_slab_ledger
from .a64_hybrid_handoff import SlabHandoff, audit_slab_handoffs


def _sha(s):
    return isinstance(s,str) and len(s)==64 and all(c in '0123456789abcdef' for c in s)

@dataclass(frozen=True)
class WorldSlabBinding:
    world_id: str
    start: Q
    end: Q
    public_control_id: str
    protocol_digest_sha256: str
    native_tube_digest_sha256: str
    guard_digest_sha256: str
    resource_digest_sha256: str
    observation_digest_sha256: str

    def __post_init__(self):
        if not self.world_id or type(self.start) is not Q or type(self.end) is not Q or not self.start<self.end:
            raise ValueError('exact world/time identity required')
        if not self.public_control_id or not isinstance(self.public_control_id,str):
            raise ValueError('public control identity required')
        for field in ('protocol_digest_sha256','native_tube_digest_sha256','guard_digest_sha256',
                      'resource_digest_sha256','observation_digest_sha256'):
            if not _sha(getattr(self,field)):
                raise ValueError('lowercase SHA256 digest declaration required: '+field)


def audit_hybrid_artifact_binding(gate: HybridClockGate,
                                   ledger: tuple[WorldSlabEvidence,...],
                                   handoffs: tuple[SlabHandoff,...],
                                   bindings: tuple[WorldSlabBinding,...]) -> dict:
    """Necessary bookkeeping check with rigid artifact role binding.

    Even a PASS must be followed by independent native/resource/guard/observer
    artifact *replay* before being used for mathematical safety certificates.
    """
    if not isinstance(gate,HybridClockGate):
        raise TypeError('typed clock partition required')
    ledger=tuple(ledger);handoffs=tuple(handoffs);bindings=tuple(bindings)
    if any(not isinstance(x,WorldSlabBinding) for x in bindings):
        raise TypeError('typed binding required')
    l=audit_world_slab_ledger(gate,ledger)
    h=audit_slab_handoffs(gate,handoffs)
    reasons=[]
    if l['reasons']:reasons.append('LEDGER_INTEGRITY_FAILED')
    if h['reasons']:reasons.append('HANDOFF_INTEGRITY_FAILED')
    if gate.status!='CONDITIONAL_EXACT_MODEL_HYBRID_PARTITION_READY':
        reasons.append('CLOCK_PARTITION_UNRESOLVED')
    req={(w,lo,hi) for lo,hi,groups in gate.posterior_worlds_by_slab
         for _,ids in groups for w in ids}
    bd={};ld={};hd={}
    for row in bindings:
        k=(row.world_id,row.start,row.end)
        if k in bd:reasons.append('DUPLICATE_BINDING')
        if k not in req:reasons.append('UNEXPECTED_BINDING')
        bd[k]=row
    for row in ledger:
        k=(row.world_id,row.start,row.end)
        if k in ld:reasons.append('DUPLICATE_LEDGER_ID')
        ld[k]=row
    for row in handoffs:
        k=(row.world_id,row.start,row.end)
        if k in hd:reasons.append('DUPLICATE_HANDOFF_ID')
        hd[k]=row
    if set(bd)!=req:reasons.append('MISSING_OR_EXTRA_WORLD_TIME_BINDINGS')
    if set(ld)!=req or set(hd)!=req:reasons.append('LEDGER_OR_HANDOFF_SUPPORT_INCOMPLETE')
    protocols=set()
    for k in req.intersection(bd).intersection(ld).intersection(hd):
        b=bd[k];r=ld[k];n=hd[k];protocols.add(b.protocol_digest_sha256)
        if b.public_control_id!=r.public_control_id:
            reasons.append('CONTROL_ID_MISMATCH:'+b.world_id)
        if (b.native_tube_digest_sha256!=r.native_tube_ref or
                b.native_tube_digest_sha256!=n.native_witness_digest):
            reasons.append('NATIVE_TUBE_CROSS_ARTIFACT_MISMATCH:'+b.world_id)
        if b.guard_digest_sha256!=r.guard_snapshot_ref:
            reasons.append('GUARD_CROSS_ARTIFACT_MISMATCH:'+b.world_id)
        if b.resource_digest_sha256!=r.resource_audit_ref:
            reasons.append('RESOURCE_CROSS_ARTIFACT_MISMATCH:'+b.world_id)
        if b.observation_digest_sha256!=r.observation_update_ref:
            reasons.append('OBSERVATION_CROSS_ARTIFACT_MISMATCH:'+b.world_id)
    if len(protocols)>1:
        reasons.append('PROTOCOL_CONTRACT_CHANGED_INSIDE_DECLARED_SUPPORT')
    for lo,hi,groups in gate.posterior_worlds_by_slab:
        for history,worlds in groups:
            controls={bd[(w,lo,hi)].public_control_id for w in worlds if (w,lo,hi) in bd}
            if len(controls)>1:reasons.append('NONANTICIPATIVE_CONTROL_BINDING_MISMATCH')
    reasons=sorted(set(reasons))
    return dict(schema='rampd.a66.hybrid_binding.v1',
                status='CONDITIONAL_ARTIFACT_IDENTITY_ALIGNED_NOT_CERTIFIED' if not reasons else 'UNKNOWN',
                reasons=reasons,expected_world_slabs=len(req),binding_count=len(bindings),
                unclosed_independent_replay_obligations=l['unclosed_obligations'],
                digest_bytes_independently_recomputed=False,
                real_native_picard_replayed=False,guard_and_resources_replayed=False,
                full_protocol_support_certified=False,terminal_policy_replayed=False,
                safety_certified=False,supervised_viability_margin_deadline_allowed=False)
