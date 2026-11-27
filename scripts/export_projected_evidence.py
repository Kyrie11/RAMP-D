#!/usr/bin/env python3
import argparse,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'python'))
from rampd_core.datasets.projected_labels import export_pair,sampled_projected_2d,bind_projected_widths_from_cache

def main():
    p=argparse.ArgumentParser();p.add_argument('--pairs',required=True);p.add_argument('--output',required=True);p.add_argument('--geometry-output');p.add_argument('--cache',help='optional source-bound dimension recovery for old pairs');p.add_argument('--corridor-width',type=float,default=3.5);a=p.parse_args();geometry=[];cached={};n=0;bad=[];seen=set();families={}
    if a.cache:
        from rampd_core.datasets.factual_dataset import load_cache
        sets,_=load_cache(a.cache);cached={r['scenario_id']:r for rows in sets.values() for r in rows}
    with Path(a.output).open('x') as out:
        for pair in map(json.loads,Path(a.pairs).read_text().splitlines()):
            try:
                rows=export_pair(pair);sid=rows[0]['family_id'];split=rows[0]['split'];digest=rows[0]['spec_sha256']
                if digest in seen or (sid in families and families[sid]!=split):raise ValueError('duplicate pair or cross-split family')
                seen.add(digest);families[sid]=split
                if a.geometry_output:
                    widths=pair['spec'].get('projected_widths',{})
                    try:
                        if not widths and sid in cached:widths=bind_projected_widths_from_cache(pair,cached[sid])
                        geo=sampled_projected_2d(pair,widths,corridor_width_m=a.corridor_width);geometry.append(dict(family_id=sid,spec_sha256=digest,**geo))
                    except ValueError as exc:geometry.append(dict(family_id=sid,spec_sha256=digest,unknown_reason=str(exc),training_allowed=False))
            except ValueError as e:bad.append(dict(family_id=pair.get('spec',{}).get('family_id'),reason=str(e)));continue
            for row in rows:out.write(json.dumps(row,allow_nan=False)+'\n');n+=1
    if a.geometry_output:
        with Path(a.geometry_output).open('x') as f:
            for row in geometry:f.write(json.dumps(row,allow_nan=False)+'\n')
    print(json.dumps(dict(rows=n,rejected=bad,training_allowed=False)));return 0 if n and not bad else 4
if __name__=='__main__':raise SystemExit(main())
