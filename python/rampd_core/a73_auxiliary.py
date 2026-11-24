"""Versioned weak label export, with dataset-wide route families, exact source
rows, and a separate visual domain. No formal loss authorization."""
import hashlib,json,re,unicodedata
from datetime import datetime
from collections import Counter
from .a72_auxiliary_pretraining import auxiliary_training_row,_split
MASKS={'L_'+k:0 for k in ('event','joint','occupancy','observation','viability','margin','deadline','causal')}
def norm(s):return ' '.join(unicodedata.normalize('NFKC',s).casefold().split())
def digest(s):return hashlib.sha256(json.dumps(s,sort_keys=True,ensure_ascii=False,allow_nan=False).encode()).hexdigest()
def export(rows):
    result=[];quarantine=[];seen=set();families={}
    for item in rows:
        try:
            if item.get('formal_label_masks')!=MASKS:raise ValueError('formal mask schema or authorization invalid')
            r=auxiliary_training_row(item);role=item['source_family'];source=digest(item)
            if source in seen:raise ValueError('duplicate source row')
            seen.add(source)
            if role=='511NY':
                category=norm(item['event_type_as_reported'])
                if not category or re.fullmatch(r'[\d\W]+',category):raise ValueError('unmapped report code')
                # A route family is deliberately coarser across dates, agencies and CSV versions.
                # Alias resolution is not complete. Split does not establish incident identity.
                facility=norm(item['reported_facility']);family='511NY:route:'+facility
                r.update(source_family_id=family,partition=_split(family),target=category,raw_target=item['event_type_as_reported'],report_year=datetime.fromisoformat(item['reported_create_time']).year,source_identity=item['source_event_id'],source_dataset_sha256=item['source_dataset_sha256'])
            else:
                r.update(source_identity=item['image_file'],source_annotation_sha256=item['source_annotation_sha256'],evaluation_authorized=False,partition='train' if item['official_gps_split']=='train' else 'validation_pending_site_review')
            g=r['source_family_id'];p=r['partition']
            if g in families and families[g]!=p:raise ValueError('cross partition family')
            families[g]=p;r.update(source_record_digest=source,formal_label_masks=dict(MASKS));result.append(r)
        except (ValueError,TypeError,KeyError,AttributeError) as e:quarantine.append(dict(reason=str(e),source=item))
    return dict(status='DESCRIPTIVE_WEAK_AUXILIARY_ONLY',rows=result,quarantine=quarantine,counts=dict(accepted=len(result),quarantined=len(quarantine),partitions=dict(Counter(r['partition'] for r in result)),families=len(families)),incident_uniqueness_proved=False,geographic_isolation_proved=False,formal_labels_authorized=False)
