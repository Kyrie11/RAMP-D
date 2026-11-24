"""Reality-informed auxiliary label factory (NOT RAMP-D formal SC supervision).

511NY label is what an operator *reported*, not lane legal effectivity.
ROADWork label is annotated image semantics, not metric road occupancy.
Canonical grouping prevents simple source-row leakage; potential unobserved
incident deduplication remains unknown, so no causal/generalization claim.
"""
from __future__ import annotations
from datetime import datetime
from hashlib import sha256
import json

def _split(key):
    # Immutable family hash; dataset-specific official split wins when present.
    n=int(sha256(key.encode('utf8')).hexdigest()[:8],16)%100
    return 'train' if n<80 else 'validation' if n<90 else 'test'

def auxiliary_training_row(item):
    if not isinstance(item,dict) or any(item.get('formal_label_masks',{}).values()):
        raise ValueError('formal label escalation prohibited')
    role=item.get('source_family')
    if role=='511NY':
        if item.get('status')!='DESCRIPTIVE_REPORT_TIMES_ONLY':raise ValueError('quarantined source')
        facility=item.get('reported_facility')
        org=item.get('reported_organization')
        t=datetime.fromisoformat(item['reported_create_time'])
        if not facility or not org or not item.get('event_type_as_reported'):
            raise ValueError('missing real report family or reported category')
        # Group by reporting agency, facility and *month*, never by individual
        # SOURCE_ROW_XX to avoid trivially splitting likely revisions.
        family='511NY:'+item['source_dataset_sha256']+':'+org.casefold()+':'+facility.casefold()+':'+t.strftime('%Y-%m')
        return dict(dataset='511NY',source_family_id=family,partition=_split(family),
            weak_target='reported_event_category',target=item['event_type_as_reported'],
            evidence_tier='EXTERNAL_OPERATOR_REPORT',
            timestamp_role='REPORT_CREATED_ONLY',spatial_role='ROUTE_TEXT_POINT_NO_LANE_CLOSURE',
            formal_rampd_label=None,official_safety_supervision=False)
    if role=='ROADWork':
        if item.get('status')!='DESCRIPTIVE_WORKZONE_OBJECTS_ONLY':raise ValueError('bad ROADWork annotation scope')
        if not item.get('source_group') or not item.get('source_annotation_sha256'):
            raise ValueError('unknown original video grouping')
        # Source split in ROADWork is official GPS split, but image template
        # group-disjoint validation is an additional requirement.
        # The annotation file hash differs between train/val. Do not include
        # it in the video family key, or a duplicated recording across official
        # splits would evade the leakage detector.
        family='ROADWork:'+item['source_group']
        declared=item.get('official_gps_split')
        if declared not in ('train','val',None):raise ValueError('unknown official ROADWork GPS split')
        partition={'train':'train','val':'validation',None:'unassigned_needs_official_gps_split'}[declared]
        return dict(dataset='ROADWork',source_family_id=family,partition=partition,
            weak_target='visible_workzone_object_classes',target=item['categories'],
            evidence_tier='HUMAN_ANNOTATED_IMAGE',timestamp_role='IMAGE_ONLY',
            spatial_role='PIXEL_ANNOTATIONS_NO_METRIC_CLOSURE',
            formal_rampd_label=None,official_safety_supervision=False)
    raise ValueError('unsupported auxiliary source')

def audit_auxiliary_training_records(records):
    reasons=[];rows=[];splits={}
    for i,item in enumerate(records):
        try:
            row=auxiliary_training_row(item);g=row['source_family_id'];p=row['partition']
            if g in splits and splits[g]!=p:reasons.append('CROSS_SPLIT_SOURCE_FAMILY_LEAK')
            splits[g]=p;rows.append(row)
        except (ValueError,KeyError,TypeError,IndexError) as e:reasons.append('UNUSABLE_SOURCE:'+str(i)+':'+str(e))
    return dict(schema='rampd.a72.aux_pretraining.v1',
        status='DESCRIPTIVE_AUXILIARY_DATASET_PREPARED' if rows and not reasons else 'REVIEW',
        reasons=reasons,rows=rows,dataset_rows=len(rows),distinct_declared_groups=len(splits),
        formal_eight_loss_supervision_generated=False,
        independent_teacher_certified=False,metric_physical_closures_attested=False)
