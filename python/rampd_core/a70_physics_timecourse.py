"""A70 independently recomputed CARLA brake-arm time-course diagnostics.

A maximum deceleration at near-rest is not interchangeable with a peak at
cruising speed. Characterise early response, stopping and regime without
claiming vehicle calibration, torque-based bounds, or actuator latency proof.
"""
from __future__ import annotations
import hashlib,json,math
from .a69_physical_factors import audit_brake_sweep,_parse

def _finite(x):return type(x) in (int,float) and math.isfinite(x)

def audit_brake_timecourses(runs:dict[str,bytes], *,levels=(.15,.30,.45),
                            min_repeats_per_level:int=1)->dict:
    base=audit_brake_sweep(runs,levels=levels,min_repeats_per_level=min_repeats_per_level)
    reasons=list(base['reasons']);rows=[]
    if base['status']!='DESCRIPTIVE_ONE_FACTOR_SWEEP_COMPLETE_MODEL_REVIEW':
        reasons.append('ONE_FACTOR_DESIGN_NOT_ACCEPTED')
    for run_id,raw in sorted(runs.items()):
        try:
            d=_parse(raw);t=d['trials'][0];trigger=t['trigger_frame']
            samples=t['samples'];at={s['frame']:s for s in samples}
            post=[s for s in samples if s['frame']>trigger]
            post.sort(key=lambda s:s['frame'])
            if len(post)!=40 or any(post[i]['frame']!=trigger+i+1 for i in range(40)):
                raise ValueError('POST_TRIGGER_FRAME_COVERAGE')
            f0=at[trigger]
            for s in [f0]+post:
                if any(not _finite(s.get(k)) for k in ('sim_time_s','planar_speed_mps','signed_longitudinal_accel_mps2','x_m_carla','y_m_carla')):
                    raise ValueError('NONFINITE_OR_MISSING_DYNAMIC_FIELDS')
            dt=d.get('step_s')
            if not _finite(dt) or dt<=0:raise ValueError('INVALID_SIM_DELTA')
            for prior,s in zip([f0]+post[:-1],post):
                if not 0<s['sim_time_s']-prior['sim_time_s']<dt*1.01:
                    raise ValueError('DISCONTIGUOUS_SIM_TIMESTAMPS')
            peak_idx=min(range(len(post)),key=lambda i:post[i]['signed_longitudinal_accel_mps2'])
            peak=post[peak_idx]
            trigger_speed=f0['planar_speed_mps']
            if trigger_speed<=.5:raise ValueError('INVALID_TRIGGER_SPEED')
            earliest=next((s for s in post if s['planar_speed_mps']<=.05),None)
            path=0.
            timeline=[f0]+post
            for a,b in zip(timeline,timeline[1:]):
                path+=math.hypot(b['x_m_carla']-a['x_m_carla'], b['y_m_carla']-a['y_m_carla'])
            # Physical response at 5m/s is not the same as an isolated actuator
            # response. These indicators are descriptive and threshold-dependent.
            initial_four=post[:4]
            first_dec=next((s for s in post if s['signed_longitudinal_accel_mps2']<=-1),None)
            moving=[s for s in post if s['planar_speed_mps']>=1]
            peak_moving=min((s['signed_longitudinal_accel_mps2'] for s in moving),default=None)
            rows.append(dict(run_id=run_id,brake_fraction=t.get('combined_brake_fraction'),
                raw_sha256=hashlib.sha256(raw).hexdigest(),
                trigger_speed_mps=trigger_speed,
                peak_deceleration_mps2=-peak['signed_longitudinal_accel_mps2'],
                peak_control_step=peak_idx+1,peak_time_since_trigger_s=peak['sim_time_s']-f0['sim_time_s'],
                speed_at_peak_mps=peak['planar_speed_mps'],
                peak_regime=('NEAR_STOP' if peak['planar_speed_mps']<1 else 'MOVING'),
                moving_at_least_1mps_peak_deceleration_mps2=(-peak_moving if peak_moving is not None else None),
                first_four_frame_min_longitudinal_accel_mps2=min(s['signed_longitudinal_accel_mps2'] for s in initial_four),
                first_minus_1mps2_response_time_s=(first_dec['sim_time_s']-f0['sim_time_s'] if first_dec else None),
                stop_observed=(earliest is not None),
                descriptive_stop_time_s=(earliest['sim_time_s']-f0['sim_time_s'] if earliest else None),
                descriptive_path_length_m=path,
                no_formal_physical_bound=True))
        except (TypeError,KeyError,IndexError,ValueError,OverflowError) as exc:
            reasons.append('INVALID_TIMECOURSE:'+str(run_id)+':'+str(exc))
    if len(rows)!=len(runs):reasons.append('INCOMPLETE_TIMECOURSES')
    timecourses_valid=(len(rows)==len(runs) and not any(x.startswith('INVALID_TIMECOURSE:') for x in reasons))
    by_level={str(v):[x for x in rows if abs(x['brake_fraction']-v)<1e-5] for v in levels}
    # A peak at near-rest is a different kinetic regime; comparing only peak
    # amplitudes would wrongly identify actuator saturation across speed.
    regimes={x['peak_regime'] for x in rows}
    if len(regimes)>1:reasons.append('PEAKS_FROM_DIFFERENT_SPEED_REGIMES')
    if min_repeats_per_level<3:reasons.append('INSUFFICIENT_PER_ARM_REPLICATION_FOR_UNCERTAINTY')
    return dict(schema='rampd.a70.carla.brake_timecourse.v1',
        status='DESCRIPTIVE_TIMECOURSES_RECOMPUTED_MODEL_UNRESOLVED' if base['status'].startswith('DESCRIPTIVE_') and timecourses_valid else 'REVIEW',
        reasons=sorted(set(reasons)),one_factor_a69_status=base['status'],
        rows=rows,peak_speed_regimes_mixed=len(regimes)>1,
        observations_per_level={k:len(v) for k,v in by_level.items()},
        actual_brake_saturation_identified=False,actuator_delay_certified=False,
        carla_model_conformance_certified=False,physical_disturbance_support_certified=False,
        real_vehicle_physics_validated=False,safe_training_labels_allowed=False)
