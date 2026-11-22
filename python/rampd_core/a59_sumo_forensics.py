"""A59/0 independent, streaming SUMO trace forensics (not full traffic safety).

Reads old a58.zip artifacts even when summary JSON was overwritten by an ERROR.
Full roster, per-step vehicle conservation, monotonically directed route
coordinates, *sampled* braking, and logical swept occupancy are recomputed.
Without per-tick actual light display and command ACK, a trace NEVER proves
red-light compliance or physical single-lane capacity.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import io
import json
import math
from pathlib import Path
import xml.etree.ElementTree as ET
from zipfile import ZipFile


@dataclass(frozen=True)
class _Vehicle:
    direction: str
    front: float
    speed: float
    length: float


def _network_lengths(network_xml):
    root=ET.fromstring(network_xml)
    out={}
    for edge in root.findall('./edge'):
        lane=edge.find('lane')
        if lane is not None:out[edge.get('id')]=float(lane.get('length'))
    expected={'inA','midA','outA','inB','midB','outB'}
    if not expected<=set(out) or any(not math.isfinite(out[k]) or out[k]<=0 for k in expected):
        raise ValueError('missing or invalid length for corridor edge')
    bounds={d:(out['in'+d],out['in'+d]+out['mid'+d]) for d in 'AB'}
    route_lengths={d:sum(out[e+d] for e in ('in','mid','out')) for d in 'AB'}
    return bounds,route_lengths


def _readlines(binary):
    for line in binary:
        if line.strip():yield json.loads(line)


def _grouped_trace(items):
    current_t=None;vehicles={}
    for row in items:
        t=row['time_s'];vid=row['id']
        if not isinstance(t,(float,int)) or not math.isfinite(t):raise ValueError('nonfinite time')
        if current_t is not None and t!=current_t:
            if t<=current_t:raise ValueError('nonmonotone trace ordering')
            yield current_t,vehicles
            vehicles={}
        if vid in vehicles:raise ValueError('duplicate vehicle in frame')
        v=_Vehicle(row['direction'],float(row['front_m']),float(row['speed_mps']),float(row['length_m']))
        if (v.direction not in 'AB' or not all(math.isfinite(x) for x in (v.front,v.speed,v.length)) or
                v.front<0 or v.speed<0 or v.length<=0):raise ValueError('invalid vehicle trace state')
        vehicles[vid]=v;current_t=t
    if current_t is not None:yield current_t,vehicles


def audit_trace(network_xml, vehicle_stream, roster_stream, log_text, *,
                profile:str,seed:int,summary=None,step_s=0.1):
    """Exactly match per-frame roster deltas; no replay of hidden traffic-light ACKs.

    Streams are opened by the caller and are not buffered as large string lists.
    """
    bounds,totals=_network_lengths(network_xml)
    errors=[];departed=set();arrived=set();entered={d:set() for d in 'AB'}
    cleared={d:set() for d in 'AB'}
    previous={};prev_time=0.;nframes=0;brakes=[];opposing=[];first_entry=[]
    groups=iter(_grouped_trace(_readlines(vehicle_stream)))
    next_group=next(groups,None)
    warning_lines=[x for x in log_text.splitlines() if any(k in x.lower() for k in ('warning:', 'error:', 'collision', 'teleport'))]
    for rr in _readlines(roster_stream):
        nframes+=1
        t=rr['time_s']
        if abs(t - (prev_time+step_s))>1e-5:
            errors.append('NONCONTIGUOUS_TIME_GRID')
        prev_time=t
        if next_group is not None and next_group[0]<t-1e-5:
            errors.append('TRACE_TIME_BEFORE_ROSTER')
        if next_group is not None and abs(next_group[0]-t)<=1e-5:
            after=next_group[1];next_group=next(groups,None)
        else:after={}
        dd=rr['departed'];aa=rr['arrived']
        if len(dd)!=len(set(dd)) or len(aa)!=len(set(aa)) or set(dd)&set(aa):errors.append('ROSTER_DUPLICATE_OR_SAME_STEP')
        if set(after)-set(previous)!=set(dd) or set(previous)-set(after)!=set(aa):errors.append('ROSTER_DELTA_MISMATCH')
        if departed.intersection(dd) or arrived.intersection(aa):errors.append('REPEATED_LIFECYCLE_ID')
        departed.update(dd);arrived.update(aa)
        present={d:set() for d in 'AB'}
        for vid in previous.keys() | after.keys():
            old,new=previous.get(vid),after.get(vid)
            v=new or old
            if old is not None and new is not None:
                if v.direction!=old.direction or abs(new.length-old.length)>1e-4 or new.front<old.front-1e-5:
                    errors.append('NONMONOTONE_OR_MUTATED_ACTOR')
                if (old.speed-new.speed)/step_s>4.01:
                    brakes.append({'t':t,'id':vid,'decel_mps2':round((old.speed-new.speed)/step_s,5)})
            start,end=bounds[v.direction]
            lo=old.front if old is not None else 0.
            hi=new.front if new is not None else totals[v.direction]
            if hi>=start and lo-v.length<=end:
                present[v.direction].add(vid)
            if lo<start<=hi:
                entered[v.direction].add(vid);first_entry.append([t,vid,v.direction])
            if old is not None and old.front-old.length<=end and (new is None or new.front-new.length>end):
                cleared[v.direction].add(vid)
        if present['A'] and present['B']:
            opposing.append({'t':t,'a':sorted(present['A']),'b':sorted(present['B'])})
        previous=after
    if next_group is not None:errors.append('EXTRA_TRACE_BEYOND_ROSTER')
    if departed != arrived:errors.append('DEPARTURE_ARRIVAL_MISMATCH')
    if previous:errors.append('UNCLEARED_FINAL_ROSTER')
    if nframes==0:errors.append('NO_ROSTER_FRAMES')
    for d in 'AB':
        if entered[d]!=cleared[d]:errors.append('ENTRY_CLEARANCE_ID_MISMATCH:'+d)
    if opposing:errors.append('OPPOSING_LOGICAL_RESOURCE_SWEEP')
    if brakes:errors.append('COMFORT_BRAKE_SAMPLES')
    if warning_lines:errors.append('SIMULATOR_WARNING_OR_ERROR_REVIEW')
    if summary is None or summary.get('status')!='SUMO_LOGICAL_CORRIDOR_PASS':
        errors.append('MISSING_VALID_CONTROLS_SUMMARY')
    else:
        if summary.get('seed')!=seed or summary.get('traffic_profile')!=profile:
            errors.append('REPORT_IDENTITY_MISMATCH')
        if (summary.get('scope') != 'TRAFFIC_ACTUATED_LOGICAL_CORRIDOR_NOT_PHYSICAL_SINGLE_LANE'
                or summary.get('stop_reserve_guard') is not True
                or summary.get('roster_completion_pass') is not True
                or summary.get('drained_at_cutoff') is not True
                or summary.get('comfort_review_required') is not False
                or not isinstance(summary.get('violations'),list) or summary['violations']
                or not isinstance(summary.get('brake_steps'),list) or summary['brake_steps']
                or not isinstance(summary.get('transitions'),list)):
            errors.append('REPORT_DECLARED_REVIEW_OR_MISSING_CONTROL_FIELDS')
        if summary.get('departed_count')!=len(departed) or summary.get('arrived_count')!=len(arrived):
            errors.append('REPORT_ROSTER_MISMATCH')
        if summary.get('unique_entries')!={d:len(v) for d,v in entered.items()}:
            errors.append('REPORT_ENTRY_MISMATCH')
        if summary.get('rear_clearances')!={d:len(v) for d,v in cleared.items()}:
            errors.append('REPORT_CLEARANCE_MISMATCH')
    return {'profile':profile,'seed':seed,'status':('LOGICAL_TRACE_REPLAY_MATCH_WITH_DECLARED_SUMMARY'
                  if not errors else 'REVIEW'),
            'reasons':sorted(set(errors)), 'frames':nframes,
            'departed':len(departed),'arrived':len(arrived),
            'entered':{d:len(v) for d,v in entered.items()},
            'cleared':{d:len(v) for d,v in cleared.items()},
            'sampled_comfort_brake_count':len(brakes),'sampled_comfort_brake_examples':brakes[:5],
            'opposing_sweeps':len(opposing),'opposing_examples':opposing[:3],
            'log_warning_count':len(warning_lines),'log_warning_examples':warning_lines[:5],
            'first_entries':first_entry[:3],
            'valid_full_runtime_certificate':False,
            'signal_ack_per_tick_available':False,'physical_shared_lane':False,
            'continuous_vehicle_dynamics_certified':False,
            'training_labels_authorized':False}


def audit_a58_archive(zip_path:Path):
    """Audit all 12 uploaded run folders, including error-overwritten reports."""
    results=[]
    with ZipFile(zip_path) as z:
        names=set(z.namelist())
        folders=sorted({n.rsplit('/',1)[0] for n in names if n.endswith('/vehicle_trace.jsonl')})
        for folder in folders:
            name=folder.rsplit('/',1)[-1]
            if not name.startswith('sumo_'):continue
            rest=name[len('sumo_'):]
            profile,sep,seed=rest.rpartition('_')
            if not sep or not seed.isdigit():raise ValueError('bad source run ID '+name)
            p=folder+'/';jsonpath=folder+'.json'
            mandatory=[p+'network.xml',p+'vehicle_trace.jsonl',p+'roster_trace.jsonl',p+'sumo.log']
            if any(f not in names for f in mandatory):raise ValueError('missing trace artifact '+name)
            summary=json.loads(z.read(jsonpath)) if jsonpath in names else None
            with z.open(p+'vehicle_trace.jsonl') as v, z.open(p+'roster_trace.jsonl') as r:
                results.append(audit_trace(z.read(p+'network.xml'),v,r,
                    z.read(p+'sumo.log').decode(errors='replace'),profile=profile,
                    seed=int(seed),summary=summary))
    required={(profile,seed) for profile in
              ('baseline','dense','slow_reaction','lower_friction_proxy') for seed in (17,23,41)}
    observed={(r['profile'],r['seed']) for r in results}
    inventory_errors=[]
    if len(results)!=len(observed):inventory_errors.append('DUPLICATED_PROFILE_SEED')
    if observed!=required:inventory_errors.append('MISSING_OR_UNEXPECTED_PROFILE_SEED')
    return {'phase':'A59/0','source':str(zip_path),'total_runs':len(results),
            'complete_summary_and_trace_replays':sum(r['status']=='LOGICAL_TRACE_REPLAY_MATCH_WITH_DECLARED_SUMMARY' for r in results),
            'inventory_errors':inventory_errors,'expected_profile_seed_pairs':len(required),
            'status':'ALL_DECLARED_REPORTS_MATCH_SCOPED_TRACES' if not inventory_errors and
                all(r['status']=='LOGICAL_TRACE_REPLAY_MATCH_WITH_DECLARED_SUMMARY' for r in results) else 'REVIEW',
            'runs':results,'no_physical_or_training_certification':True}
