"""CARLA observed brake/steer factorial; never infer tire force or guaranteed b.

A command readback is not measured wheel-torque ACK. Individual factorial
cells/replications are distinct, and low-speed stop solver impulses must not
be pooled with nonzero-speed braking dynamics.
"""
from __future__ import annotations
from .a71_carla_factor_pairs import audit_brake_steer_pair


def audit_available_brake_factorial(arms, *, levels=(.15,.30,.45),min_repeats=3):
    """arms keys (brake_fraction, 'pure'|'combined') -> distinct full raw docs.

    Partial valid cells have descriptive evidence; status is REVIEW until all
    six cells have the required independent replications.
    """
    reasons=[];cells=[];pair_rows=[]
    if type(min_repeats) is not int or min_repeats<1:raise ValueError('positive repeat count')
    for level in levels:
        pair={}
        for mode in ('pure','combined'):
            docs=arms.get((level,mode),())
            if type(docs) not in (list,tuple):raise TypeError('each cell has ordered raw experiment documents')
            digests=set();valid=0
            for doc in docs:
                # Individual recognition independent of any other cell.
                if type(doc) is not dict or doc.get('status')!='RAW_CARLA_TRIALS_CAPTURED_NOT_CERTIFIED':
                    reasons.append('INVALID_RAW_CAPTURE:'+str((level,mode)));continue
                trials=doc.get('trials',[])
                if len(trials)!=1 or trials[0].get('status')!='CAPTURED' or trials[0].get('maneuver')!=('brake' if mode=='pure' else 'combined'):
                    reasons.append('WRONG_MANEUVER_OR_TRIAL_COUNT:'+str((level,mode)));continue
                import json,hashlib
                digest=hashlib.sha256(json.dumps(doc,sort_keys=True,allow_nan=False).encode()).hexdigest()
                if digest in digests:reasons.append('DUPLICATED_RAW_REPLICATION:'+str((level,mode)));continue
                digests.add(digest);valid+=1
            if valid<min_repeats:reasons.append('INSUFFICIENT_REPLICATIONS:'+str((level,mode)))
            cells.append(dict(brake=level,mode=mode,received=len(docs),valid_capture_docs=valid))
            if docs:pair[mode]=docs[0]
        if set(pair)=={'pure','combined'}:
            p=audit_brake_steer_pair(pair['pure'],pair['combined'],brake=level)
            pair_rows.append(dict(brake=level,status=p['status'],reasons=p['reasons'],
                                  measurements=p['observations'],
                                  actuator_calibration=False,causal_tire_coupling_identified=False))
            if p['reasons']:reasons.append('PAIRED_PROTOCOL_FAILURE:'+str(level))
        else:reasons.append('MISSING_ONE_STEERING_ARM:'+str(level))
    return dict(schema='rampd.a72.carla.factorial.v1',
                status='DESCRIPTIVE_2X3_REPLICATED_NOT_CALIBRATED' if not reasons else 'REVIEW',
                reasons=sorted(set(reasons)),cells=cells,pairs=pair_rows,
                actual_wheel_torque_measured=False,physical_solver_contact_mode_identified=False,
                sufficient_real_vehicle_uncertainty_support=False,
                causal_tire_force_coupling_proved=False,safe_training_labels_allowed=False)
