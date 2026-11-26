#!/usr/bin/env python3
"""Recompute A74 evidence from the actual archives. No simulator is run."""
import argparse,hashlib,json,math,sys,types,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'python'))
if 'rampd_core' not in sys.modules:
    p=types.ModuleType('rampd_core');p.__path__=[str(ROOT/'python'/'rampd_core')];sys.modules['rampd_core']=p
from rampd_core.a73_physics import diagnose
from rampd_core.a75_contract import batch
from rampd_core.a75_wait_game import synthesize,replay

def carla(path):
    rows=[]
    with zipfile.ZipFile(path) as z:
        for f in sorted(z.namelist()):
            if not f.endswith('.json'):continue
            raw=z.read(f);d=json.loads(raw);t=d['trials'][0];dt=d['step_s'];b=t['brake_only_fraction'];row=dict(file=f,sha256=hashlib.sha256(raw).hexdigest(),dt=dt,brake=b)
            try:
                r=diagnose(d,b,'pure',dt);s=t['samples'];j=next(i for i,x in enumerate(s) if x['frame']==t['trigger_frame']);post=s[j+1:]; moving=[x for i,x in enumerate(post) if min(s[j+i]['planar_speed_mps'],x['planar_speed_mps'])>=1];peak=min(moving,key=lambda x:x['signed_longitudinal_accel_mps2']);w=peak['solver_telemetry_raw']['wheels'];v=peak['solver_telemetry_raw']['vehicle'];
                if len(w)!=4 or any(not math.isfinite(y[k]) for y in w for k in ('omega','long_slip','long_force','tire_load','tire_friction','torque')):raise ValueError('invalid wheel telemetry')
                force=sum(y['long_force'] for y in w);load=sum(y['tire_load'] for y in w);ax=peak['signed_longitudinal_accel_mps2'];mass=d['physics']['mass_kg_raw'];
                row.update(pass_capture=True,trigger_speed=r['initial_speed'],peak_ax=ax,peak_time_s=(post.index(peak)+1)*dt,peak_speed=peak['planar_speed_mps'],peak_raw_long_force_sum=force,peak_raw_load_sum=load,peak_force_over_load=force/load,peak_ma=mass*ax,peak_raw_force_over_ma=force/(mass*ax),all_wheels_locked=all(abs(y['omega'])<1e-4 for y in w),all_high_negative_slip=all(y['long_slip']<-.8 for y in w),wheel_data=w,engine=v,stop_s=r['observed_sustained_stop_s'],sampled_path_m=r['sampled_path_m'],right_censored=r['stop_right_censored'],raw_force_units_and_substep_alignment_unverified=True)
            except (ValueError,KeyError,TypeError,StopIteration,ZeroDivisionError) as e:row.update(pass_capture=False,reason=str(e))
            rows.append(row)
    return dict(status='DESCRIPTIVE' if rows and all(r['pass_capture'] for r in rows) else 'REVIEW',captures=len(rows),pass_count=sum(r['pass_capture'] for r in rows),rows=rows,physical_envelope=False)

def pair(path):
    import numpy as np
    d=json.loads(path.read_text());rows=[]
    for r in d['records']:
        if r['status']!='MODEL_CONDITIONAL_PAIR':rows.append(dict(index=r['index'],status='REVIEW'));continue
        A,AA,B=(np.asarray(r[k],dtype=float) for k in ('A','AA','B'))
        if A.shape!=AA.shape or A.shape!=B.shape or A.ndim!=3 or A.shape[-1]!=5 or not all(np.isfinite(x).all() for x in (A,AA,B)):raise ValueError('pair arrays')
        delta=np.linalg.norm(A[:,:,:2]-B[:,:,:2],axis=-1);maxima=delta.max(axis=0);ego=int(maxima.argmax());others=np.arange(len(maxima))!=ego
        # Current artifact lacks explicit ego ID; inferred largest-difference actor is diagnostic only.
        rows.append(dict(index=r['index'],aa=float(np.max(abs(A-AA))),initial=float(np.max(abs(A[0]-B[0]))),max_displacement=float(maxima[ego]),second_actor_max=float(maxima[others].max()),reported_ego=r['ego_ab_max_displacement_m'],reported_other=r['other_ab_max_displacement_m'],factual_ADE=r['factual_A_masked_ADE_m'],valid_samples_including_root=r['factual_valid_samples'],ego_identity_independently_bound=False,informative_reported_ego=r['ego_ab_max_displacement_m']>=.1,reported_other_response=r['other_ab_max_displacement_m']>=.01))
    return dict(rows=rows,scope='MODEL_ONLY_PRIVILEGED_FUTURE_ROUTE',formal_causal_label=False)

def main():
    p=argparse.ArgumentParser();p.add_argument('--carla-zip',type=Path,required=True);p.add_argument('--waymax-pair',type=Path,required=True);p.add_argument('--inventory',type=Path,required=True);p.add_argument('--format',type=Path,required=True);p.add_argument('--output-dir',type=Path,required=True);a=p.parse_args();a.output_dir.mkdir(parents=True,exist_ok=False)
    inventory=json.loads(a.inventory.read_text());fmt=json.loads(a.format.read_text());expected={r['scenario_id']:r['record_sha256'] for r in fmt['records'] if r['kind']=='SCENARIO'};actual={r['scene']['manifest']['scenario_id']:r['record_sha256'] for r in inventory['records']}
    if not expected or expected!=actual or len(expected)!=len(inventory['records']):raise ValueError('format/inventory mismatch')
    factual=batch(inventory['records']);(a.output_dir/'factual_validation.jsonl').write_text(''.join(json.dumps(r,allow_nan=False)+'\n' for r in factual));root,policy=synthesize();n=replay(root,policy,14);short=synthesize(horizon=11)[1]
    report=dict(carla=carla(a.carla_zip),waymax=pair(a.waymax_pair),factual=dict(scenarios=len(factual),valid_actor_knots=sum(r['heads']['joint']['valid_actor_knots'] for r in factual),training_rows=sum(r['heads']['joint']['training_allowed'] for r in factual),unmodelled_births=sum(len(r['births_unmodelled']) for r in factual)),finite_wait=dict(rank=n,first_action=policy['action'],horizon11_policy=short,scope='EXACT_FINITE_DECLARED_TRANSLATION_GAME',full_sc_native=False))
    (a.output_dir/'finite_wait_policy.json').write_text(json.dumps(policy,indent=2)+'\n');(a.output_dir/'review.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n');print(json.dumps({k:v for k,v in report.items() if k!='carla'},indent=2));print('CARLA',report['carla']['pass_count'],report['carla']['captures'])
if __name__=='__main__':main()
