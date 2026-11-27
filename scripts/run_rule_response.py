#!/usr/bin/env python3
"""Scoped projected-lane diagnostic. No authorization of simulated trajectory labels."""
import argparse,json,sys
from pathlib import Path
from itertools import islice
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'python'))
from rampd_core.datasets.incident_response import from_record,from_feature_and_proposal,paired,audit_pair,reaction_evidence,reconfigure_projected_pair
from rampd_core.datasets.split_manifest import stream_records
from rampd_core.datasets.incident_scenarios import CLOCK_PROFILES,resource_applicability

def plot_pair(pair,path):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from fractions import Fraction
    fig,ax=plt.subplots(figsize=(9,5))
    spec=pair['spec'];c=spec['closure'];eid=spec['ego_id'];
    for name,style in [('A','-'),('B','--'),('NO_EVENT',':')]:
        frames=pair['runs'][name]['frames'];t=[float(Fraction(f['t'])) for f in frames]
        ax.plot(t,[f['state'][eid][0] for f in frames],style,label=name+' ego',lw=2)
        for i in sorted(frames[0]['state']):
            if i!=eid:ax.plot(t,[f['state'][i][0] for f in frames],style,lw=.7,alpha=.5)
    ax.axhspan(c['start'],c['end'],alpha=.12,color='orange',label='Projected resource interval')
    ax.axvline(float(Fraction(c['effective_on'])),color='red',alpha=.7,label='Rule on (EVENT)')
    ax.axvline(float(Fraction(c['effective_off'])),color='green',alpha=.7,label='Rule off (EVENT)')
    r=spec['receipts'][eid]
    if r is not None:ax.axvline(float(Fraction(r)),color='gray',ls='--',label='Ego receipt (EVENT)')
    # Do not extend the time axis just because the rule expires beyond the rollout.
    ax.set_xlim(0,max(float(Fraction(v['frames'][-1]['t'])) for v in pair['runs'].values()))
    ax.set(xlabel='Relative decision time (s)',ylabel='Projected center arc (m)',title=spec['family_id']+' | model diagnostic, not real trajectory')
    ax.legend(fontsize=8);fig.tight_layout();fig.savefig(path,dpi=140);plt.close(fig)

def plot_route_bev(pair,path,record=None):
    """Actual mapped centerline and projected scope. Not a lane polygon."""
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import numpy as np
    spec=pair['spec'];lane=spec['lane'];line=np.asarray(lane['centerline'],float);arc=np.r_[0.,np.cumsum(np.linalg.norm(np.diff(line,axis=0),axis=1))];c=spec['closure'];fig,ax=plt.subplots(figsize=(9,6))
    if record is not None and 'scene' in record:
        for f in record['scene']['map_context']['primitives']:
            if f['kind'] in ('lane','road_line','road_edge') and f['vertices']:
                ax.plot([v['x'] for v in f['vertices']],[v['y'] for v in f['vertices']],color='0.83',lw=.6)
        k=record['scene']['manifest']['current_time_index'];excluded={x[0] for x in spec['excluded_current']};points=[a['states'][k] for a in record['scene']['tracks'] if str(a['track_id']) in excluded and a['states'][k]['valid']]
        if points:ax.scatter([x['x'] for x in points],[x['y'] for x in points],c='0.5',s=12,label='Excluded current actors')
    ax.plot(line[:,0],line[:,1],color='tab:blue',lw=2,label='Mapped route centerline')
    q=np.linspace(c['start'],c['end'],60);ax.plot(np.interp(q,arc,line[:,0]),np.interp(q,arc,line[:,1]),color='tab:orange',lw=5,label='Declared closure arc (not polygon)')
    for a in spec['vehicles']:
        z=a['s'];x,y=np.interp(z,arc,line[:,0]),np.interp(z,arc,line[:,1]);ax.scatter([x],[y],c='tab:green' if a['id']==spec['ego_id'] else 'tab:red',s=30);ax.annotate(a['id'],(x,y),fontsize=8)
    ax.set(xlim=(line[:,0].min()-15,line[:,0].max()+15),ylim=(line[:,1].min()-15,line[:,1].max()+15),aspect='equal',xlabel='World X (m)',ylabel='World Y (m)',title=spec['family_id']+' | projected model only');ax.legend(fontsize=8);fig.tight_layout();fig.savefig(path,dpi=140);plt.close(fig)


def main():
    p=argparse.ArgumentParser();g=p.add_mutually_exclusive_group(required=True);g.add_argument('--manifest');g.add_argument('--inventory');g.add_argument('--cache');g.add_argument('--pair-input',help='audited existing pairs; reconfigure declared subscene, not raw replay');p.add_argument('--proposals');p.add_argument('--limit',type=int,default=5);p.add_argument('--steps',type=int,default=60);p.add_argument('--plots',action='store_true');p.add_argument('--extend-route',action='store_true',help='unique map successor chain, raw records only');p.add_argument('--output',required=True);p.add_argument('--clock-profile',choices=tuple(CLOCK_PROFILES),default='nominal');p.add_argument('--prepend-route',action='store_true');p.add_argument('--recipient-policy',choices=('all_current_nearest','projected_nearest'),default='all_current_nearest');p.add_argument('--visual-range',type=float);p.add_argument('--reaction-delay');p.add_argument('--physical-on');p.add_argument('--physical-off');a=p.parse_args()
    if not 1<=a.limit<=100 or not 1<=a.steps<=200:p.error('bounded pilot only')
    if bool(a.cache)!=bool(a.proposals):p.error('--cache and --proposals must be supplied together')
    if a.cache and a.clock_profile!='nominal':p.error('cached mode uses bound proposal clock, not overrides')
    if a.cache and (a.recipient_policy!='all_current_nearest' or a.prepend_route):p.error('cached proposal roster cannot be reassigned')
    if a.pair_input and (a.extend_route or a.prepend_route or a.clock_profile!='nominal'):p.error('existing pairs preserve topology and clock profile')
    if (a.physical_on is None)!=(a.physical_off is None) or (a.physical_on is not None and a.visual_range is None):p.error('physical window requires both times and visual proxy')
    if a.prepend_route and not a.extend_route:p.error('prepend requires extend-route')
    if a.cache and a.extend_route:p.error('--extend-route requires raw map topology')
    if a.cache:
        from rampd_core.datasets.factual_dataset import load_cache
        from rampd_core.datasets.collate import collate
        sets,_=load_cache(a.cache); rows={r['scenario_id']:r for v in sets.values() for r in v}
        records=((p['family_id'],p) for p in map(json.loads,Path(a.proposals).read_text().splitlines()))
        def construct(p):
            if p['family_id'] not in rows:raise ValueError('proposal not in cache')
            row=rows[p['family_id']];collate([row]);return from_feature_and_proposal(row,p)
    elif a.pair_input:
        records=((p['spec']['family_id'],p) for p in map(json.loads,Path(a.pair_input).read_text().splitlines()))
        construct=lambda p:reconfigure_projected_pair(p,recipient_policy='projected_nearest' if a.recipient_policy=='projected_nearest' else 'preserve')
    else:
        raw=stream_records(json.loads(Path(a.manifest).read_text())) if a.manifest else iter(json.loads(Path(a.inventory).read_text())['records'])
        records=((r['scene']['manifest']['scenario_id'],r) for r in raw);construct=lambda r:from_record(r,extend_route=a.extend_route,clock_profile=a.clock_profile,prepend_route=a.prepend_route,recipient_policy=a.recipient_policy)
    out=Path(a.output);out.mkdir(parents=True,exist_ok=False);ok=[];bad=[]
    with (out/'pairs.jsonl').open('w') as f:
        for sid,record in islice(records,a.limit):
            try:
                spec=construct(record)
                if a.reaction_delay is not None:spec['reaction_delay_s']=a.reaction_delay
                if a.visual_range is not None:
                    # Explicit scenario assumption: visibility interval coincides with
                    # legal effectivity in THIS experiment, not a physical ACK.
                    spec['observation_model']=dict(physical_on=a.physical_on or spec['closure']['effective_on'],physical_off=a.physical_off or spec['closure']['effective_off'],range_m=a.visual_range)
                r=paired(spec,steps=a.steps)
            except ValueError as exc:bad.append(dict(scenario_id=sid,reason=str(exc)));continue
            r['trace_audit']=audit_pair(r);r['reaction_evidence']=reaction_evidence(r);r['resource_applicability']=resource_applicability(r['spec'])
            if not r['trace_audit']['ok']:bad.append(dict(scenario_id=sid,reason='trace consistency failed',errors=r['trace_audit']['errors']));continue
            if a.plots:
                plot_pair(r,out/(sid+'.png'));plot_route_bev(r,out/(sid+'_bev.png'),record if not a.cache else None)
            f.write(json.dumps(r,allow_nan=False)+'\n');ok.append(dict(family_id=r['spec']['family_id'],actors=len(r['spec']['vehicles']),excluded=len(r['spec']['excluded_current']),aa_equal=r['aa_equal'],resource_applicability=r['resource_applicability'],trace_audit=r['trace_audit'],ego_intervention=r['ego_intervention'],rule_intervention=r['rule_intervention'],alternative_response=r['alternative_response'],runs={k:dict(stop=v['stop'],violations=len(v['violations'])) for k,v in r['runs'].items()}))
    (out/'summary.json').write_text(json.dumps(dict(accepted=ok,rejected=bad,formal_sc=False,training_allowed=False),indent=2)+'\n');print('accepted',len(ok),'rejected',len(bad));return 0 if ok else 4
if __name__=='__main__':raise SystemExit(main())
