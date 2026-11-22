"""Independent SUMO *summary* audit, NOT physical co-sim certification.

No missing field may be converted to a default PASS. For raw trajectory
independent replay use a59_sumo_forensics; this lightweight audit cannot see
signal ACKs or vehicle_trace samples and says so in its return value.
"""
from __future__ import annotations
from pathlib import Path
import json

_SCOPED_STATUS='SUMO_LOGICAL_CORRIDOR_PASS'
_SCOPED_MODEL='TRAFFIC_ACTUATED_LOGICAL_CORRIDOR_NOT_PHYSICAL_SINGLE_LANE'


def audit_runs(paths,*,expected_vehicles=70,require_all_complete=True,
               brake_limit=0,expected_profile=None,require_stop_reserve=False):
    if type(brake_limit) is not int or brake_limit<0 or type(expected_vehicles) is not int or expected_vehicles<=0:
        raise ValueError('positive baseline size and nonnegative exact comfort threshold required')
    rows=[]
    for p in paths:
        path=Path(p)
        r=json.loads(path.read_text())
        if not isinstance(r,dict):raise ValueError('each run summary must be a JSON object')
        reasons=[]
        if r.get('status')!=_SCOPED_STATUS:reasons.append('RUN_HAS_NOT_PASSED_SCOPED_GATE')
        if r.get('scope')!=_SCOPED_MODEL:reasons.append('UNKNOWN_SCOPE')
        if expected_profile is not None and r.get('traffic_profile')!=expected_profile:
            reasons.append('PROFILE_MISMATCH')
        if require_stop_reserve and r.get('stop_reserve_guard') is not True:
            reasons.append('REQUIRED_STOP_RESERVE_CONTROL_NOT_VERIFIED')
        if type(r.get('seed')) is not int:reasons.append('MISSING_SEED')
        if not isinstance(r.get('violations'),list) or r['violations']:
            reasons.append('MISSING_OR_PRESENT_RESOURCE_VIOLATION')
        brakes=r.get('brake_steps')
        if not isinstance(brakes,list) or len(brakes)>brake_limit:
            reasons.append('MISSING_OR_EXCESSIVE_COMFORT_BRAKING')
        if r.get('comfort_review_required') is not False:
            reasons.append('COMFORT_OR_GUARD_EXHAUSTED_OR_UNREPORTED')
        expected=r.get('expected_vehicles',expected_vehicles)
        if type(expected) is not int or expected<=0:
            reasons.append('INVALID_EXPECTED_VEHICLE_COUNT')
        if require_all_complete and (
            type(r.get('departed_count')) is not int or
            type(r.get('arrived_count')) is not int or
            r.get('departed_count')!=expected or
            r.get('arrived_count')!=expected or
            r.get('roster_completion_pass') is not True or
            r.get('drained_at_cutoff') is not True):
            reasons.append('INCOMPLETE_VEHICLE_MISSION')
        if not isinstance(r.get('transitions'),list):
            reasons.append('MISSING_PHASE_TRANSITION_SUMMARY')
        rows.append({'source':str(path),'seed':r.get('seed'),
             'phase_transitions':len(r['transitions']) if isinstance(r.get('transitions'),list) else None,
             'brake_samples':len(brakes) if isinstance(brakes,list) else None,
             'warnings_considered':False,
             'traffic_profile':r.get('traffic_profile','baseline'),
             'departed':r.get('departed_count'),'arrived':r.get('arrived_count'),
             'result':'PASS_SCOPED' if not reasons else 'REVIEW',
             'reasons':sorted(set(reasons))})
    if not rows:raise ValueError('no runs supplied')
    seeds=[r['seed'] for r in rows]
    if len(set(seeds))!=len(seeds):raise ValueError('repeated seed does not establish distinct-seed coverage')
    profiles={r['traffic_profile'] for r in rows}
    if len(profiles)!=1:
        for row in rows:
            row['reasons']=sorted(set(row['reasons'])|{'MIXED_TRAFFIC_PROFILES'})
            row['result']='REVIEW'
    all_pass=all(r['result']=='PASS_SCOPED' for r in rows)
    # baseline sigma=speedDev=0 and deterministic departures: varying seeds
    # is NOT independent behavior variation. No claim of robustness coverage.
    deterministic_baseline=profiles=={'baseline'}
    return {'status':('DETERMINISTIC_BASELINE_SCOPED_REPLAY_ONLY' if deterministic_baseline
            else 'MULTISEED_LOGICAL_SUMO_PASS') if all_pass else 'REVIEW',
            'scope':'DIFFERENT_SEEDS_LOGICAL_CORRIDOR_ONLY_NO_CARLA',
            'runs':rows,'raw_trace_independently_replayed':False,
            'actual_signal_ack_evidence_available':False,
            'different_seed_behavior_diversity_proved':False,
            'real_shared_lane_proved':False,'real_driver_model_validated':False,
            'terminal_tail_certified':False,'training_labels_authorized':False}
