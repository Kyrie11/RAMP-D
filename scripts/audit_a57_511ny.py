#!/usr/bin/env python3
"""Streaming stratified report timestamp quality. No automatic repair/physical labels."""
import argparse,csv,json,re,hashlib
from collections import defaultdict,Counter
from pathlib import Path
from zoneinfo import ZoneInfo
from audit_511ny import parse_time,classify

def audit(path,zone_name='America/New_York'):
    zone=ZoneInfo(zone_name);strata=defaultdict(Counter);overall=Counter();examples=[]
    with path.open(encoding='utf-8-sig',newline='') as f:
        rd=csv.DictReader(f);norm=lambda k:re.sub(r'[^a-z0-9]+','_',k.casefold()).strip('_');cols={norm(k):k for k in rd.fieldnames or []}
        if not {'event_type','organization_name','state','facility_name','create_time','close_time'}<=cols.keys() or len(cols)!=len(rd.fieldnames or []):raise ValueError('bad columns')
        for lineno,row in enumerate(rd,2):
            overall['rows']+=1;get=lambda k:(row.get(cols[k]) or '').strip();org=get('organization_name');key=org.casefold()
            if get('state').upper()!='NY' or any(w in key for w in ('transit','subway','railroad','rail road','bus','ferry')) or not (('dot' in key or 'department of transportation' in key or 'thruway' in key or 'transportation management' in key) and get('facility_name')):continue
            overall['ny_road_agency_proxy']+=1
            a,sa=parse_time(get('create_time'),zone);b,sb=parse_time(get('close_time'),zone);g=classify(get('event_type'));yr=str(a.astimezone(zone).year) if a else 'unknown';c=strata[(org,yr,g,get('event_type'))];c['rows']+=1
            if a is None or b is None:status='UNRESOLVED_'+sa+'_'+sb
            elif min(a.astimezone(zone).year,b.astimezone(zone).year)<2010:status='QUARANTINE_PRE2010'
            else:
                d=(b-a).total_seconds()
                if d<0:
                    status='QUARANTINE_NEGATIVE';c['negative_le_1h' if -d<=3600 else 'negative_le_24h' if -d<=86400 else 'negative_gt_24h']+=1
                    if len(examples)<100:examples.append(dict(row=lineno,organization=org,event_type=get('event_type'),create=get('create_time'),close=get('close_time'),delta_s=d))
                elif d==0:status='ZERO_SEPARATE'
                else:status='POSITIVE_REPORT_ONLY'
            c[status]+=1;overall[status]+=1
    if sum(x['rows'] for x in strata.values())!=overall['ny_road_agency_proxy']:raise ValueError('strata conservation')
    with path.open('rb') as f:
        digest=hashlib.sha256()
        for chunk in iter(lambda:f.read(1024*1024),b''):digest.update(chunk)
    return dict(status='REPORT_QUALITY_AUDIT_PASS' if overall['ny_road_agency_proxy'] else 'REVIEW_EMPTY',scope='REPORT_ROW_QUALITY_NO_AUTOMATIC_REPAIR',sha256=digest.hexdigest(),timezone=zone_name,counts=dict(overall),strata=[dict(org=k[0],year=k[1],event_group=k[2],raw_event_type=k[3],counts=dict(v)) for k,v in sorted(strata.items())],negative_examples=examples,labels_generated=False,unique_events_proved=False,negative_repaired=0)

def main():
    p=argparse.ArgumentParser();p.add_argument('--csv',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--timezone',default='America/New_York');a=p.parse_args();r=audit(a.csv,a.timezone);a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(r,indent=2,ensure_ascii=False)+'\n');print(r['status']);return 0 if r['status']=='REPORT_QUALITY_AUDIT_PASS' else 4
if __name__=='__main__':raise SystemExit(main())
