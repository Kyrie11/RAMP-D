#!/usr/bin/env python3
import argparse,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'python'))
from rampd_core.cosim_map_registration import inventory,fit_landmarks

def main():
    p=argparse.ArgumentParser();p.add_argument('--xodr',required=True);p.add_argument('--net',required=True);p.add_argument('--landmarks');p.add_argument('--tolerance-m',type=float,default=.5);p.add_argument('--output',required=True);a=p.parse_args();r=inventory(a.xodr,a.net)
    if a.landmarks:
        l=json.loads(Path(a.landmarks).read_text())
        if any(l.get(k)!=r[k] for k in ('xodr_sha256','sumo_net_sha256')):raise ValueError('landmark map binding mismatch')
        r['registration']=fit_landmarks(l['points'],tolerance_m=a.tolerance_m)
    with open(a.output,'x') as f:json.dump(r,f,indent=2)
    print(r.get('registration',r)['status'])
    return 4 if r.get('registration',{}).get('status')=='REVIEW_MAP_REGISTRATION' else 0
if __name__=='__main__':raise SystemExit(main())
