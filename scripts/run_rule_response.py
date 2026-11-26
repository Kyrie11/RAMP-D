#!/usr/bin/env python3
"""Scoped projected-lane diagnostic. No authorization of simulated trajectory labels."""
import argparse,json,sys
from pathlib import Path
from itertools import islice
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'python'))
from rampd_core.datasets.incident_response import from_record,from_feature_and_proposal,paired,audit_pair
from rampd_core.datasets.split_manifest import stream_records

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

def main():
    p=argparse.ArgumentParser();g=p.add_mutually_exclusive_group(required=True);g.add_argument('--manifest');g.add_argument('--inventory');g.add_argument('--cache');p.add_argument('--proposals');p.add_argument('--limit',type=int,default=5);p.add_argument('--steps',type=int,default=60);p.add_argument('--plots',action='store_true');p.add_argument('--output',required=True);a=p.parse_args()
    if not 1<=a.limit<=100 or not 1<=a.steps<=200:p.error('bounded pilot only')
    if bool(a.cache)!=bool(a.proposals):p.error('--cache and --proposals must be supplied together')
    if a.cache:
        from rampd_core.datasets.factual_dataset import load_cache
        from rampd_core.datasets.collate import collate
        sets,_=load_cache(a.cache); rows={r['scenario_id']:r for v in sets.values() for r in v}
        records=((p['family_id'],p) for p in map(json.loads,Path(a.proposals).read_text().splitlines()))
        def construct(p):
            if p['family_id'] not in rows:raise ValueError('proposal not in cache')
            row=rows[p['family_id']];collate([row]);return from_feature_and_proposal(row,p)
    else:
        raw=stream_records(json.loads(Path(a.manifest).read_text())) if a.manifest else iter(json.loads(Path(a.inventory).read_text())['records'])
        records=((r['scene']['manifest']['scenario_id'],r) for r in raw);construct=from_record
    out=Path(a.output);out.mkdir(parents=True,exist_ok=False);ok=[];bad=[]
    with (out/'pairs.jsonl').open('w') as f:
        for sid,record in islice(records,a.limit):
            try:r=paired(construct(record),steps=a.steps)
            except ValueError as exc:bad.append(dict(scenario_id=sid,reason=str(exc)));continue
            r['trace_audit']=audit_pair(r)
            if not r['trace_audit']['ok']:bad.append(dict(scenario_id=sid,reason='trace consistency failed',errors=r['trace_audit']['errors']));continue
            if a.plots:plot_pair(r,out/(sid+'.png'))
            f.write(json.dumps(r,allow_nan=False)+'\n');ok.append(dict(family_id=r['spec']['family_id'],actors=len(r['spec']['vehicles']),excluded=len(r['spec']['excluded_current']),aa_equal=r['aa_equal'],trace_audit=r['trace_audit'],ego_intervention=r['ego_intervention'],rule_intervention=r['rule_intervention'],alternative_response=r['alternative_response'],runs={k:dict(stop=v['stop'],violations=len(v['violations'])) for k,v in r['runs'].items()}))
    (out/'summary.json').write_text(json.dumps(dict(accepted=ok,rejected=bad,formal_sc=False,training_allowed=False),indent=2)+'\n');print('accepted',len(ok),'rejected',len(bad));return 0 if ok else 4
if __name__=='__main__':raise SystemExit(main())
