#!/usr/bin/env python3
"""Independent, fail-closed A69 input audit (no simulator or safety proof)."""
from __future__ import annotations
import argparse,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'python'))
from rampd_core.a68_physical_campaign import audit_physical_repeat_campaign
from rampd_core.a69_physical_factors import audit_brake_sweep
from rampd_core.a69_supervision_provenance import audit_lineage

def load_entries(items):
    result={}
    for token in items:
        if '=' not in token:raise ValueError('expected ID=PATH')
        key,path=token.split('=',1)
        if not key or key in result:raise ValueError('blank or duplicate run ID')
        result[key]=Path(path).read_bytes()
    return result

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--repeat',action='append',default=[],help='ID=raw JSON path, three required')
    p.add_argument('--brake-arm',action='append',default=[],help='ID=raw JSON path, at 0.15/0.30/0.45')
    p.add_argument('--output',required=True,type=Path)
    a=p.parse_args()
    if a.output.exists():raise SystemExit('REFUSE_EXISTING_OUTPUT')
    if not a.repeat and not a.brake_arm:
        raise SystemExit('AT_LEAST_ONE_REAL_SOURCE_CAMPAIGN_REQUIRED')
    repeats=load_entries(a.repeat)
    arms=load_entries(a.brake_arm)
    rep=audit_physical_repeat_campaign(repeats) if repeats else None
    factor=audit_brake_sweep(arms)
    lineage=audit_lineage(())
    result=dict(schema='rampd.a69.independent_three_track_progress.v1',
       stage='PHASE6C_A59_1B0O_CONDITIONAL_NOT_CERTIFIED',
       mathematical=dict(reference_joint_affine_and_guard_targeted_in_pytest=True,
          real_native_segmented_picard_replay=False,full_hidden_protocol_verified=False,
          continuous_swept_polygons_verified=False,terminal_sc_tail_verified=False),
       physical=dict(carla_repeated_control=rep,brake_one_factor_sweep=factor,
           physical_error_support_certified=False),
       evidence=dict(lineage_gate=lineage,
           eight_supervised_label_masks={k:0 for k in lineage['formal_label_masks']}),
       sc_certified=False,carla_sumo_live_sync_executed=False,
       waymax_live_simulator_executed=False,sumo_live_simulator_executed=False)
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(result,indent=2,ensure_ascii=False,allow_nan=False)+'\n')
    print(json.dumps(dict(repeats=rep['status'] if rep else 'NOT_SUPPLIED',
       brake_sweep=factor['status'],lineage=lineage['status'],certified=False),ensure_ascii=False,indent=2))
    # Diagnostic campaign not complete is legitimate for a work-in-progress
    # report, but a requested repeat campaign must have three valid runs.
    if repeats and rep['status']!='DESCRIPTIVE_THREE_REPEAT_PROTOCOL_REPRODUCED_MODEL_REVIEW':return 4
    if arms and factor['status']!='DESCRIPTIVE_ONE_FACTOR_SWEEP_COMPLETE_MODEL_REVIEW':return 4
    return 0

if __name__=='__main__':raise SystemExit(main())
