#!/usr/bin/env python3
"""Streaming 511NY report-lifetime inventory, NOT physical or TIM clearance labels."""
import argparse,csv,json,re
from collections import Counter,defaultdict
from datetime import datetime,timezone
from pathlib import Path
from zoneinfo import ZoneInfo
from math import isfinite


def parse_time(s,zone):
    s=s.strip()
    if not s: return None,'missing'
    try: d=datetime.fromisoformat(s.replace('Z','+00:00'))
    except ValueError:
        for fmt in ('%m/%d/%Y %I:%M:%S %p','%m/%d/%Y %I:%M %p','%m/%d/%Y %H:%M:%S'):
            try: d=datetime.strptime(s,fmt);break
            except ValueError: pass
        else: return None,'invalid'
    if d.tzinfo is not None: return d.astimezone(timezone.utc),'ok'
    # Explicit local clock assumption. Reject DST folds/gaps rather than guess.
    options={q.astimezone(timezone.utc) for fold in (0,1) if (q:=d.replace(tzinfo=zone,fold=fold)).astimezone(timezone.utc).astimezone(zone).replace(tzinfo=None)==d}
    return (next(iter(options)),'ok') if len(options)==1 else (None,'ambiguous_or_nonexistent_local')


def classify(s):
    s=' '.join(s.casefold().split())
    if s in {'disabled vehicle','vehicle breakdown','disabled truck'}: return 'breakdown'
    if s in {'debris on roadway','debris','roadway debris'}: return 'debris'
    if s in {'accident','crash','accident with property damage','accident with injuries','fatal accident'}: return 'crash_report'
    if s in {'construction','roadwork','road maintenance operations','bridge work'}: return 'planned_work_report'
    if s in {'fallen tree','tree down','rock slide','landslide','flooding'}: return 'environment_report'
    return 'other_or_unknown'


def audit(path,zone_name='America/New_York',limit=None):
    zone=ZoneInfo(zone_name); counts=Counter(); per=defaultdict(Counter); org=Counter(); years=Counter(); raw_types=Counter()
    boundaries=(0,60,300,900,1800,3600,7200,21600,86400,604800)
    with path.open('r',encoding='utf-8-sig',newline='') as f:
        reader=csv.DictReader(f)
        norm=lambda k: re.sub(r'[^a-z0-9]+','_',k.casefold()).strip('_')
        columns={norm(k):k for k in reader.fieldnames or []}
        required={'event_type','organization_name','state','create_time','close_time','facility_name','latitude','longitude'}
        if not required<=columns.keys() or len(columns)!=len(reader.fieldnames or []): raise ValueError('missing/ambiguous columns: '+str(required-columns.keys()))
        for row in reader:
            if limit is not None and counts['rows']>=limit:break
            counts['rows']+=1
            get=lambda k:(row.get(columns[k]) or '').strip()
            typ=get('event_type'); raw_types[typ or '<missing>']+=1
            # Strict NY roadway subset proxy: exclude named transit organizations;
            # unknown road eligibility is not a positive incident label.
            state=get('state').upper(); agency=get('organization_name'); facility=get('facility_name')
            if state!='NY':counts['other_or_missing_state']+=1;continue
            org_key=agency.casefold()
            if any(w in org_key for w in ('transit','subway','railroad','rail road','bus','ferry')):counts['transit_org_excluded']+=1;continue
            if not (('dot' in org_key or 'department of transportation' in org_key or 'thruway' in org_key or 'transportation management' in org_key) and facility):counts['agency_or_facility_unverified']+=1;continue
            counts['ny_road_agency_proxy']+=1; org[agency]+=1
            group=classify(typ); p=per[group];p['rows']+=1
            try:
                lat,lon=float(get('latitude')),float(get('longitude'))
                geo=isfinite(lat) and isfinite(lon) and -90<=lat<=90 and -180<=lon<=180 and (lat,lon)!=(0,0)
            except ValueError:geo=False
            if not geo:p['invalid_or_missing_geo']+=1
            a,sa=parse_time(get('create_time'),zone);b,sb=parse_time(get('close_time'),zone)
            p['create_'+sa]+=1;p['close_'+sb]+=1
            if a is not None:years[str(a.astimezone(zone).year)]+=1
            if a is None or b is None:continue
            if a.astimezone(zone).year<2010 or b.astimezone(zone).year<2010:p['pre2010_timestamp']+=1;continue
            d=(b-a).total_seconds()
            if d<0:p['negative_lifetime']+=1;continue
            p['nonnegative_report_lifetime']+=1
            # zero is kept distinct; no outlier truncation or censor imputation.
            if d==0:p['zero_lifetime']+=1;continue
            label=next((f'lt_{t}s' for t in boundaries[1:] if d<t),'ge_604800s')
            p['lifetime_'+label]+=1
    return dict(status='BOUNDED_511_REPORT_INVENTORY_PASS' if counts['rows'] and counts['ny_road_agency_proxy'] else 'REVIEW_REQUIRED',scope='ROW_COUNTS_NOT_UNIQUE_INCIDENTS_REPORT_LIFETIME_NOT_TIM',input=str(path),timezone_assumption=zone_name,counts=dict(counts),groups={g:dict(p) for g,p in sorted(per.items())},top_raw_types=raw_types.most_common(30),top_road_agencies=org.most_common(30),create_years=dict(sorted(years.items())),full_scan=limit is None,exact_event_labels_generated=False,physical_clearance_labels_generated=False,unique_incidents_known=False)


def main():
    p=argparse.ArgumentParser();p.add_argument('--csv',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--timezone',default='America/New_York');p.add_argument('--max-rows',type=int);a=p.parse_args()
    try:
        if a.max_rows is not None and a.max_rows<=0:raise ValueError('positive max rows')
        out=audit(a.csv,a.timezone,a.max_rows)
    except Exception as e:out=dict(status='ERROR',reason=f'{type(e).__name__}: {e}')
    a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(out,indent=2,allow_nan=False)+'\n');print(json.dumps(out,indent=2));return 0 if out['status']=='BOUNDED_511_REPORT_INVENTORY_PASS' else 4
if __name__=='__main__':raise SystemExit(main())
