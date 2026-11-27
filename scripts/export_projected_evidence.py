#!/usr/bin/env python3
import argparse,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'python'))
from rampd_core.datasets.projected_labels import export_pair

def main():
    p=argparse.ArgumentParser();p.add_argument('--pairs',required=True);p.add_argument('--output',required=True);a=p.parse_args();n=0;bad=[];seen=set();families={}
    with Path(a.output).open('x') as out:
        for pair in map(json.loads,Path(a.pairs).read_text().splitlines()):
            try:
                rows=export_pair(pair);sid=rows[0]['family_id'];split=rows[0]['split'];digest=rows[0]['spec_sha256']
                if digest in seen or (sid in families and families[sid]!=split):raise ValueError('duplicate pair or cross-split family')
                seen.add(digest);families[sid]=split
            except ValueError as e:bad.append(dict(family_id=pair.get('spec',{}).get('family_id'),reason=str(e)));continue
            for row in rows:out.write(json.dumps(row,allow_nan=False)+'\n');n+=1
    print(json.dumps(dict(rows=n,rejected=bad,training_allowed=False)));return 0 if n and not bad else 4
if __name__=='__main__':raise SystemExit(main())
