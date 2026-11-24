#!/usr/bin/env python3
"""Bounded stream of 511NY roadway *report rows* to A71 auxiliary JSONL.

Uses the existing DST-safe timestamp parser. Report creation and closure do
NOT represent physical blockage onset/reopening. If raw source lacks an event
identifier, create only a ROW identity and mark incident de-duplication UNKNOWN.
No traffic-rule labels or pseudo event-effectivity are produced.
"""
from __future__ import annotations
from pathlib import Path
import argparse,csv,hashlib,json,re,sys,tempfile,shutil
from collections import Counter
from zoneinfo import ZoneInfo
sys.path.insert(0,str(Path(__file__).resolve().parent))
from audit_511ny import parse_time,classify

def normalize_csv(source:Path, output:Path, *,max_rows:int=10000,timezone='America/New_York'):
    if type(max_rows) is not int or not 1<=max_rows<=10000000:raise ValueError('bounded max_rows')
    if output.exists():raise ValueError('REFUSE_EXISTING_OUTPUT')
    h=hashlib.sha256()
    with source.open('rb') as f:
        for buf in iter(lambda:f.read(4*1024*1024),b''):h.update(buf)
    sha=h.hexdigest();stats=Counter();bad=[];ids=set();staging=tempfile.SpooledTemporaryFile(mode="w+t",encoding="utf-8",max_size=1024*1024)
    with source.open(encoding='utf-8-sig',newline='') as f:
        rd=csv.DictReader(f)
        norm=lambda k:re.sub('[^a-z0-9]+','_',k.lower()).strip('_')
        cols={norm(k):k for k in rd.fieldnames or ()}
        required={'event_type','organization_name','state','facility_name','create_time','close_time'}
        if not required.issubset(cols) or len(cols)!=len(rd.fieldnames or ()):
            raise ValueError('required CSV report columns missing or ambiguous')
        get=lambda row,k:(row.get(cols[k]) or '').strip() if k in cols else ''
        zone=ZoneInfo(timezone)
        for i,row in enumerate(rd,2):
            if stats['rows_considered']>=max_rows:break
            stats['rows_considered']+=1
            org=get(row,'organization_name').lower()
            if (get(row,'state').upper()!='NY' or not get(row,'facility_name')
                or any(q in org for q in ('transit','subway','railroad','rail road','bus','ferry'))
                or not any(q in org for q in ('dot','department of transportation','thruway','transportation management'))):
                stats['excluded_nonroad_proxy']+=1;continue
            a,ast=parse_time(get(row,'create_time'),zone);b,bst=parse_time(get(row,'close_time'),zone)
            if a is None:
                stats['invalid_or_ambiguous_create']+=1
                if len(bad)<50:bad.append(dict(row=i,reason='CREATE_'+ast))
                continue
            if b is not None and b<a:
                stats['negative_report_duration_quarantined']+=1
                if len(bad)<50:bad.append(dict(row=i,reason='NEGATIVE_REPORT_DURATION'))
                continue
            ident=get(row,'event_id') or get(row,'id')
            unique_event_id_verified=bool(ident)
            if not ident:ident='SOURCE_ROW_'+str(i)
            # Preserve same source event id across multiple report revisions, do
            # not overwrite/merge: derived family grouping must handle that.
            key=ident
            if key in ids:stats['repeated_source_ids']+=1
            ids.add(key)
            staging.write(json.dumps(dict(source_event_id=key,source_dataset_sha256=sha,
                event_type=get(row,'event_type'),reported_create_time=a.isoformat(),
                reported_close_time=b.isoformat() if b else None,
                source_row_index=i,unique_source_event_identity_attested=unique_event_id_verified,
                reported_facility=get(row,'facility_name'),reported_organization=get(row,'organization_name'),
                reported_latitude=get(row,'latitude') or None,reported_longitude=get(row,'longitude') or None,
                event_group_guess=classify(get(row,'event_type')),scope='REPORT_ONLY'),ensure_ascii=False,allow_nan=False)+'\n')
            stats['normalized_rows']+=1
            if b is None:stats['missing_or_bad_close_time']+=1
    output.parent.mkdir(parents=True,exist_ok=True)
    staging.seek(0)
    with output.open('w',encoding='utf-8') as dest:shutil.copyfileobj(staging,dest)
    staging.close()
    summary=dict(schema='rampd.a71.511ny_source_row_stream.v1',
      status='DESCRIPTIVE_511NY_ROW_IMPORT_NOT_UNIQUE_EVENTS' if stats['normalized_rows'] else 'REVIEW',
      source_sha256=sha,timezone=timezone,counts=dict(stats),quarantine_examples=bad,
      event_effective_times_generated=False,metric_closures_generated=False,
      actor_message_receipt_inferred=False,event_uniqueness_proved=False,
      safety_or_formal_training_labels_generated=False)
    output.with_suffix(output.suffix+'.audit.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
    return summary

def main():
 p=argparse.ArgumentParser();p.add_argument('--csv',required=True,type=Path);p.add_argument('--output',required=True,type=Path)
 p.add_argument('--max-rows',type=int,default=10000);p.add_argument('--timezone',default='America/New_York');a=p.parse_args()
 r=normalize_csv(a.csv,a.output,max_rows=a.max_rows,timezone=a.timezone);print(json.dumps(r,ensure_ascii=False));return 0 if r['status'].startswith('DESCRIPTIVE') else 4
if __name__=='__main__':raise SystemExit(main())
