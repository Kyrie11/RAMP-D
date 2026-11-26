"""Cross-check a genuinely complete 4x3 SUMO logical signal/Guard campaign.

Includes all 9000 steps per run and actual TraCI signal trace. Scope remains
separate directed edges in SUMO, not a proven physical reversible lane.
"""
from __future__ import annotations
from pathlib import Path
import json
from .sumo_tls_replay import audit_sumo_signal_trace,read_jsonl

PROFILES=('baseline','dense','slow_reaction','lower_friction_proxy')
SEEDS=(17,23,41)

def audit_campaign(root:Path):
    root=Path(root);reasons=[];rows=[];expected=set()
    for profile in PROFILES:
        for seed in SEEDS:
            key=f'sumo_{profile}_{seed}';expected.add(key)
            p=root/(key+'.json');trace=root/(key+'.work')/'signal_trace.jsonl'
            try:
                d=json.loads(p.read_text());signal=read_jsonl(trace)
                r=audit_sumo_signal_trace(d,signal)
                if d.get('traffic_profile')!=profile or d.get('seed')!=seed or d.get('scope')!='TRAFFIC_ACTUATED_LOGICAL_CORRIDOR_NOT_PHYSICAL_SINGLE_LANE':
                    reasons.append('WRONG_SCENARIO_IDENTITY:'+key)
                if r['reasons']:reasons.append('TRACI_SIGNAL_CAUSAL_REVIEW:'+key)
                steps=d.get('steps',[])
                if len(steps)!=9000 or d.get('violations') not in (0,[]):reasons.append('INCOMPLETE_OR_FAILING_LOGICAL_RESOURCE_TRACE:'+key)
                if d.get('departed_count')!=d.get('arrived_count') or not d.get('roster_completion_pass'):
                    reasons.append('INCOMPLETE_VEHICLE_ROSTER:'+key)
                # This is a logical occupancy / phase consistency check only.
                contradictions=0
                for st in steps:
                    contradictions+=int(st['swept_a']>0 and st['swept_b']>0)
                    contradictions+=int(st['entries_a']>0 and st['phase']!='A_GREEN')
                    contradictions+=int(st['entries_b']>0 and st['phase']!='B_GREEN')
                if contradictions:reasons.append('LOGICAL_GUARD_OCCUPANCY_CONTRADICTION:'+key)
                rows.append(dict(run_id=key,seed=seed,profile=profile,sim_steps=len(steps),
                    signal_records=len(signal),departed=d.get('departed_count'),
                    arrived=d.get('arrived_count'),logical_contradictions=contradictions,
                    traci_replay_status=r['status']))
            except (OSError,ValueError,TypeError,KeyError,IndexError) as ex:
                reasons.append('MISSING_OR_BAD_CAMPAIGN_RUN:'+key+':'+type(ex).__name__+':'+str(ex))
    extra={p.stem for p in root.glob('sumo_*.json') if '.signal_review' not in p.name}-expected
    if extra:reasons.append('UNDECLARED_RUNS_IN_CAMPAIGN')
    return dict(schema='rampd.a72.sumo.12_run_joint_guard.v1',
        status='DESCRIPTIVE_LOGICAL_SUMO_12_OF_12' if not reasons else 'REVIEW',
        reasons=sorted(set(reasons)),runs=rows,
        all_twelve_logical_controller_traces_verified=not reasons,
        physical_reversible_single_lane_verified=False,
        authority_effective_and_vehicle_receipt_time_verified=False,
        concrete_physical_barrier_ack_verified=False,
        full_actor_footprint_sweeps_verified=False,
        carla_sumo_common_clock_live_verified=False,
        formal_safe_training_labels_allowed=False)
