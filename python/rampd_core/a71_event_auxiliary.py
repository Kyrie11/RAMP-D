"""A71 preliminary 511NY and ROADWork *auxiliary* source adapters.

Source-specific semantics are kept separate. A 511NY report timestamp is NOT
traffic-rule effectivity; a ROADWork 2D image box is NOT a metric road closure.
Synthetic rule/event models require a different, explicitly authoritative
mechanism contract; neither source automatically produces a positive SC label.
"""
from __future__ import annotations
from datetime import datetime
from hashlib import sha256
import json


def _stamp(value):
    if type(value) is not str or not value:raise ValueError('missing timezone-aware report timestamp')
    t=datetime.fromisoformat(value.replace('Z','+00:00'))
    if t.tzinfo is None or t.utcoffset() is None:raise ValueError('timezone missing')
    return t


def adapt_511ny_report(row):
    """Input normalized 511 report attributes; zero assumptions about physical onset."""
    if not isinstance(row,dict):raise TypeError('normalized source row required')
    sid=row.get('source_event_id');src=row.get('source_dataset_sha256');etype=row.get('event_type')
    if not all(type(x) is str and x for x in (sid,src,etype)):
        raise ValueError('source event ID, event type and dataset hash required')
    created=_stamp(row.get('reported_create_time'))
    closed=_stamp(row['reported_close_time']) if row.get('reported_close_time') else None
    reasons=[]
    if closed and closed<created:reasons.append('NEGATIVE_REPORTED_DURATION_QUARANTINE')
    # Never equate reported creation/closure with physical activation/reopening.
    return dict(schema='rampd.a71.auxiliary_511ny_report.v1',
       source_family='511NY',source_event_id=sid,source_dataset_sha256=src,
       event_type_as_reported=etype,reported_create_time=created.isoformat(),
       reported_close_time=closed.isoformat() if closed else None,
       reported_facility=row.get('reported_facility'),
       reported_organization=row.get('reported_organization'),
       reported_latitude=row.get('reported_latitude'),
       reported_longitude=row.get('reported_longitude'),
       source_row_index=row.get('source_row_index'),
       unique_source_event_identity_attested=(row.get('unique_source_event_identity_attested') is True),
       observed_report_duration_s=(closed-created).total_seconds() if closed else None,
       status='REPORT_DURATION_REVIEW' if reasons else 'DESCRIPTIVE_REPORT_TIMES_ONLY',
       reasons=reasons,physical_rule_effective_at=None,physical_blocked_on=None,
       physical_reopened_at=None,vehicle_received_at=None,metric_resource_geometry=None,
       source_authority_confirmed=False,source_role='EXTERNAL_REPORT_ONLY',
       scenario_family_id='511NY:'+src+':'+sid,
       formal_label_masks={x:0 for x in ('L_event','L_joint','L_occupancy','L_observation','L_viability','L_margin','L_deadline','L_causal')})


def adapt_roadwork_scene(template):
    if not isinstance(template,dict) or template.get('status')!='VISUAL_SEMANTICS_ONLY_NEEDS_CALIBRATED_WORLD_GENERATOR':
        raise ValueError('previous grouped image template required')
    src=template.get('source',{})
    if not isinstance(src,dict) or not src.get('source_group') or not src.get('source_annotation_sha256') or not src.get('image_file'):
        raise ValueError('missing image/source grouping')
    objects=src.get('objects')
    if type(objects) is not list or any(type(o) is not dict or not o.get('category') for o in objects):
        raise ValueError('complete objects not available')
    return dict(schema='rampd.a71.auxiliary_roadwork_visual.v1',
        source_family='ROADWork',source_group=src['source_group'],
        source_annotation_sha256=src['source_annotation_sha256'],
        image_file=src['image_file'],template_id=template.get('template_id'),
        official_gps_split=src.get('source_split'),
        scene_tags=src.get('scene_tags'),scene_description=src.get('description'),
        categories=[o['category'] for o in objects],
        bbox_pixel_semantics_only=True,
        empty_annotation_does_not_prove_no_workzone=True,
        metric_polygon=None,physical_rule_effective_at=None,
        vehicle_received_at=None,official_rule_authority=None,
        status='DESCRIPTIVE_WORKZONE_OBJECTS_ONLY',
        scenario_family_id='ROADWork:'+src['source_annotation_sha256']+':'+src['source_group'],
        formal_label_masks={x:0 for x in ('L_event','L_joint','L_occupancy','L_observation','L_viability','L_margin','L_deadline','L_causal')})
