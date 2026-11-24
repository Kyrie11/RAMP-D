"""A71 external verifier for the repo's synthetic Waymax IDM paired rollouts.

No synthetic rollout, even with perfect replay, proves all-agent counterfactual
support or an actual driver's action under an alternate ego policy.
"""
from __future__ import annotations
import math


def _matrix(s):
    if type(s) not in (list,tuple) or len(s)!=2:raise ValueError('two explicit actors required')
    if any(type(row) not in (tuple,list) or len(row)!=5 or any(type(v) not in (int,float) or not math.isfinite(v) for v in row) for row in s):
        raise ValueError('invalid x,y,yaw,vx,vy row')
    return s


def audit_waymax_idm_pair(report:dict)->dict:
    reasons=[];metrics={}
    if not isinstance(report,dict):raise TypeError('Waymax report object required')
    if report.get('status')!='SYNTHETIC_IDM_RESPONSE_PASS':
        reasons.append('ORIGINAL_WAYMAX_PROBE_NOT_PASSED')
    if report.get('scope')!='SYNTHETIC_TWO_VEHICLE_STRAIGHT_ROUTE_ONLY' or report.get('real_scene_used') is not False:
        reasons.append('WRONG_SYNTHETIC_EXPERIMENT_SCOPE')
    if report.get('counterfactual_training_labels_generated') is not False or report.get('safety_certified') is not False:
        reasons.append('FORBIDDEN_FORMAL_LABEL_OR_SAFETY_CLAIM')
    if report.get('actor_order')!=['ego','follower'] or report.get('state_order')!=['x','y','yaw','vx','vy']:
        reasons.append('UNKNOWN_ACTOR_OR_STATE_REFERENCE')
    if type(report.get('steps')) is not int or not 2<=report.get('steps',0)<=80:
        reasons.append('INVALID_STEP_COUNT')
    if type(report.get('dt_s')) not in (float,int) or abs(report.get('dt_s',0)-.1)>1e-9:
        reasons.append('UNDECLARED_SIMULATOR_STEP')
    worlds=report.get('rollouts',{});v={}
    try:
        n=report['steps']+1
        for world in ('A','AA','B'):
            raw=worlds[world]
            if len(raw)!=n:raise ValueError('wrong rollout length')
            v[world]=[_matrix(row) for row in raw]
        # The counterfactual intervention cannot alter the common prefix or
        # retroactively change other agents' *first* decision.
        if any(abs(v['A'][0][i][j]-v['B'][0][i][j])>1e-5 for i in range(2) for j in range(5)):
            reasons.append('DIFFERENT_PREINTERVENTION_INITIAL_CONDITIONS')
        if any(abs(v['A'][1][1][j]-v['B'][1][1][j])>1e-4 for j in range(5)):
            reasons.append('FUTURE_LEAD_STATE_LEAKED_INTO_FOLLOWER_DECISION')
        difference_aa=max(abs(v['A'][i][a][d]-v['AA'][i][a][d]) for i in range(n) for a in range(2) for d in range(5))
        ego_cf=max(abs(v['A'][i][0][0]-v['B'][i][0][0]) for i in range(n))
        follower_cf=max(abs(v['A'][i][1][3]-v['B'][i][1][3]) for i in range(n))
        geom=report.get('ego_length_m'),report.get('follower_length_m')
        if not all(type(x) in (float,int) and math.isfinite(x) and x>0 for x in geom):
            raise ValueError('missing positive actor dimensions')
        gaps=[v[w][i][0][0]-v[w][i][1][0]-(geom[0]+geom[1])/2 for w in ('A','B') for i in range(n)]
        if min(gaps)<=0:reasons.append('SAMPLED_COLLISION_OR_NEGATIVE_GAP')
        if difference_aa>1e-4:reasons.append('IDENTICAL_CONTROL_NOT_DETERMINISTIC')
        if ego_cf<=.01 or follower_cf<=1e-4:reasons.append('PAIRED_INTERVENTION_NO_SENSITIVE_RESPONSE')
        for w in ('A','B'):
            if any(v[w][i+1][a][0]<v[w][i][a][0]-1e-4 or v[w][i][a][3]<-1e-6 for i in range(n-1) for a in range(2)):
                reasons.append('STRONGLY_NONMONOTONE_STRAIGHT_FIXTURE')
        audit=report.get('official_internal_audit',{})
        for w in ('A','AA','B'):
            if len(audit[w])!=n-1:raise ValueError('missing official internal per-step audit')
            if any(any(type(row.get(k)) not in (int,float) or not math.isfinite(row[k]) for k in ('distance_m','lead_speed_mps','raw_accel_mps2')) for row in audit[w]):
                raise ValueError('bad official IDM internals')
        if not report.get('idm_source_sha256') or not report.get('waymax'):
            reasons.append('MISSING_OFFICIAL_POLICY_PROVENANCE')
        metrics=dict(synthetic_actor_count=2,steps=n-1,deterministic_max_difference=difference_aa,
                    ego_position_intervention_difference_m=ego_cf,
                    follower_speed_intervention_difference_mps=follower_cf,
                    minimum_sampled_bumper_gap_m=min(gaps),
                    official_idm_internal_steps_present=True)
    except (ValueError,TypeError,KeyError,IndexError) as exc:
        reasons.append('INCOMPLETE_OR_MALFORMED_WAYMAX_TRACE:'+str(exc))
    reasons=sorted(set(reasons))
    return dict(schema='rampd.a71.waymax.synth_pair_independent.v1',
                status='DESCRIPTIVE_SYNTHETIC_PAIR_REPLAYED' if not reasons else 'REVIEW',
                reasons=reasons,measurements=metrics,
                actual_waymax_redistribution_run_here=False,real_driver_counterfactual_proved=False,
                curved_route_or_occlusion_covered=False,continuous_collision_proved=False,
                safe_training_labels_allowed=False)
