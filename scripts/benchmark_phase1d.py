#!/usr/bin/env python3
"""Synthetic conservative swept-footprint broad/narrow-phase benchmark."""
from __future__ import annotations
import argparse, json, math, statistics, time
from fractions import Fraction
from pathlib import Path
from rampd_core import Interval, StateBounds
from rampd_core.footprint import (VehicleGeometry, SweptFootprint,
    SeparationStatus, candidate_axes, separate_swept_footprints,
    save_separation_certificate, replay_separation_certificate)


def make_case():
    theta = math.pi / 4.0
    nx, ny = -math.sin(theta), math.cos(theta)
    a = SweptFootprint(StateBounds.point((0,0,theta,0,0,0)),
        VehicleGeometry(4.0,0.2),Fraction(0),Fraction(1,5),"ego")
    b = SweptFootprint(StateBounds.point((1.5*nx,1.5*ny,theta,0,0,0)),
        VehicleGeometry(4.0,0.2),Fraction(0),Fraction(1,5),"agent")
    return a,b


def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--output',required=True)
    ap.add_argument('--repeats',type=int,default=5); ap.add_argument('--iterations',type=int,default=100)
    args=ap.parse_args()
    if args.repeats<1 or args.iterations<1: raise SystemExit('positive repeats/iterations required')
    a,b=make_case()
    default=candidate_axes(a,b)
    dense=tuple((math.cos(2*math.pi*k/16),math.sin(2*math.pi*k/16)) for k in range(16))+default
    methods=[('aabb_only',((1.0,0.0),(0.0,1.0))),('oriented_candidate_axes',default),('dense_16_plus_oriented',dense)]
    rows=[]
    for name,axes in methods:
        samples=[]; result=None
        for _ in range(args.repeats):
            t0=time.perf_counter()
            for _ in range(args.iterations): result=separate_swept_footprints(a,b,axes)
            samples.append((time.perf_counter()-t0)/args.iterations)
        replay=False
        if result.status is SeparationStatus.SEPARATED:
            cert=Path(args.output).with_name(name+'_separation.json')
            save_separation_certificate(a,b,result,cert)
            replay=replay_separation_certificate(cert).ok
        rows.append(dict(method=name,status=result.status.value,axes_tested=result.axes_tested,
                         median_seconds=statistics.median(samples),samples_seconds=samples,
                         clearance_lower_m=None if result.witness is None else result.witness.clearance_lower_m,
                         witness_replay=replay))
    expected={'aabb_only':'UNKNOWN','oriented_candidate_axes':'SEPARATED','dense_16_plus_oriented':'SEPARATED'}
    for row in rows:
        if row['status']!=expected[row['method']]: raise SystemExit(f"unexpected status: {row}")
        if row['status']=='SEPARATED' and not row['witness_replay']: raise SystemExit(f"witness replay failed: {row}")
    out=dict(benchmark='phase1d_swept_footprint_axes',
             classification='synthetic_geometry_microbenchmark_not_vehicle_experiment',
             time_interval_exact=['0','1/5'], geometry={'length_m':4.0,'width_m':0.2},
             repeats=args.repeats,iterations_per_repeat=args.iterations,rows=rows,
             interpretation='AABB overlap is UNKNOWN; a strict outward support-projection gap proves swept-set separation. UNKNOWN is not collision.')
    p=Path(args.output); p.parent.mkdir(parents=True,exist_ok=True); p.write_text(json.dumps(out,indent=2)+'\n')
    print(json.dumps(out,indent=2))
if __name__=='__main__': main()
