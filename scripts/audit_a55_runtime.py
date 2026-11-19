#!/usr/bin/env python3
"""Independent replay of uploaded/locally produced A55 JSON and SUMO trace.
Roster changes inferred from trace, NOT independent departed/arrived evidence.
No simulator execution or proof labels. Preserve diagnostics even on failure.
"""
import argparse, json, math, re, sys
from pathlib import Path
from fractions import Fraction as Q
from collections import defaultdict, Counter
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'python'))
from rampd_core.a54_signal import SignalPlan, SignalController
from rampd_core.a53_rule_models import FlowSnapshot
from rampd_core.a53b_interlock import ClearanceObservation
from rampd_core.a56_guard import GuardCase, GuardParent, advance_support


def waymax_report(r):
    import numpy as np
    if r.get("ego_control_profile","constant")!="constant":raise ValueError("A55 constant fixture only")
    dt=r['dt_s']; n=r['steps']; v={k:np.asarray(r['rollouts'][k],dtype=float) for k in ('A','AA','B')}
    if not math.isfinite(dt) or dt<=0 or type(n) is not int or n<2 or any(x.shape!=(n+1,2,5) or not np.isfinite(x).all() for x in v.values()):raise ValueError('invalid rollout shape or values')
    if r['actor_order']!=['ego','follower'] or r['state_order']!=['x','y','yaw','vx','vy']:raise ValueError('unknown state layout')
    # Exact minimum under declared straight piecewise constant acceleration;
    # include interior extremum of relative quadratic, not just endpoints.
    metrics={}
    for k,x in v.items():
        a=np.diff(x[:,:,3],axis=0)/dt; jerk=np.diff(a,axis=0)/dt
        gap=x[:,0,0]-x[:,1,0]-4.5; minimum=float(gap.min()); residual=np.diff(x[:,:,0],axis=0)-dt/2*(x[1:,:,3]+x[:-1,:,3]);
        for i in range(n):
            relv=x[i,0,3]-x[i,1,3]; rela=a[i,0]-a[i,1]
            if rela>0 and 0<-relv/rela<dt:
                t=-relv/rela; minimum=min(minimum,float(gap[i]+relv*t+rela*t*t/2))
        metrics[k]=dict(final_x=x[-1,:,0].tolist(),final_speed=x[-1,:,3].tolist(),min_accel=a.min(axis=0).tolist(),max_accel=a.max(axis=0).tolist(),max_abs_sampled_jerk=np.abs(jerk).max(axis=0).tolist(),minimum_knot_gap_m=float(gap.min()),minimum_quadratic_reference_gap_m=minimum,position_residual_m=float(np.abs(residual).max()),min_speed=float(x[:,:,3].min()),straight=bool(np.abs(x[:,:,[1,2,4]]).max()<=1e-5))
    a,aa,b=(v[k] for k in ('A','AA','B')); repeat=float(np.abs(a-aa).max()); delta=float(np.abs(a[:,1,3]-b[:,1,3]).max()); ed=float(np.abs(a[:,0,0]-b[:,0,0]).max()); first=bool(np.allclose(a[1,1],b[1,1],atol=1e-5,rtol=0)); init=bool(np.array_equal(a[0],b[0])); maneuver=bool(np.max(np.abs(np.diff(a[:,0,3])/dt))<1e-4 and np.max(np.abs(np.diff(b[:,0,3])/dt+3))<1e-4)
    good=(r['status']=='SYNTHETIC_IDM_RESPONSE_PASS' and init and maneuver and repeat<=1e-5 and delta>.05 and ed>.1 and first and b[-1,1,3]<a[-1,1,3] and all(m['straight'] and m['min_speed']>=-1e-5 and m['minimum_quadratic_reference_gap_m']>0 and m['position_residual_m']<.02 for m in metrics.values()))
    return dict(status='STRAIGHT_RESPONSE_TRACE_REPLAY_PASS' if good else 'REVIEW_REQUIRED',runs=metrics,aa_max=repeat,ab_follower_speed_max=delta,ab_ego_position_max=ed,same_initial=init,first_step_follower_equal=first,ego_control_parity=maneuver,physical_continuous_certificate=False,real_counterfactual_truth=False)


def sumo_report(r,trace,log):
    # Independent arithmetic; do not call probe_sumo_alternating.swept_occupants.
    if r.get("comfort_guard",False) or r.get("detector_range_m",200)!=200:raise ValueError("A55 baseline controller only")
    dt=Q(str(r['dt_s'])); steps=r['steps']; groups=defaultdict(dict); seen=set()
    if dt!=Q(1,10) or not steps:raise ValueError('expected A55 tick')
    with trace.open() as f:
        for line in f:
            row=json.loads(line); t=Q(str(row['time_s'])); i=t/dt
            vid=row['id']; d=row['direction']; x,v,l=(row[k] for k in ('front_m','speed_mps','length_m'))
            if i.denominator!=1 or not 1<=i<=len(steps) or vid in groups[int(i)] or d not in 'AB' or len(d)!=1 or not all(math.isfinite(z) for z in (x,v,l)) or min(x,v)<0 or l<=0:raise ValueError('bad trace record')
            groups[int(i)][vid]=(d,x,v,l)
    bounds=r['resource_bounds_m']; old={}; entered=Counter(); cleared=Counter(); arrivals=Counter(); born=Counter(); failures=[]; max_euler=0.; max_brake=0.; brake_candidates=[]; peak=Counter(); end_counts={}; replay_transitions=[]
    p=SignalPlan(dt,Q(12),Q(25),Q(3),Q(10),Q(1),1,'A55 replay'); c=SignalController.initial('sumo-demo',1,'logical-corridor',p)
    for i,s in enumerate(steps,1):
        t=i*dt; new=groups[i]; occ=Counter(); entry=Counter(); q=Counter(); at_end=0
        for vid in old.keys()|new.keys():
            a=old.get(vid); b=new.get(vid); d,x,v,l=b or a; lo,hi=bounds[d]
            if a is not None and b is not None:
                if a[0]!=b[0] or a[3]!=b[3] or b[1]<a[1]:failures.append([i,vid,'nonmonotone_or_changed'])
                max_euler=max(max_euler,abs(b[1]-a[1]-float(dt)*b[2])); dec=(a[2]-b[2])/float(dt);max_brake=max(max_brake,dec)
                if dec>4.01: brake_candidates.append((float(t),vid,dec))
            if a is None:
                if vid in seen:failures.append([i,vid,'id_reused'])
                seen.add(vid);born[d]+=1
                if b[1]>=lo:failures.append([i,vid,'birth_not_upstream'])
            if b is None:
                arrivals[d]+=1
                if a[1]-l<=hi:failures.append([i,vid,'disappeared_before_rear_clearance'])
            start=a[1] if a else 0.; end=b[1] if b else math.inf
            if start-l<=hi and end>=lo:occ[d]+=1
            if start<lo<=end:entry[d]+=1;entered[d]+=1
            if start-l<=hi<end-l and end>=lo: cleared[d]+=1
            if b:
                if b[1]<lo and b[2]<.1:q[d]+=1
                if b[1]>=lo and b[1]-l<=hi:at_end+=1
        if Q(str(s['time_s']))!=t or s['phase']!=c.phase or any(s[k]!=v for k,v in [('queue_a',q['A']),('queue_b',q['B']),('swept_a',occ['A']),('swept_b',occ['B']),('entries_a',entry['A']),('entries_b',entry['B'])]):failures.append([i,'state_or_count_mismatch'])
        if occ['A'] and occ['B']:failures.append([i,'opposing_sweep'])
        if any(entry[d] and disp=='RED' for d,disp in zip('AB',c.displays)):failures.append([i,'red_entry'])
        evidence=ClearanceObservation(t-dt,t,True,not any(occ.values()),'trace replay assumption',c.controller_id,c.version,c.resource_id)
        flow=FlowSnapshot(t,q['A'],q['B'],at_end)
        _,cells=advance_support((GuardParent('trace',c,(GuardCase('tick',flow,evidence),)),))
        nxt=cells['silence'][0].controller
        if nxt.phase!=s['next_phase']:failures.append([i,'guard_mismatch'])
        if nxt.phase!=c.phase:replay_transitions.append((float(t),c.phase,nxt.phase))
        c=nxt;old=new
        for d in 'AB':peak[d]=max(peak[d],q[d]);end_counts[d]=sum(v[0]==d for v in new.values())
    if {d:entered[d] for d in 'AB'}!=r['entries'] or replay_transitions!=[(x['time_s'],x['from_phase'],x['to_phase']) for x in r['transitions']] or r['violations']:failures.append(['report_mismatch'])
    text=log.read_text(); warnings=[x for x in text.splitlines() if 'performs emergency braking' in x.casefold()]; bad=[x for x in text.splitlines() if 'collision' in x.casefold() or 'teleport' in x.casefold()]
    return dict(status='LOGICAL_TRACE_REPLAY_PASS' if not failures and not bad else 'REVIEW_REQUIRED',failure_examples=failures[:30],failure_count=len(failures),reported_emergency_braking=warnings,brake_step_count=len(brake_candidates),max_sampled_decel_mps2=max_brake,peak_queue=dict(peak),entered=dict(entered),rear_cleared=dict(cleared),inserted=dict(born),disappeared_after_clear=dict(arrivals),remaining=dict(end_counts),final_resource_current_count=at_end,max_same_route_euler_residual_m=max_euler,final_phase=c.phase,transition_count=len(replay_transitions),comfort_review_required=bool(warnings or brake_candidates),drained_at_cutoff=not old,roster_events_independently_verified=False,physical_single_lane_certified=False,log_collision_or_teleport_lines=bad)


def main():
    p=argparse.ArgumentParser();p.add_argument('--waymax',type=Path,required=True);p.add_argument('--sumo',type=Path,required=True);p.add_argument('--trace',type=Path,required=True);p.add_argument('--sumo-log',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    try:
        out={'waymax':waymax_report(json.loads(a.waymax.read_text())), 'sumo':sumo_report(json.loads(a.sumo.read_text()),a.trace,a.sumo_log)}
        out['status']='SCOPED_TRACE_REPLAY_PASS' if all(x['status'].endswith('PASS') for x in out.values()) else 'REVIEW_REQUIRED'
    except Exception as e:out={'status':'ERROR','reason':f'{type(e).__name__}: {e}'}
    a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(out,indent=2,allow_nan=False)+'\n'); print(out['status']);return 0 if out['status']=='SCOPED_TRACE_REPLAY_PASS' else 4
if __name__=='__main__':raise SystemExit(main())
