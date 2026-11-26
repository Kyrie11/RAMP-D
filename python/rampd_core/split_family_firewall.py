"""A70 lineage-family split firewall and evidence-tier inventory.

A scenario_id alone can be renamed. All derivatives of a physical recording,
including alternative interventions and annotation versions, must share the
same split. This is an additional *necessary* source-hygiene test, not a proof
of physical observations or permission to mint formal supervision labels.
"""
from __future__ import annotations
from hashlib import sha256
import json
from .supervision_provenance import EvidenceRow,audit_lineage,_pairs
from .a68_supervision_release import LABELS


def audit_recording_families(rows:tuple[EvidenceRow,...])->dict:
    rows=tuple(rows)
    base=audit_lineage(rows)
    reasons=list(base['reasons']);by_family={};by_causal={};summary=[]
    for r in rows:
        try:
            doc=json.loads(r.raw.decode('utf8'),object_pairs_hook=_pairs,
                parse_constant=lambda x: (_ for _ in ()).throw(ValueError('NONFINITE_JSON')))
            if type(doc) is not dict:raise ValueError('NONOBJECT')
            root=doc.get('root_scenario_id');recording=doc.get('recording_family_id');dataset=doc.get('dataset_id')
            if any(type(v) is not str or not v for v in (root,recording,dataset)):
                raise ValueError('MISSING_CANONICAL_RECORDING_FAMILY_IDENTITY')
            fam=(dataset,root,recording)
            if fam in by_family and by_family[fam]!=r.split:
                reasons.append('RECORDING_FAMILY_SPLIT_LEAK:'+':'.join(fam))
            by_family[fam]=r.split
            # An intervention is not a new independent recording; the same
            # exogenous seed/counterfactual base must stay in one split.
            exog=doc.get('exogenous_realization_id')
            if exog is not None:
                if type(exog) is not str or not exog:
                    raise ValueError('INVALID_EXOGENOUS_REALIZATION_ID')
                pair=(dataset,root,recording,exog)
                if pair in by_causal and by_causal[pair]!=r.split:
                    reasons.append('CAUSAL_EXOGENOUS_PAIR_LEAK:'+':'.join(pair))
                by_causal[pair]=r.split
            summary.append(dict(sample_id=r.sample_id,declared_scenario=r.scenario_id,
                family_id=list(fam),split=r.split,sha256=sha256(r.raw).hexdigest()))
        except (TypeError,ValueError,UnicodeError) as exc:
            reasons.append('INVALID_FAMILY_EVIDENCE:'+r.sample_id+':'+str(exc))
    reasons=sorted(set(reasons))
    return dict(schema='rampd.a70.lineage_family_split.v1',
        status='CONDITIONAL_AUXILIARY_FAMILY_SPLITS_PASS' if not reasons else 'REVIEW',
        reasons=reasons,canonical_recording_families=len(by_family),rows=summary,
        base_lineage_status=base['status'],
        formal_masks={k:0 for k in LABELS},
        complete_teacher_proof_replayed=False,
        derived_causal_pairs_proven=False,safe_training_labels_allowed=False)
