"""A68 honest eight-loss source release gate (auxiliary != safety supervision).

A file hash proves unchanged bytes, not a physical event, a native proof or
causality. No safety label is minted merely from a source's self-assertions.
The authority to release certified labels requires future independent proof
replay; this stage ONLY releases explicitly marked AUXILIARY data.
"""
from __future__ import annotations
from dataclasses import dataclass
from hashlib import sha256
import json

LABELS=('L_event','L_joint','L_occupancy','L_observation',
        'L_viability','L_margin','L_deadline','L_causal')
AUX_ROLES={'L_event':{'SIMULATED_EVENT_LOG'},
           'L_joint':{'FACTUAL_TRACK_LOG'},
           'L_occupancy':{'SAMPLED_FOOTPRINT_LOG'},
           'L_observation':{'SENSOR_RECEIPT_LOG'},
           'L_causal':{'DECLARED_PAIRED_INTERVENTION_LOG'}}
FORMAL_ROLES={'L_viability':{'COMPLETE_SC_ORACLE_PROOF'},
              'L_margin':{'REPLAYED_NATIVE_TUBE_PROOF'},
              'L_deadline':{'REPLAYED_PROTOCOL_TIME_PROOF'}}

@dataclass(frozen=True)
class SourceClaim:
    label: str
    role: str
    raw_bytes: bytes
    claimed_sha256: str
    offered_value: object = None
    def __post_init__(self):
        if self.label not in LABELS or not isinstance(self.role,str) or type(self.raw_bytes) is not bytes:
            raise ValueError('typed known label and raw evidence required')
        if not isinstance(self.claimed_sha256,str) or len(self.claimed_sha256)!=64:
            raise ValueError('exact SHA256 needed')


def _unique(pairs):
    out={}
    for k,v in pairs:
        if k in out:raise ValueError('duplicate JSON key')
        out[k]=v
    return out


def review_supervision_sources(claims:tuple[SourceClaim,...]) -> dict:
    """Return only auxiliary evidence metadata; all formal safety masks are 0."""
    if any(not isinstance(c,SourceClaim) for c in claims):raise TypeError('SourceClaim required')
    rows={};issues=[]
    for c in claims:
        if c.label in rows:
            issues.append('DUPLICATED_LABEL_SOURCE:'+c.label);continue
        reasons=[]
        if sha256(c.raw_bytes).hexdigest()!=c.claimed_sha256:reasons.append('SOURCE_BYTES_SHA256_MISMATCH')
        try:
            obj=json.loads(c.raw_bytes.decode('utf8'),object_pairs_hook=_unique,
                parse_constant=lambda x: (_ for _ in ()).throw(ValueError('nonfinite JSON')))
            if type(obj) is not dict:reasons.append('SOURCE_NOT_JSON_OBJECT')
        except (TypeError,ValueError,UnicodeError):reasons.append('SOURCE_JSON_UNREADABLE_OR_NONCANONICAL')
        allowed=AUX_ROLES.get(c.label,set())|FORMAL_ROLES.get(c.label,set())
        if c.role not in allowed:reasons.append('SOURCE_ROLE_NOT_ALLOWED_FOR_LOSS')
        if c.label in FORMAL_ROLES:
            reasons.append('INDEPENDENT_M1_M12_PROOF_REPLAY_NOT_AVAILABLE')
        if c.label=='L_causal':
            reasons.append('PAIRING_AND_EXOGENOUS_STATE_NOT_INDEPENDENTLY_VERIFIED')
        if c.offered_value is not None:
            reasons.append('RAW_VALUE_OFFERED_WITHOUT_INDEPENDENT_LABEL_CONSTRUCTION')
        rows[c.label]=dict(status='REVIEW' if reasons else 'AUXILIARY_SOURCE_BYTES_VERIFIED_ONLY',
                           reasons=sorted(set(reasons)),source_role=c.role,sha256=c.claimed_sha256,
                           formal_label_mask=0,auxiliary_only=(not reasons),
                           training_label_value=None)
    for label in LABELS:
        if label not in rows:
            rows[label]=dict(status='MISSING',reasons=['NO_SOURCE'],formal_label_mask=0,
                             auxiliary_only=False,training_label_value=None)
    issues=sorted(set(issues))
    return dict(schema='rampd.a68.eight_supervision_source_gate.v1',
                status='EVIDENCE_INVENTORY_ONLY_NO_FORMAL_LABELS' if not issues else 'REVIEW',
                reasons=issues,labels=rows,formal_masks={k:0 for k in LABELS},
                all_eight_formal_supervision_available=False,
                no_unknown_converted_to_negative=True,
                proof_replay_completed=False)
