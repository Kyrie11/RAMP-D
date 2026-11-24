#!/usr/bin/env python3
"""Independently runnable TWO hidden worlds / 2 clock slabs native 6D replay.

A deterministic small example, not a real intersection/SC proof. Outputs
four MPFR/Picard certificates with byte digests bound to world/time/control.
"""
from __future__ import annotations
import argparse,json,sys
from pathlib import Path
from fractions import Fraction as Q
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'python'))
from rampd_core.a60_clock_resource import ClockEvent
from rampd_core.a61_hybrid_partition import ClockWorld
from rampd_core.a70_native_segmented import NativeSlabInput,replay_segmented_native
from rampd_core.model import BicycleParameters,ControlBounds,StateBounds
from rampd_core.interval import Interval
from rampd_core.reachability import integrate,TubeStatus
from rampd_core.a5_replay_bridge import exact_step_endpoint
from rampd_core.exact_time import binary64_bracket

def main(argv=None):
    ap=argparse.ArgumentParser();ap.add_argument('--output-dir',required=True)
    args=ap.parse_args(argv)
    out=Path(args.output_dir)
    if out.exists():raise SystemExit('REFUSE_EXISTING_OUTPUT_DIR')
    p=BicycleParameters(3,.9);u=ControlBounds.point(0,0)
    h=Q(1,20);z=(Interval.point(0),)*6
    x=StateBounds.point([0,0,0,4,0,0])
    first=integrate(x,u,p,binary64_bracket(h)[1])
    if first.status is not TubeStatus.VALIDATED:raise SystemExit('NATIVE_REFERENCE_PREP_FAILED')
    nxt=exact_step_endpoint(first,h)
    worlds=tuple(ClockWorld(world,(ClockEvent('switch-'+world,'RULE_EFFECTIVE',h,
        'DECLARED_TOY_MODEL'),),declared_complete=True,public_history_id='same')
        for world in ('A','B'))
    rows=tuple(NativeSlabInput(world,start,end,'same-public-control',initial,u,z)
            for world in ('A','B') for start,end,initial in ((Q(0),h,x),(h,2*h,nxt)))
    report,certs=replay_segmented_native(worlds,rows,start=Q(0),end=2*h,params=p)
    if report['status']!='CONDITIONAL_DECLARED_EGO_NATIVE_PICARD_SEGMENTED_REPLAY':
        raise SystemExit('NATIVE_SEGMENTED_MODEL_MICROCASE_FAILED:'+str(report['reasons']))
    out.mkdir(parents=True)
    for (world,start,end),cert in sorted(certs.items()):
        (out/f'world_{world}_slab_{start.numerator}_{start.denominator}_{end.numerator}_{end.denominator}.json').write_bytes(
            json.dumps(cert,sort_keys=True,separators=(',',':'),allow_nan=False).encode())
    (out/'manifest_report.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
    print(json.dumps(dict(status=report['status'],world_slabs=len(certs),
         native_picard_subslabs_replayed=report['native_picard_subslabs_replayed'],
         sc_certified=False,output=str(out)),indent=2))

if __name__=='__main__':main()
