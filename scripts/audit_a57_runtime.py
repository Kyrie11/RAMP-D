#!/usr/bin/env python3
"""Independent A56/A57 numeric audit of reported rollouts and raw SUMO traces.
Does not import simulator or controller; validates full roster, front/rear passage,
sampled excessive braking and signal-relative timing, not physical lane geometry.
"""
import argparse,json,math,re,collections,hashlib
from pathlib import Path
from fractions import Fraction as Q

def load(p):return json.loads(p.read_text())
def waymax(r):
    from fractions import Fraction as Q
    dt=Q(str(r['dt_s']));h=float(dt);rows=r['rollouts'];N=r['steps'];L=(r.get('ego_length_m',4.5)+r.get('follower_length_m',4.5))/2
    if any(len(v)!=N+1 for v in rows.values()) or set(rows)!=set(('A','AA','B')):raise ValueError('rollout lengths')
    ref=[];x=Q(0);v=Q(10);a=Q(0)
    for k in range(N+1):
        ref.append((float(x)+10+r.get('initial_center_offset_m',15),float(v)))
        j=Q(-5,2) if k<10 else Q(5,2) if 40<=k<50 else Q(0)
        x+=v*dt+a*dt**2/2+j*dt**3/6;v+=a*dt+j*dt**2/2;a+=j*dt
    out={};
    def idm(v,lead,g):return 2*(1-(v/13.9)**4-((2+max(0,1.5*v+v*(v-lead)/(2*math.sqrt(6))))/g)**2)
    for key in 'AB':
        z=rows[key];gaps=[s[0][0]-s[1][0]-L for s in z];vel=[s[1][3] for s in z];acc=[(b-a)/h for a,b in zip(vel,vel[1:])];ideal=[max(-vel[k]/h,idm(vel[k],z[k][0][3],gaps[k])) for k in range(N) if gaps[k]>0];err=[a-b for a,b in zip(acc,ideal)] if len(ideal)==N else []
        out[key]=dict(min_gap=min(gaps),last_state=z[-1],min_accel=min(acc),max_accel=max(acc),mean_abs_geometric_idm_error=sum(map(abs,err))/len(err) if err else None,max_abs_geometric_idm_error=max(map(abs,err)) if err else None,max_position_trapezoid_error=max(abs(b[1][0]-a[1][0]-h*(a[1][3]+b[1][3])/2) for a,b in zip(z,z[1:])))
        if 'official_internal_audit' in r:
            internal=r['official_internal_audit'][key];out[key]['internal_gap_error_max']=max(abs(x['distance_m']-gaps[k]) for k,x in enumerate(internal));out[key]['internal_speed_update_error_max']=max(abs(vel[k+1]-max(0,vel[k]+h*x['raw_accel_mps2'])) for k,x in enumerate(internal))
    obs=(rows['A'][1][1][3]-rows['A'][0][1][3])/h;vg=rows['A'][0][1][3];free=(vg/13.9)**4;ss=2+1.5*vg
    return dict(scope='NUMERIC_STRAIGHT_FIXTURE_ONLY',aa_equal=rows['A']==rows['AA'],initial_effective_gap_inferred=ss/math.sqrt(1-free-obs/2),smooth_max_x_error=max(abs(s[0][0]-t[0]) for s,t in zip(rows['B'],ref)) if r['ego_control_profile']=='smooth-stop' else None,smooth_max_v_error=max(abs(s[0][3]-t[1]) for s,t in zip(rows['B'],ref)) if r['ego_control_profile']=='smooth-stop' else None,rollouts=out,physical_certificate=False)

def sumo(r,work):
    by=collections.defaultdict(dict);roster={};n=len(r['steps']);dt=Q(str(r['dt_s']));
    def tick(t):
        k=Q(str(t))/dt
        if k.denominator!=1:raise ValueError('off-grid timestamp')
        return int(k)
    for l in (work/'vehicle_trace.jsonl').open():
        v=json.loads(l);k=tick(v['time_s']);vid=v['id'];
        if not 1<=k<=n or vid in by[k]:raise ValueError('duplicate/out-of-range trace sample')
        if v['direction'] not in ('A','B') or not all(math.isfinite(v[f]) for f in ('front_m','speed_mps','length_m')) or min(v['front_m'],v['speed_mps'])<0 or v['length_m']<=0:raise ValueError('invalid state')
        by[k][vid]=v
    for l in (work/'roster_trace.jsonl').open():
        v=json.loads(l);k=tick(v['time_s']);
        if k in roster:raise ValueError('duplicate roster tick')
        roster[k]=v
    if set(roster)!=set(range(1,n+1)):raise ValueError('missing roster tick')
    prev={};depart=set();arrive=set();entries={d:set() for d in 'AB'};clears={d:set() for d in 'AB'};violations=[];braking=[];switch_map={tick(t['time_s']):t for t in r['transitions'] if t['to_phase'].endswith('YELLOW')};switch_brake=[]
    for k in range(1,n+1):
        cur=by[k];ro=roster[k];dd=set(ro['departed']);aa=set(ro['arrived']);
        if len(dd)!=len(ro['departed']) or len(aa)!=len(ro['arrived']) or dd!=cur.keys()-prev.keys() or aa!=prev.keys()-cur.keys() or dd&depart or aa&arrive:raise ValueError('roster inconsistency')
        depart|=dd;arrive|=aa;occ={d:set() for d in 'AB'};ent={d:set() for d in 'AB'};phase=r['steps'][k-1]['phase']
        if tick(r['steps'][k-1]['time_s'])!=k or (k>1 and r['steps'][k-2]['next_phase']!=phase):raise ValueError('reported phase/tick chain broken')
        for vid in prev.keys()|cur.keys():
            a=prev.get(vid);b=cur.get(vid);v=b or a;d=v['direction'];L=v['length_m'];lo,hi=r['resource_bounds_m'][d];x=a['front_m'] if a else 0;y=b['front_m'] if b else float('inf')
            if a and b and (a['direction']!=b['direction'] or a['length_m']!=b['length_m'] or x>y):raise ValueError('changed body/direction or reverse')
            if y>=lo and x-L<=hi:occ[d].add(vid)
            if x<lo<=y:entries[d].add(vid);ent[d].add(vid)
            if x-L<=hi<y-L:clears[d].add(vid)
            if a and b:
                dec=(a['speed_mps']-b['speed_mps'])/float(dt)
                if dec>4.01:
                    braking.append((k,vid,dec,phase))
                    if k-1 in switch_map:
                        gap=lo-x;v=a['speed_mps'];switch_brake.append(dict(time_s=float((k-1)*dt),id=vid,front_gap_m=gap,speed_mps=v,old_stop_m=.1*v+v*v/8,stop_reserve_m=.1*v+v*v/8+2,phase=phase))
        if occ['A'] and occ['B']:violations.append((k,'opposing'))
        for d in 'AB':
            if ent[d] and (phase[0]!=d or phase.endswith('RED_CLEAR')):violations.append((k,'red entry',d))
            if len(occ[d])!=r['steps'][k-1]['swept_'+d.lower()] or len(ent[d])!=r['steps'][k-1]['entries_'+d.lower()]:violations.append((k,'trace summary mismatch',d))
        prev=cur
    logs=(work/'sumo.log').read_text();warnings=len(re.findall('performs emergency braking',logs));reported=[(tick(x['time_s']),x['id'],x['deceleration_mps2'],x['phase']) for x in r['brake_steps']]
    if sorted(braking)!=sorted(reported):violations.append(('braking summary mismatch',))
    return dict(scope='LOGICAL_ROUTE_MONOTONE_SWEEP_ONLY',departed=len(depart),arrived=len(arrive),entries={d:len(s) for d,s in entries.items()},rear_cleared={d:len(s) for d,s in clears.items()},all_identity_complete=depart==arrive==set().union(*entries.values())==set().union(*clears.values()) and all(entries[d]==clears[d] for d in 'AB') and len(depart)==70 and not prev,violations=violations,braking_samples=len(braking),braking_vehicle_count=len({x[1] for x in braking}),emergency_warnings=warnings,first_tick_after_yellow=switch_brake,queue_max={d:max(x['queue_'+d.lower()] for x in r['steps']) for d in 'AB'},physical_certificate=False)

def main():
    p=argparse.ArgumentParser();p.add_argument('--waymax',type=Path,required=True);p.add_argument('--sumo-control',type=Path,required=True);p.add_argument('--control-work',type=Path,required=True);p.add_argument('--sumo-comfort',type=Path,required=True);p.add_argument('--comfort-work',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();out=dict(waymax=waymax(load(a.waymax)),control=sumo(load(a.sumo_control),a.control_work),comfort=sumo(load(a.sumo_comfort),a.comfort_work));a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(out,indent=2,allow_nan=False)+'\n');print('AUDIT_WRITTEN');return 4 if any(out[k]['violations'] for k in ('control','comfort')) else 0
if __name__=='__main__':raise SystemExit(main())
