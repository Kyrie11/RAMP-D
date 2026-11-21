"""Independent A57 SUMO repeated-seed acceptance. Not physical co-sim safety."""
from __future__ import annotations
from pathlib import Path
import json

def audit_runs(paths,*,expected_vehicles=70,require_all_complete=True,brake_limit=0):
    rows=[]
    for p in paths:
        path=Path(p)
        r=json.loads(path.read_text())
        reasons=[]
        if r.get('scope')!='TRAFFIC_ACTUATED_LOGICAL_CORRIDOR_NOT_PHYSICAL_SINGLE_LANE':reasons.append('UNKNOWN_SCOPE')
        if r.get('violations'):reasons.append('RESOURCE_OR_TRAFFIC_VIOLATION')
        if require_all_complete and (r.get('departed_count')!=r.get('expected_vehicles',expected_vehicles) or
            r.get('arrived_count')!=r.get('expected_vehicles',expected_vehicles) or not r.get('roster_completion_pass') or not r.get('drained_at_cutoff')):
            reasons.append('INCOMPLETE_VEHICLE_MISSION')
        if len(r.get('brake_steps',[]))>brake_limit:reasons.append('COMFORT_BRAKING_EXCEEDED')
        if r.get('comfort_review_required'):reasons.append('COMFORT_OR_GUARD_EXHAUSTED')
        if r.get('status')=='ERROR':reasons.append('SIMULATOR_ERROR')
        rows.append(dict(source=str(path),seed=r.get('seed'),phase_transitions=len(r.get('transitions',[])),
             brake_samples=len(r.get('brake_steps',[])),warnings_considered=False,traffic_profile=r.get('traffic_profile','baseline'),
             departed=r.get('departed_count'),arrived=r.get('arrived_count'),
             result='PASS_SCOPED' if not reasons else 'REVIEW',reasons=sorted(set(reasons))))
    if not rows:raise ValueError('no runs supplied')
    seeds=[r['seed'] for r in rows]
    if len(set(seeds))!=len(seeds):raise ValueError('repeated seed does not establish distinct-seed coverage')
    return {'status':'MULTISEED_LOGICAL_SUMO_PASS' if all(r['result']=='PASS_SCOPED' for r in rows) else 'REVIEW',
            'scope':'DIFFERENT_SEEDS_LOGICAL_CORRIDOR_ONLY_NO_CARLA',
            'runs':rows,'real_shared_lane_proved':False,'real_driver_model_validated':False,
            'terminal_tail_certified':False}
