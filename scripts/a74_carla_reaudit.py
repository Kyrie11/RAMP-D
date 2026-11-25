#!/usr/bin/env python3
import argparse,hashlib,json,sys,types,math
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'python'));pkg=types.ModuleType('rampd_core');pkg.__path__=[str(ROOT/'python'/'rampd_core')];sys.modules['rampd_core']=pkg
from rampd_core.a73_physics import diagnose

def review(root,dt=.05):
    rows=[]
    for f in sorted(root.glob('*_b*/run*.json')):
        d=json.loads(f.read_text());mode,b=f.parent.name.split('_b');b=int(b)/100;t=d['trials'][0];s=t['samples'];j=next(i for i,x in enumerate(s) if x['frame']==t['trigger_frame']);post=s[j+1:]
        # Normalize global frame/time away; identical response is not proof of copied run.
        signal=[{k:x.get(k) for k in ('planar_speed_mps','signed_longitudinal_accel_mps2','signed_lateral_accel_mps2','wheel_steer_deg_front_left_raw','wheel_steer_deg_front_right_raw','actual_brake','actual_throttle','actual_steer','actual_gear','yaw_rate_radps_carla')} for x in post]
        digest=hashlib.sha256(json.dumps(signal,sort_keys=True,allow_nan=False).encode()).hexdigest()
        mismatch=[i+1 for i,x in enumerate(post) if abs(x['actual_brake']-x['command_brake'])>1e-5 or abs(x['actual_throttle']-x['command_throttle'])>1e-5 or abs(x['actual_steer']-x['command_steer'])>1e-5]
        first=next((i+1 for i,x in enumerate(post) if abs(x['actual_brake']-b)<=1e-5),None)
        row=dict(file=str(f.relative_to(root)),mode=mode,brake=b,actor_id=d['actor_id'],trigger_frame=t['trigger_frame'],response_digest=digest,readback_mismatch_ticks=mismatch,first_matching_brake_sample_s=first*dt if first else None,readback_time_not_force_onset=True)
        try:
            r=diagnose(d,b,mode,dt);row.update(strict_pass=True,moving_peak_ax=r['regimes']['moving']['min_ax'],sampled_path_m=r['sampled_path_m'],sustained_stop_s=r['observed_sustained_stop_s'],right_censored=r['stop_right_censored'])
        except (ValueError,KeyError,TypeError) as e:row.update(strict_pass=False,reason=str(e))
        rows.append(row)
    cells={}
    for r in rows:
        key=f"{r['mode']}:{r['brake']:.2f}";cells.setdefault(key,[]).append(r)
    return dict(status='DESCRIPTIVE_ONLY',captures=len(rows),strict_pass=sum(x['strict_pass'] for x in rows),cells={k:dict(n=len(v),valid=sum(x['strict_pass'] for x in v),distinct_response_shapes=len({x['response_digest'] for x in v if x['strict_pass']})) for k,v in cells.items()},rows=rows,independence_proved=False,guaranteed_envelope=False,formal_labels_authorized=False)

def main():
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);p.add_argument('--dt',type=float,default=.05);p.add_argument('--output',type=Path,required=True);a=p.parse_args();
    if a.output.exists():raise SystemExit('REFUSE_OVERWRITE')
    r=review(a.root,a.dt);a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(r,indent=2)+'\n');print(r['captures'],r['strict_pass'],r['cells']);return 0 if r['captures'] else 4
if __name__=='__main__':raise SystemExit(main())
