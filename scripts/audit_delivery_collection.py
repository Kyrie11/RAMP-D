#!/usr/bin/env python3
"""Check matched coverage interventions, geometry ledger and model replay.
Optional normalized inventory binds a subset to source map vertices; no raw
TFRecord authenticity claim. Does not authorize labels.
"""
import argparse,json,sys,zipfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'python'))
from rampd_core.datasets.incident_response import audit_pair,paired,verify_projected_source
from rampd_core.datasets.incident_scenarios import route_integrity,verify_route_source,resource_applicability

def load(path):
    if path.suffix=='.zip':
        with zipfile.ZipFile(path) as z:
            names=[n for n in z.namelist() if n.endswith('/pairs.jsonl') or n=='pairs.jsonl']
            if len(names)!=1:raise ValueError('unique pairs ledger required')
            lines=z.read(names[0]).splitlines()
    else:lines=path.read_bytes().splitlines()
    rows=[json.loads(l) for l in lines];res={r['spec']['family_id']:r for r in rows}
    if len(res)!=len(rows):raise ValueError('duplicate family')
    return res

def main():
    p=argparse.ArgumentParser();p.add_argument('--zero',required=True,type=Path);p.add_argument('--half',required=True,type=Path);p.add_argument('--full',required=True,type=Path);g=p.add_mutually_exclusive_group();g.add_argument('--inventory',type=Path);g.add_argument('--manifest',type=Path);p.add_argument('--output',default='reports/phase7bc_relation/delivery_audit.json',type=Path);a=p.parse_args();cohorts=[load(v) for v in (a.zero,a.half,a.full)];ids=set(cohorts[0]);errors=[];details=[]
    if any(set(v)!=ids for v in cohorts):raise ValueError('coverage families differ')
    source={}
    if a.inventory:
        for r in json.loads(a.inventory.read_text())['records']:source[(r['scene']['manifest']['scenario_id'],r['record_sha256'])]=r
    if a.manifest:
        from rampd_core.datasets.split_manifest import stream_records
        for r in stream_records(json.loads(a.manifest.read_text()),selected_ids=ids):source[(r['scene']['manifest']['scenario_id'],r['record_sha256'])]=r
    for sid in sorted(ids):
        recs=[v[sid] for v in cohorts];specs=[r['spec'] for r in recs];fixed=lambda s:{k:v for k,v in s.items() if k not in ('receipts','all_current_receipts','recipient_model')}
        if not all(fixed(s)==fixed(specs[0]) for s in specs):errors.append([sid,'NON_DELIVERY_FACTOR_CHANGED'])
        rosters=[{i for i,t in s['receipts'].items() if i!=s['ego_id'] and t is not None} for s in specs]
        expected=set(specs[0]['receipts'])-{specs[0]['ego_id']}
        if rosters[0] or not rosters[1]<=rosters[2] or rosters[2]!=expected or any(s['receipts'][s['ego_id']]!=specs[0]['receipts'][s['ego_id']] for s in specs):errors.append([sid,'RECIPIENT_COVERAGE'])
        result=[]
        for prob,r,s in zip((0,.5,1),recs,specs):
            check=audit_pair(r);geo=route_integrity(s['lane']);original=source.get((sid,s['source_digest']));raw=verify_projected_source(original,s) if original else None
            if a.manifest and raw is None:errors.append([sid,prob,'SOURCE_BYTES_NOT_BOUND'])
            steps=r['runs']['A'].get('requested_steps')
            fresh=paired(s,steps=steps) if type(steps) is int else None
            replay=fresh is not None and all(r[k]==v for k,v in fresh.items())
            if not check['ok'] or not geo['ok'] or not replay or (raw is not None and not raw['ok']):errors.append([sid,prob,'AUDIT_OR_REPLAY'])
            run=r['runs']['A'];full=all(v['stop']=='HORIZON' and len(v['frames'])==steps+1 for v in r['runs'].values());viol=sum(v['kind']=='CLOSED_ENTRY' for v in run['violations'])
            result.append(dict(probability=prob,recipients=len(rosters[len(result)]),full=full,closed_entries=viol,rule_other_m=r['rule_intervention']['other_m'],trace_ok=check['ok'],replay=replay,source_map_checked=raw is not None,source_map_ok=None if raw is None else raw['ok']))
        details.append(dict(scenario_id=sid,actors=len(specs[0]['vehicles']),excluded=len(specs[0]['excluded_current']),joins=len(specs[0]['lane'].get('route_joins',[])),length_m=specs[0]['lane']['centerline_length_m'],resource_straight=resource_applicability(specs[0])['centerline_straight_closure_candidate'],coverage=result))
    aggregates=[]
    for j,pb in enumerate((0,.5,1)):
        d=[r['coverage'][j] for r in details];aggregates.append(dict(probability=pb,recipients=sum(r['recipients'] for r in d),full=sum(r['full'] for r in d),closed_entries=sum(r['closed_entries'] for r in d),full_other_response=sum(r['full'] and r['rule_other_m']>=.1 for r in d),replay=sum(r['replay'] for r in d)))
    report=dict(scope='PROJECTED_REPLAY_AND_OPTIONAL_NORMALIZED_MAP_NOT_FULL_REAL_WORLD',ok=not errors,errors=errors,families=len(ids),actors=sum(r['actors'] for r in details),excluded=sum(r['excluded'] for r in details),joins=sum(r['joins'] for r in details),source_map_families=sum(r['coverage'][0]['source_map_checked'] for r in details),aggregates=aggregates,details=details,formal_sc=False,training_allowed=False)
    a.output.parent.mkdir(parents=True,exist_ok=True)
    with a.output.open('x') as f:json.dump(report,f,indent=2,allow_nan=False)
    print(json.dumps({k:v for k,v in report.items() if k!='details'}));return 0 if report['ok'] else 4
if __name__=='__main__':raise SystemExit(main())
