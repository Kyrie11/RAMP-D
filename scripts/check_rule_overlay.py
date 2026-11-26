#!/usr/bin/env python3
"""Build a scoped synthetic scheduled-rule sidecar; never attaches labels to logged motion."""
import argparse,json,sys
from pathlib import Path
from fractions import Fraction as Q
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'python'))
from rampd_core.datasets.split_manifest import stream_records
from rampd_core.datasets.rule_overlay import RuleOverlay,KINDS

def main():
    p=argparse.ArgumentParser();p.add_argument('--manifest',required=True);p.add_argument('--scenario-id',required=True);p.add_argument('--lane-id',required=True);p.add_argument('--kind',choices=KINDS,default='LANE_CLOSURE');p.add_argument('--generation',required=True);p.add_argument('--on',required=True);p.add_argument('--off',required=True);p.add_argument('--issue',required=True);p.add_argument('--receipt');p.add_argument('--authority',default='SIMULATED_ROAD_AUTHORITY');p.add_argument('--seed',type=int,default=7);p.add_argument('--announce-window',action='store_true');p.add_argument('--output',required=True);a=p.parse_args()
    m=json.loads(Path(a.manifest).read_text()); record=next((r for r in stream_records(m) if r['scene']['manifest']['scenario_id']==a.scenario_id),None)
    if record is None: raise ValueError('scenario not in manifest')
    s=record['scene']['manifest']; cutoff=str(s['timestamps'][s['current_time_index']]); event=RuleOverlay(a.scenario_id,record['record_sha256'],a.scenario_id+':demo:1',a.lane_id,a.kind,a.generation,a.on,a.off,a.issue,a.receipt,a.authority,a.seed,a.announce_window)
    output=event.bind(record);output.update(cutoff=cutoff,public_at_cutoff=event.public_view(cutoff),teacher_active_at_cutoff=event.teacher_active(cutoff),time_reference='WOMD_SCENARIO_SECONDS',physical_execution='NOT_RUN',history_reuse_compatible=(Q(event.generation)>=Q(cutoff)),history_reuse_note='Prior events require regenerated history or independent compatibility evidence; no response labels authorized')
    with open(a.output,'x') as f:json.dump(output,f,indent=2)
    print('SYNTHETIC_OVERLAY_BOUND_NO_TRAINING_AUTHORIZATION')
if __name__=='__main__':main()
