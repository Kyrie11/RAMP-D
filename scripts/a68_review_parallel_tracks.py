#!/usr/bin/env python3
"""Independent A68 *descriptive* audit of three uploaded CARLA repeats.

This CLI never creates a safety label, never uses CARLA or SUMO, and refuses
silent overwrite. It also reports that the other two tracks remain gated.
"""
from __future__ import annotations
import argparse,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'python'))
from rampd_core.a68_physical_campaign import audit_physical_repeat_campaign
from rampd_core.a68_supervision_release import review_supervision_sources

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--run',action='append',required=True,help='ID=exact input raw JSON path')
    p.add_argument('--output',type=Path,required=True)
    args=p.parse_args()
    raw={}
    for spec in args.run:
        if '=' not in spec:raise SystemExit('invalid --run ID=path')
        k,v=spec.split('=',1)
        if not k or k in raw:raise SystemExit('duplicate or blank run id')
        raw[k]=Path(v).read_bytes()
    if args.output.exists():raise SystemExit('REFUSE_EXISTING_OUTPUT')
    physical=audit_physical_repeat_campaign(raw)
    supervision=review_supervision_sources(())
    result=dict(schema='rampd.a68.three_track_acceptance.v1',
                overall_status='CONDITIONAL_A68_PARALLEL_ENTRY_AUDITED_NOT_CERTIFIED',
                source_files_live_carla_this_invocation=False,
                math=dict(exact_affine_reference_in_pure_tests=True,
                          native_picard_each_slab_replayed=False,full_guard_resources=False,
                          sc_goal_tail_certified=False),
                physical=physical,
                evidence_supervision=supervision,
                m1_to_m13_fully_certified=False,
                all_eight_losses_formally_released=False)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
    print(json.dumps({'overall_status':result['overall_status'],
                      'carla_repeat_status':physical['status'],
                      'carla_repeat_reasons':physical['reasons'],
                      'safety_labels_released':False},ensure_ascii=False,indent=2))
    return 0 if physical['status']=='DESCRIPTIVE_THREE_REPEAT_PROTOCOL_REPRODUCED_MODEL_REVIEW' else 4

if __name__=='__main__':raise SystemExit(main())
