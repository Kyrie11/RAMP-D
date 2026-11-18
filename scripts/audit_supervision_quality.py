#!/usr/bin/env python3
"""Independent audit of bounded label inventory, not proof or training data.
Only measures fields actually present in the input manifest. No imputed labels.
"""
import argparse
from collections import Counter
import json
from pathlib import Path
import hashlib
import statistics


def audit(labels, waymax=None):
    groups=[]; problems=[]; ids={}; hashes={}
    required={('WOMD','training'),('WOMD','validation'),('AV2','train'),('AV2','validation')}
    observed=[(g['dataset'],g['split']) for g in labels['groups']]
    if set(observed)!=required or len(observed)!=len(required):
        problems.append('required four unique dataset splits not supplied')
    for g in labels['groups']:
        key=(g['dataset'],g['split']); rows=g.get('records',[])
        si=[r['scenario_id'] for r in rows]; sh=[r['raw_record_or_file_sha256'] for r in rows]
        if len(si)!=len(set(si)) or len(sh)!=len(set(sh)):
            problems.append(f'{key}: duplicate within split')
        ids[key]=set(si); hashes[key]=set(sh)
        for r in rows:
            n=r['valid_actor_time_knots']; d=r['joint_target_knots_with_box_dimensions']
            if r['status']!='LOGGED_EGO_PATH_SURROGATE' or not r['scenario_id'] or not r['raw_record_or_file_sha256']:
                problems.append(f'{key}: invalid factual record provenance/status')
            if type(n) is not int or type(d) is not int or not 0<=d<=n or n<=0 or type(r['actor_count']) is not int or r['actor_count']<=0:
                problems.append(f'{key}/{r["scenario_id"]}: invalid/empty factual count')
            if type(r['auxiliary_signal_change_brackets']) is not int or r['auxiliary_signal_change_brackets']<0:
                problems.append(f'{key}/{r["scenario_id"]}: invalid signal count')
        total=sum(r['valid_actor_time_knots'] for r in rows); dim=sum(r['joint_target_knots_with_box_dimensions'] for r in rows)
        groups.append(dict(dataset=key[0],split=key[1],status=g['status'],reason=g.get('reason'),
            scenes=len(rows),files=len(set(r['source_file'] for r in rows)),actors=sum(r['actor_count'] for r in rows),
            valid_knots=total,dimension_knots=dim,dimension_fraction=dim/total if total else None,
            signal_label_source_supported=key[0]=='WOMD',
            valid_knots_per_scene_min=min((r['valid_actor_time_knots'] for r in rows),default=None),
            valid_knots_per_scene_median=statistics.median([r['valid_actor_time_knots'] for r in rows]) if rows else None,
            valid_knots_per_scene_max=max((r['valid_actor_time_knots'] for r in rows),default=None),
            signal_brackets=sum(r['auxiliary_signal_change_brackets'] for r in rows),
            scenes_with_signal=sum(r['auxiliary_signal_change_brackets']>0 for r in rows),
            label_status_counts=dict(Counter(r['status'] for r in rows))))
        if g['status']!='PASS' or len(rows)!=labels['records_requested_per_split']:
            problems.append(f'{key}: bounded data gate not passed')
    for a in ids:
        for b in ids:
            if a<b and a[0]==b[0] and (ids[a]&ids[b] or hashes[a]&hashes[b]):
                problems.append(f'{a}/{b}: sampled split overlap')
    wm=None
    if waymax is not None:
        wm={k:waymax.get(k) for k in ('status','scope','initial_timestep','next_timestep','counterfactual_labels_generated','safety_certified')}
        wm['standard_91_frame_current_step_aligned']=waymax.get('initial_timestep')==10 and waymax.get('next_timestep')==11
        if not wm['standard_91_frame_current_step_aligned']: problems.append('Waymax: historical probe not aligned to current step 10')
        if wm['status']!='PASS' or wm['scope']!='WAYMAX_LOGGED_DATA_INGESTION_ONLY' or wm['counterfactual_labels_generated'] is not False or wm['safety_certified'] is not False:
            problems.append('Waymax: wrong scope/status or missing non-certification flags')
    return {'status':'NOT_PASSED' if problems else 'BOUNDED_INVENTORY_PASS',
        'scope':'UPLOADED_INVENTORY_ONLY_NOT_REALISM_OR_PROOF_OR_FULL_DEDUP', 'groups':groups,'findings':problems,'waymax':wm,
        'sampling':labels.get('sampling'),'full_dataset_deduplication':False,'geometry_occupancy_generated':False,
        'proof_labels_generated':False,'simulator_labels_generated':False,'training_complete':False}


def main():
    p=argparse.ArgumentParser();p.add_argument('--labels',type=Path,required=True);p.add_argument('--waymax',type=Path);p.add_argument('--output',type=Path,required=True);p.add_argument('--plot',type=Path);a=p.parse_args()
    raw=a.labels.read_bytes(); labels=json.loads(raw); result=audit(labels,json.loads(a.waymax.read_bytes()) if a.waymax else None)
    result['input_sha256']=hashlib.sha256(raw).hexdigest()
    if a.waymax: result['waymax_input_sha256']=hashlib.sha256(a.waymax.read_bytes()).hexdigest()
    a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(result,indent=2)+'\n')
    if a.plot:
        import matplotlib;matplotlib.use('Agg');import matplotlib.pyplot as plt
        fig,axs=plt.subplots(1,2,figsize=(10,4.2),layout='constrained')
        for g in labels['groups']:
            if not g['records']:continue
            k=f"{g['dataset']} {g['split']}";rows=g['records'];v=sorted(r['valid_actor_time_knots'] for r in rows)
            axs[0].step(v,[(i+1)/len(v) for i in range(len(v))],where='post',label=k)
            if g['dataset']=='WOMD':
                s=sum(r['auxiliary_signal_change_brackets']>0 for r in rows)
                axs[1].bar(k,s/len(rows),label=k);axs[1].text(k,s/len(rows)+.025,f'{s}/{len(rows)}',ha='center')
        axs[0].set(xlabel='Valid actor-time knots per scene',ylabel='Empirical cumulative fraction',title='Factual trajectory inventory');axs[0].legend();axs[1].set(ylim=(0,1),ylabel='Fraction of sampled scenes',title='At least one signal-change bracket');axs[1].tick_params(axis='x',rotation=12)
        fig.suptitle(f"Bounded inventory: {result['status']} — no generated proof labels",fontsize=12)
        axs[1].set_xlabel('AV2 signal supervision unavailable (not zero)')
        a.plot.parent.mkdir(parents=True,exist_ok=True);fig.savefig(a.plot,dpi=160);plt.close(fig)
    print(result['status']);return 0 if result['status']=='BOUNDED_INVENTORY_PASS' else 4
if __name__=='__main__':raise SystemExit(main())
