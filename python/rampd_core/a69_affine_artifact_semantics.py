"""A69 semantic replay of a *toy affine* Native-role JSON payload.

A67 bound only bytes and context; this checker reconstructs exact rational
intervals from independently serialized payloads and checks the actual affine
reach equations, as an intentionally small mathematical test oracle.

It is NOT an MPFR/Picard or general-bicycle Native certificate replayer.
"""
from __future__ import annotations
from fractions import Fraction as Q
import hashlib,json,re
from .a61_hybrid_partition import HybridClockGate
from .a66_hybrid_contract_binding import WorldSlabBinding
from .a68_affine_slab_replay import QInterval,AffineSlab,audit_affine_slab_replay

_RATIONAL=re.compile(r'-?(?:0|[1-9][0-9]*)(?:/[1-9][0-9]*)?\Z')

def _q(value):
    if type(value) is not str or not _RATIONAL.fullmatch(value):
        raise ValueError('EXACT_CANONICAL_RATIONAL_STRING_REQUIRED')
    return Q(value)

def _iv(obj):
    if type(obj) is not list or len(obj)!=2:
        raise ValueError('TWO_EXACT_RATIONAL_INTERVAL_ENDPOINTS_REQUIRED')
    return QInterval(_q(obj[0]),_q(obj[1]))

def _unique(pairs):
    out={}
    for k,v in pairs:
        if k in out:raise ValueError('DUPLICATE_JSON_KEY')
        out[k]=v
    return out

def audit_affine_native_artifact_semantics(gate:HybridClockGate,
        bindings:tuple[WorldSlabBinding,...],raw_native:dict,*,protocol_bytes:bytes|None)->dict:
    if not isinstance(gate,HybridClockGate):raise TypeError('gate required')
    if any(not isinstance(x,WorldSlabBinding) for x in bindings):
        raise TypeError('WorldSlabBinding required')
    if type(raw_native) is not dict:raise TypeError('native artifact bytes map required')
    expected={(b.world_id,b.start,b.end):b for b in bindings}
    reasons=[];slabs=[]
    # The protocol itself must be byte-bound to all world/clock artifacts;
    # A digest string without the referenced raw contract is insufficient.
    if type(protocol_bytes) is not bytes:
        reasons.append('MISSING_RAW_PROTOCOL_CONTRACT_BYTES')
    else:
        try:
            p=json.loads(protocol_bytes.decode('utf8'),object_pairs_hook=_unique,
                parse_constant=lambda x: (_ for _ in ()).throw(ValueError('NONFINITE_JSON')))
            if type(p) is not dict or p.get('schema')!='rampd.a67.protocol_contract.v1' or \
               not isinstance(p.get('contract_id'),str) or not p['contract_id'] or \
               p.get('semantic_model')!='exact_affine_xdot_v_vdot_a_v1':
                raise ValueError('UNSUPPORTED_PROTOCOL_SEMANTIC_MODEL')
            contract_digest=hashlib.sha256(protocol_bytes).hexdigest()
            if not bindings or any(b.protocol_digest_sha256!=contract_digest for b in bindings):
                raise ValueError('RAW_PROTOCOL_DIGEST_MISMATCH')
        except (TypeError,ValueError,UnicodeError) as exc:
            reasons.append('INVALID_RAW_PROTOCOL_BYTES:'+str(exc))
    required={(w,lo,hi) for lo,hi,groups in gate.posterior_worlds_by_slab
              for _,ids in groups for w in ids}
    if len(expected)!=len(bindings) or set(expected)!=required or set(raw_native)!=required:
        reasons.append('INCOMPLETE_OR_DUPLICATE_NATIVE_ROLE_EVIDENCE')
    for key,b in expected.items():
        raw=raw_native.get(key)
        if type(raw) is not bytes:
            reasons.append('MISSING_NATIVE_ROLE_BYTES:'+str(key));continue
        if hashlib.sha256(raw).hexdigest()!=b.native_tube_digest_sha256:
            reasons.append('NATIVE_ROLE_BYTES_HASH_MISMATCH:'+str(key));continue
        try:
            record=json.loads(raw.decode('utf8'),object_pairs_hook=_unique,
                parse_constant=lambda x: (_ for _ in ()).throw(ValueError('NONFINITE_JSON')))
            w,lo,hi=key
            if type(record) is not dict or record.get('schema')!='rampd.a67.context_artifact.v1' or \
                record.get('role')!='native_tube' or record.get('world_id')!=w or \
                record.get('start')!=str(lo) or record.get('end')!=str(hi) or \
                record.get('public_control_id')!=b.public_control_id:
                raise ValueError('NATIVE_WORLD_TIME_CONTROL_CONTEXT_INVALID')
            body=record.get('body')
            if type(body) is not dict or body.get('model')!='exact_affine_xdot_v_vdot_a_v1':
                raise ValueError('UNSUPPORTED_NATIVE_ROLE_SEMANTIC_MODEL')
            slabs.append(AffineSlab(w,lo,hi,b.public_control_id,
                _iv(body.get('x_start')),_iv(body.get('v_start')),_iv(body.get('a_set')),
                _iv(body.get('x_end')),_iv(body.get('v_end')),
                _iv(body.get('x_tube')),_iv(body.get('v_tube'))))
        except (TypeError,ValueError,UnicodeError,KeyError) as exc:
            reasons.append('INVALID_AFFINE_ROLE_BODY:'+str(key)+':'+str(exc))
    reference=audit_affine_slab_replay(gate,tuple(slabs))
    if reference['status']!='CONDITIONAL_EXACT_AFFINE_MODEL_REPLAY_PASS':
        reasons.extend('REPLAY:'+r for r in reference['reasons'])
    reasons=sorted(set(reasons))
    return dict(schema='rampd.a69.exact_affine_artifact_semantic_replay.v1',
        status=('CONDITIONAL_TOY_AFFINE_ARTIFACT_SEMANTICS_REPLAYED' if not reasons else 'UNKNOWN'),
        reasons=reasons,expected_world_slabs=len(required),decoded_world_slabs=len(slabs),
        exact_affine_semantics_replayed=(not reasons),
        mpfr_picard_native_proof_replayed=False,guard_authority_replayed=False,
        complete_protocol_support_replayed=False,sc_certified=False,
        safe_training_labels_allowed=False)
