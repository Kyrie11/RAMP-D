"""A71 offline, fail-closed SUMO TraCI *signal-state* causality replay.

The real simulator's traffic light state getter is evidence of the TraCI
controller representation; it is NOT a physical roadside signal or barrier ACK.
Time uses exact rational strings recorded by the simulator probe.
"""
from __future__ import annotations
from fractions import Fraction as Q
import json


def audit_sumo_signal_trace(summary:dict,rows:list[dict])->dict:
    reasons=[];seen={};issued={};post={}
    if summary.get('status')!='SUMO_LOGICAL_CORRIDOR_PASS' or summary.get('traci_signal_state_readback_observed') is not True:
        reasons.append('NO_SUCCESSFUL_INSTRUMENTED_SUMO_RUN')
    n=summary.get('steps')
    if type(n) is not list or not n:reasons.append('MISSING_LOGICAL_RESOURCE_TICKS')
    if not rows:reasons.append('EMPTY_TRACI_SIGNAL_RECORDS')
    if summary.get('signal_records')!=len(rows):reasons.append('SIGNAL_TRACE_INCOMPLETE')
    for row in rows:
        try:
            kind=row['kind'];t=Q(row['time']);tls=row['tls_id']
            if kind not in ('COMMAND_READBACK','POST_STEP_READBACK') or tls not in ('A','B') or t<0:
                raise ValueError('invalid identity or time')
            key=(kind,t,tls)
            if key in seen:reasons.append('DUPLICATE_TLS_TIME_KIND')
            seen[key]=True
            if kind=='COMMAND_READBACK':
                if row['desired']!=row['readback']:reasons.append('COMMAND_NOT_REFLECTED_IN_TRACI_STATE')
                if not row.get('entry_link_indices') or not row.get('exit_link_indices'):
                    reasons.append('UNMAPPED_TLS_LINKS')
                issued[(t,tls)]=row['desired']
            else:
                if row['expected']!=row['observed']:reasons.append('NEXT_TICK_SIGNAL_READBACK_MISMATCH')
                post[(t,tls)]=row['observed']
            if row.get('proof_scope')!='TRACI_SIGNAL_STATE_NOT_FIELD_ACTUATION_ACK':
                reasons.append('WRONG_PROOF_SCOPE')
        except (ValueError,KeyError,TypeError,ZeroDivisionError) as e:
            reasons.append('INVALID_RECORD:'+str(e))
    if type(n) is list and n:
        try:
            for i,s in enumerate(n):
                t=Q(str(s['time_s']));prior=Q(0) if i==0 else Q(str(n[i-1]['time_s']))
                if t-prior!=Q(1,10):reasons.append('GAPPED_SUMO_TICKS')
                for tls in ('A','B'):
                    if (t,tls) not in post or (prior,tls) not in issued:
                        reasons.append('MISSING_SIGNAL_STATE_FOR_TICK')
                    elif post[(t,tls)]!=issued[(prior,tls)]:
                        reasons.append('SIGNAL_READBACK_DIFFERENT_FROM_PREVIOUS_COMMAND')
                    # Controller commands at the current tick are valid for the NEXT physical step.
                    if (t,tls) not in issued and i<len(n)-1:
                        reasons.append('MISSING_CONTROLLER_COMMAND_AFTER_STEP')
        except (KeyError,ValueError,TypeError) as exc:
            reasons.append('INVALID_SUMO_STEP_TIME:'+str(exc))
    reasons=sorted(set(reasons))
    return dict(schema='rampd.a71.sumo_traci_signal_replay.v1',
        status='DESCRIPTIVE_TRAFFIC_LIGHT_STATE_TRACE_REPLAYED' if not reasons else 'REVIEW',
        reasons=reasons,tick_count=len(n) if isinstance(n,list) else 0,
        signal_records=len(rows),physical_signal_ack_proven=False,
        continuous_physical_shared_lane_proved=False,all_hidden_rule_worlds_proved=False,
        full_sc_certified=False,safe_training_labels_allowed=False)


def read_jsonl(path):
    values=[]
    with open(path,encoding='utf8') as f:
        for line in f:
            if line.strip():values.append(json.loads(line))
    return values
