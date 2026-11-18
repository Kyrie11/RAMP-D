#!/usr/bin/env python3
"""Audit registry + flattened event CSV, not a certified rule or full schema validator."""
import argparse,csv,hashlib,json,zipfile
from collections import Counter
from datetime import datetime
from pathlib import Path

def digest(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def read_csv(p):
    with p.open(encoding='utf-8-sig',newline='') as f:
        reader=csv.DictReader(f); return tuple(reader.fieldnames or ()),list(reader)
def schema(p):
    if p.is_dir():
        candidates=list(p.glob('**/schemas/4.2/RoadEventFeature.json'))
        if len(candidates)!=1: raise ValueError('expected exactly one v4.2 schema')
        raw=candidates[0].read_bytes()
    else:
        with zipfile.ZipFile(p) as z:
            names=[n for n in z.namelist() if n.endswith('/schemas/4.2/RoadEventFeature.json')]
            if len(names)!=1: raise ValueError('expected exactly one v4.2 schema in zip')
            raw=z.read(names[0])
    return json.loads(raw),hashlib.sha256(raw).hexdigest()
def date(s):
    if not s: raise ValueError('missing date')
    t=datetime.fromisoformat(s.replace('Z','+00:00'))
    if t.tzinfo is None: raise ValueError('missing timezone')
    return t

def audit(registry,events,schema_path):
    rh,rr=read_csv(registry);eh,er=read_csv(events);s,sh=schema(schema_path)
    allowed=set(s['definitions']['VehicleImpact']['enum']); event_types=set(s['definitions']['EventType']['enum'])
    if not {'state','feedName','version','active'}<=set(rh): raise ValueError('wrong registry table')
    flags=('is_start_date_verified','is_end_date_verified','is_start_position_verified','is_end_position_verified')
    if not {'vehicle_impact','start_date','end_date','core_details','line',*flags}<=set(eh): raise ValueError('wrong event projection')
    impacts=Counter();types=Counter();ver={k:Counter() for k in flags};issues=Counter();geometry=Counter();methods=Counter()
    try:
        from shapely import wkt
    except ImportError: wkt=None
    for r in er:
        impact=r['vehicle_impact'];impacts[impact]+=1
        if impact not in allowed: issues['unknown_vehicle_impact']+=1
        try:
            typ=json.loads(r['core_details'])['event_type'];types[typ]+=1
            if typ not in event_types: issues['unknown_event_type']+=1
        except (ValueError,KeyError,TypeError): issues['invalid_core_details']+=1
        try:
            if date(r['end_date'])<date(r['start_date']): issues['reversed_date_interval']+=1
        except (ValueError,TypeError): issues['invalid_or_missing_dates']+=1
        for k in flags:
            v=(r[k] or '').lower();ver[k][v if v in ('true','false') else 'unknown']+=1
        methods[r.get('location_method') or 'unknown']+=1
        if wkt is not None:
            try:
                g=wkt.loads(r['line']);x1,y1,x2,y2=g.bounds
                if g.is_empty or not g.is_valid or g.geom_type!='LineString' or g.length<=0 or not (-180<=x1<=x2<=180 and -90<=y1<=y2<=90): raise ValueError('invalid geographic line')
                geometry['valid_geographic_lines']+=1
            except Exception: geometry['invalid_or_unsupported']+=1
    return {'status':'BOUNDED_CSV_INVENTORY_PASS' if rr and er and not issues and not geometry['invalid_or_unsupported'] else 'NOT_PASSED',
        'scope':'FLATTENED_REPORT_ROWS_NOT_UNIQUE_EVENTS_OR_LABELS','registry_rows':len(rr),'registry_active':dict(Counter(r['active'] for r in rr)),
        'registry_versions':dict(Counter(r['version'] or 'unknown' for r in rr)), 'event_rows':len(er),'vehicle_impact':dict(impacts),'event_type':dict(types),
        'verification_flags':{k:dict(v) for k,v in ver.items()},'location_method':dict(methods),'geometry_check':dict(geometry),'geometry_checked':wkt is not None,
        'issues':dict(issues),'feature_id_column_present':any(k in eh for k in ('id','feature_id','event_id')),'full_geojson_schema_validated':False,
        'unique_event_count_known':False,'authoritative_rule_time_labels_generated':False,'ego_receipt_labels_generated':False,
        'registry_sha256':digest(registry),'event_csv_sha256':digest(events),'schema_sha256':sh}

def main():
    p=argparse.ArgumentParser();p.add_argument('--registry',type=Path,required=True);p.add_argument('--event-csv',type=Path,required=True);p.add_argument('--schema',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    try: o=audit(a.registry,a.event_csv,a.schema)
    except Exception as e: o={'status':'ERROR','reason':f'{type(e).__name__}: {e}'}
    a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(o,indent=2)+'\n');print(json.dumps(o,indent=2));return 0 if o['status']=='BOUNDED_CSV_INVENTORY_PASS' else 4
if __name__=='__main__':raise SystemExit(main())
