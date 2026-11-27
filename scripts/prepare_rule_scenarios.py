#!/usr/bin/env python3
"""Small rule proposal / timing replay + BEV diagnostics. No response labels."""
import argparse,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'python'))
from rampd_core.datasets.split_manifest import stream_records
from rampd_core.datasets.incident_scenarios import propose,CLOCK_PROFILES

def draw(record,row,path):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    s=record['scene'];m=s['manifest'];k=m['current_time_index']; idx=m['metadata']['source_track_indices'].index(m['metadata']['sdc_track_index']); ego=s['tracks'][idx]; x,y=ego['states'][k]['x'],ego['states'][k]['y']
    fig,ax=plt.subplots(figsize=(8,7))
    for f in s['map_context']['primitives']:
        if f['kind'] in ('lane','road_edge','road_line') and f['vertices']:
            ax.plot([v['x']-x for v in f['vertices']],[v['y']-y for v in f['vertices']],color='0.75',lw=.5)
    v=row['lane_proposal']['centerline'];ax.plot([a-x for a,b in v],[b-y for a,b in v],color='orange',lw=3,label='Proposed lane centerline (not closed polygon)')
    for a in s['tracks']:
        st=a['states']; isego=a['track_id']==ego['track_id']; hist=[q for q in st[:k+1] if q['valid']];
        if hist: ax.scatter([q['x']-x for q in hist],[q['y']-y for q in hist],s=8 if isego else 3,c='blue' if isego else '0.4',alpha=.7)
        if isego:
            future=[q for q in st[k+1:k+31] if q['valid']];ax.scatter([q['x']-x for q in future],[q['y']-y for q in future],s=12,c='green',label='Original logged ego future (NOT intervention)')
    ax.scatter([0],[0],c='blue',s=40,label='Ego at cutoff');ax.set(xlim=(-60,60),ylim=(-60,60),aspect='equal',xlabel='World X offset (m)',ylabel='World Y offset (m)',title=f"{m['scenario_id']} | geometry proposal only");ax.legend(loc='upper right',fontsize=7);fig.tight_layout();fig.savefig(path,dpi=130);plt.close(fig)

def main():
    p=argparse.ArgumentParser();p.add_argument('--manifest',required=True);p.add_argument('--output',required=True);p.add_argument('--limit',type=int,default=5);p.add_argument('--plots',action='store_true');p.add_argument('--split',choices=('training','validation','all'),default='all');p.add_argument('--clock-profile',choices=tuple(CLOCK_PROFILES),default='nominal');a=p.parse_args()
    if not 1<=a.limit<=20:p.error('limit 1..20')
    from itertools import islice
    out=Path(a.output);out.mkdir(parents=True,exist_ok=False); rows=[]; rejected=[]
    records=stream_records(json.loads(Path(a.manifest).read_text()))
    for record in islice((r for r in records if a.split=='all' or r['scene']['manifest']['split']==a.split),a.limit):
        try: row=propose(record,clock_profile=a.clock_profile)
        except ValueError as e: rejected.append({'scenario_id':record['scene']['manifest']['scenario_id'],'reason':str(e)});continue
        rows.append(row)
        if a.plots: draw(record,row,out/(row['family_id']+'.png'))
    (out/'rule_scenarios.jsonl').write_text(''.join(json.dumps(r,allow_nan=False)+'\n' for r in rows));(out/'summary.json').write_text(json.dumps(dict(accepted=len(rows),rejected=rejected,physical_execution=False,training_allowed=False),indent=2)+'\n');print('accepted',len(rows),'rejected',len(rejected));return 0 if rows else 4
if __name__=='__main__':raise SystemExit(main())
