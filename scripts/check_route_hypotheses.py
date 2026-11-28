#!/usr/bin/env python3
import argparse,json,sys
from pathlib import Path
from itertools import islice
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'python'))
from rampd_core.datasets.incident_scenarios import lane_proposal,enumerate_route_hypotheses
from rampd_core.datasets.split_manifest import stream_records

def main():
    p=argparse.ArgumentParser();g=p.add_mutually_exclusive_group(required=True);g.add_argument('--manifest',type=Path);g.add_argument('--inventory',type=Path);p.add_argument('--limit',type=int,default=20);p.add_argument('--output',type=Path,required=True);a=p.parse_args();
    if not 1<=a.limit<=100:p.error('limit')
    records=stream_records(json.loads(a.manifest.read_text())) if a.manifest else iter(json.loads(a.inventory.read_text())['records']);rows=[]
    for r in islice(records,a.limit):
        sid=r['scene']['manifest']['scenario_id']
        try:
            lane=lane_proposal(r,max_distance=1.25,min_length=2,min_ahead=0,min_alignment=.9);q=enumerate_route_hypotheses(r,lane);rows.append(dict(scenario_id=sid,source_digest=r['record_sha256'],**q))
        except ValueError as e:rows.append(dict(scenario_id=sid,error=str(e)))
    a.output.parent.mkdir(parents=True,exist_ok=True)
    with a.output.open('x') as f:json.dump(dict(scope='MAP_ONLY_ROUTE_CANDIDATES_NOT_NAVIGATION_OR_PHYSICAL_SUPPORT',raw_manifest_path_used=bool(a.manifest),rows=rows),f,indent=2,allow_nan=False)
if __name__=='__main__':main()
