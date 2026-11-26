"""A69 scenario-grouped source lineage and isolation gate.

Evidence bytes and schema/role are checked. Splits are keyed by scenario,
not file names; no certified supervision values are produced by this gate.
"""
from __future__ import annotations
from dataclasses import dataclass
from hashlib import sha256
import json
from .a68_supervision_release import LABELS,AUX_ROLES,FORMAL_ROLES

@dataclass(frozen=True)
class EvidenceRow:
    sample_id: str
    scenario_id: str
    split: str
    label: str
    role: str
    domain: str
    raw: bytes
    declared_sha256: str
    def __post_init__(self):
        if any(type(getattr(self,k)) is not str or not getattr(self,k)
               for k in ('sample_id','scenario_id','split','label','role','domain','declared_sha256')):
            raise ValueError('nonempty typed evidence identity required')
        if type(self.raw) is not bytes:raise TypeError('byte-stream required')


def _pairs(items):
    obj={}
    for k,v in items:
        if k in obj:raise ValueError('DUPLICATE_JSON_KEY')
        obj[k]=v
    return obj


def audit_lineage(rows:tuple[EvidenceRow,...], *,
                  permitted_splits=('train','validation','test')) ->dict:
    rows=tuple(rows)
    if any(not isinstance(x,EvidenceRow) for x in rows):raise TypeError('EvidenceRow required')
    reasons=[];scenarios={};samples={};files={};seen=set();accepted=[]
    if not rows:reasons.append('NO_EVIDENCE')
    for r in rows:
        if r.label not in LABELS:reasons.append('UNKNOWN_LABEL:'+r.label)
        if r.split not in permitted_splits:reasons.append('INVALID_SPLIT:'+r.split)
        if r.sample_id in samples and samples[r.sample_id]!=r.scenario_id:
            reasons.append('SAMPLE_REASSIGNED_TO_DIFFERENT_SCENARIO')
        samples[r.sample_id]=r.scenario_id
        if r.scenario_id in scenarios and scenarios[r.scenario_id]!=r.split:
            reasons.append('SCENARIO_LEAKED_ACROSS_SPLITS:'+r.scenario_id)
        scenarios[r.scenario_id]=r.split
        if (r.sample_id,r.label,r.role) in seen:
            reasons.append('DUPLICATE_SAMPLE_LABEL_ROLE')
        seen.add((r.sample_id,r.label,r.role))
        if r.label in FORMAL_ROLES:
            reasons.append('FORMAL_PROOF_REPLAY_ABSENT:'+r.label)
        if r.label=='L_causal':
            reasons.append('PAIRED_EXOGENOUS_INTERVENTIONS_UNVERIFIED')
        if r.role not in (AUX_ROLES.get(r.label,set()) | FORMAL_ROLES.get(r.label,set())):
            reasons.append('ROLE_MISMATCH:'+r.label)
        digest=sha256(r.raw).hexdigest()
        if digest!=r.declared_sha256:reasons.append('SOURCE_HASH_MISMATCH:'+r.sample_id)
        if digest in files and files[digest]!=(r.scenario_id,r.split,r.domain):
            reasons.append('SAME_RAW_BYTES_REASSIGNED_TO_OTHER_DOMAIN_OR_SPLIT')
        files[digest]=(r.scenario_id,r.split,r.domain)
        try:
            obj=json.loads(r.raw.decode('utf8'),object_pairs_hook=_pairs,
                 parse_constant=lambda s: (_ for _ in ()).throw(ValueError('NONFINITE_JSON')))
            if type(obj) is not dict:
                raise ValueError('NONOBJECT_EVIDENCE')
            if obj.get('scenario_id')!=r.scenario_id or obj.get('domain')!=r.domain:
                raise ValueError('EVIDENCE_INTERNAL_PROVENANCE_MISMATCH')
            if obj.get('source_role')!=r.role:
                raise ValueError('EVIDENCE_INTERNAL_ROLE_MISMATCH')
            if not isinstance(obj.get('event_or_sample_time'),(int,float,str)) or isinstance(obj.get('event_or_sample_time'),bool):
                raise ValueError('MISSING_SOURCE_TIME_PROVENANCE')
        except (TypeError,ValueError,UnicodeError) as exc:
            reasons.append('INVALID_SOURCE_JSON:'+r.sample_id+':'+str(exc))
        accepted.append(dict(sample_id=r.sample_id,scenario_id=r.scenario_id,
                             split=r.split,label=r.label,role=r.role,domain=r.domain,sha256=digest))
    reasons=sorted(set(reasons))
    return dict(schema='rampd.a69.scenario_source_lineage.v1',
         status=('CONDITIONAL_AUXILIARY_LINEAGE_INVENTORY_PASS' if not reasons else 'REVIEW'),
         reasons=reasons,rows=accepted,distinct_scenarios=len(scenarios),
         formal_label_masks={x:0 for x in LABELS},
         causal_pairing_verified=False,independent_teacher_replayed=False,
         source_bytes_prove_physical_claims=False,safe_training_labels_allowed=False)
