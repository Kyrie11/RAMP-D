#!/usr/bin/env python3
"""Validate exclusive histogram bins and derive quantile brackets, not TIM time."""
import argparse, json, math
from pathlib import Path
B=(0,60,300,900,1800,3600,7200,21600,86400,604800)

def summarize(r):
    if r['status']!='BOUNDED_511_REPORT_INVENTORY_PASS':raise ValueError('inventory not passed')
    c=r['counts']; groups=r['groups']
    if sum(v for k,v in c.items() if k!='rows')!=c['rows'] or sum(x['rows'] for x in groups.values())!=c['ny_road_agency_proxy']:raise ValueError('inventory count mismatch')
    out={}
    for g,x in groups.items():
        if any(type(v) is not int or v<0 for v in x.values()):raise ValueError('invalid counts')
        n=x['nonnegative_report_lifetime'];z=x.get('zero_lifetime',0)
        bins=[dict(lo_s=0,hi_s=0,count=z,interval='point')]+[dict(lo_s=a,hi_s=b,count=x.get(f'lifetime_lt_{b}s',0),interval='positive_only' if a==0 else 'left_closed_right_open') for a,b in zip(B,B[1:])]+[dict(lo_s=B[-1],hi_s=None,count=x.get('lifetime_ge_604800s',0),interval='right_unbounded')]
        if sum(b['count'] for b in bins)!=n or n+x.get('negative_lifetime',0)>x['rows']:raise ValueError('lifetime bins inconsistent')
        def quantile(p):
            if not n:return None
            rank=math.ceil(n*p);cum=0
            for b in bins:
                cum+=b['count']
                if cum>=rank:return {k:b[k] for k in ('lo_s','hi_s','interval')}
        out[g]=dict(rows=x['rows'],valid_nonnegative=n,negative=x.get('negative_lifetime',0),negative_fraction=x.get('negative_lifetime',0)/x['rows'],zero=z,excluded_from_nonnegative=x['rows']-n,p10=quantile(.1),p50=quantile(.5),p90=quantile(.9),bins=bins)
    return dict(status='BOUNDED_REPORT_LIFETIME_SUMMARY_PASS',scope='SELECTED_NONNEGATIVE_511_REPORT_ROWS_ONLY',full_scan=r['full_scan'],timezone_assumption=r['timezone_assumption'],groups=out,physical_duration_identified=False,unique_event_identified=False,selection_bias_corrected=False)

def main():
    p=argparse.ArgumentParser();p.add_argument('--input',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--plot',type=Path);a=p.parse_args()
    out=summarize(json.loads(a.input.read_text()));a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(out,indent=2)+'\n')
    if a.plot:
        import matplotlib;matplotlib.use('Agg');import matplotlib.pyplot as plt
        for g,x in out['groups'].items():
            if not x['valid_nonnegative']:continue
            c=0;tx=[];y=[]
            for b in x['bins']:
                c+=b['count']
                if b['hi_s'] is not None and b['hi_s']>0:tx.append(b['hi_s']/60);y.append(c/x['valid_nonnegative'])
            plt.plot(tx,y,marker='o',label=g)
        plt.xscale('log');plt.xlabel('511 report lifetime upper bin boundary (min)');plt.ylabel('Fraction of nonnegative rows below boundary');plt.legend(fontsize=7);plt.tight_layout();a.plot.parent.mkdir(parents=True,exist_ok=True);plt.savefig(a.plot,dpi=160);plt.close()
    print(out['status']);return 0
if __name__=='__main__':raise SystemExit(main())
