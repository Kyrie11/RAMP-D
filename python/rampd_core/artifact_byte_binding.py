"""A67 byte-authenticated, context-bound artifact inventory (not proof replay).

Previous A66 only compared *declared strings*. Here we recompute SHA256 over
supplied bytes, reject duplicated JSON keys, and validate exact world/time/
control/role. The content's mathematical claims are still entirely UNVERIFIED.
"""
from __future__ import annotations
from fractions import Fraction as Q
from hashlib import sha256
import json
from .a66_hybrid_contract_binding import audit_hybrid_artifact_binding

_ROLES = ('native_tube','guard','resource','observation')
_DIGEST_FIELDS = ('native_tube_digest_sha256','guard_digest_sha256',
                  'resource_digest_sha256','observation_digest_sha256')


def _unique_pairs(pairs):
    d={}
    for key, value in pairs:
        if key in d:raise ValueError('DUPLICATE_JSON_KEY:'+key)
        d[key]=value
    return d


def _strict_json(data):
    if not isinstance(data, bytes):raise TypeError('RAW_ARTIFACT_BYTES_REQUIRED')
    return json.loads(data.decode('utf8'),object_pairs_hook=_unique_pairs,
                      parse_constant=lambda x: (_ for _ in ()).throw(ValueError('INVALID_NUMBER:'+x)))


def audit_payload_bytes(gate,ledger,handoffs,bindings,*,
                        protocol_bytes:bytes|None,
                        role_bytes:dict|None) -> dict:
    """role_bytes[(world_id, Fraction(start), Fraction(end), role)] = raw bytes.

    A referenced native proof is NOT replayed here; the producer is not a
    trusted teacher. Only exact-byte context identity and hash declarations
    are checked. A binding PASS cannot certify feasibility or train labels.
    """
    base = audit_hybrid_artifact_binding(gate,ledger,handoffs,bindings)
    reasons=list(base['reasons'])
    if reasons:reasons.append('DECLARED_BINDING_GATE_FAILED')
    expected={}
    for b in bindings:
        for role,field in zip(_ROLES,_DIGEST_FIELDS):
            expected[(b.world_id,b.start,b.end,role)]=(getattr(b,field),b.public_control_id)
    if not isinstance(role_bytes,dict):
        role_bytes={};reasons.append('MISSING_ARTIFACT_BYTES_MAP')
    if set(role_bytes)!=set(expected):
        reasons.append('MISSING_OR_EXTRA_ARTIFACT_BYTES')
    valid=0
    for key,(digest,control) in expected.items():
        raw=role_bytes.get(key)
        if raw is None:
            reasons.append('MISSING_ARTIFACT_BYTES:'+str(key));continue
        try:
            record=_strict_json(raw)
            if not isinstance(record,dict):raise ValueError('NONOBJECT_ARTIFACT')
            world,lo,hi,role=key
            if (record.get('schema')!='rampd.a67.context_artifact.v1' or
                    record.get('role')!=role or record.get('world_id')!=world or
                    record.get('start')!=str(lo) or record.get('end')!=str(hi) or
                    record.get('public_control_id')!=control or
                    type(record.get('body')) is not dict):
                raise ValueError('ROLE_WORLD_TIME_CONTROL_CONTEXT_MISMATCH')
            if sha256(raw).hexdigest()!=digest:
                raise ValueError('DECLARED_SHA256_NOT_ACTUAL_BYTES_SHA256')
            valid+=1
        except (ValueError,TypeError,UnicodeError) as exc:
            reasons.append('INVALID_ARTIFACT_BYTES:'+str(key)+':'+str(exc))
    protocol_valid=False
    if not isinstance(protocol_bytes,bytes):
        reasons.append('MISSING_PROTOCOL_BYTES')
    else:
        try:
            p=_strict_json(protocol_bytes)
            if not isinstance(p,dict) or p.get('schema')!='rampd.a67.protocol_contract.v1' or not isinstance(p.get('contract_id'),str) or not p['contract_id']:
                raise ValueError('INVALID_PROTOCOL_CONTENT')
            digest=sha256(protocol_bytes).hexdigest()
            if not bindings or any(b.protocol_digest_sha256!=digest for b in bindings):
                raise ValueError('PROTOCOL_BYTES_SHA256_MISMATCH')
            protocol_valid=True
        except (ValueError,TypeError,UnicodeError) as exc:
            reasons.append('INVALID_PROTOCOL_BYTES:'+str(exc))
    reasons=sorted(set(reasons))
    return dict(schema='rampd.a67.artifact_byte_gate.v1',
                status=('CONDITIONAL_CONTEXT_BYTES_BOUND_NOT_REPLAYED' if not reasons else 'UNKNOWN'),
                reasons=reasons,expected_role_artifacts=len(expected),verified_role_artifacts=valid,
                protocol_bytes_hash_verified=protocol_valid,
                all_declared_artifact_hashes_verified=not reasons,
                native_picard_replayed=False,guard_authority_replayed=False,
                continuous_resource_geometry_replayed=False,public_observation_replayed=False,
                full_protocol_support_certified=False,goal_tail_replayed=False,
                sc_certified=False,all_eight_training_labels_certified=False)
