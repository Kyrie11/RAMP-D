#!/usr/bin/env python3
"""High-precision random-corner falsification audit for footprint projections."""
from __future__ import annotations
import argparse,json,math,random
from fractions import Fraction
from pathlib import Path
import mpmath as mp
from rampd_core import Interval,StateBounds
from rampd_core.footprint import VehicleGeometry,SweptFootprint

def exact(x):
    n,d=float(x).as_integer_ratio(); return mp.mpf(n)/d

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--output',required=True); ap.add_argument('--samples',type=int,default=2000); ap.add_argument('--seed',type=int,default=9317); args=ap.parse_args()
    if args.samples<1: raise SystemExit('samples must be positive')
    mp.mp.dps=100; rng=random.Random(args.seed)
    state=StateBounds(Interval(-2,2),Interval(-1,1),Interval(-0.65,0.7),Interval.point(0),Interval.point(0),Interval.point(0))
    geom=VehicleGeometry(4.7,1.95,0.35,0.02)
    f=SweptFootprint(state,geom,Fraction(0),Fraction(1,10),'audit')
    half_length=exact(geom.length_m)/2
    half_width=exact(geom.width_m)/2
    axes=((1.0,0.0),(0.0,1.0),(0.6,0.8),(-0.8,0.6),(0.31,-0.91))
    misses=0; checks=0
    for _ in range(args.samples):
        px=rng.uniform(-2,2); py=rng.uniform(-1,1); psi=rng.uniform(-0.65,0.7)
        c,s=mp.cos(exact(psi)),mp.sin(exact(psi))
        cx=exact(px)+c*exact(geom.center_offset_x_m)-s*exact(geom.center_offset_y_m)
        cy=exact(py)+s*exact(geom.center_offset_x_m)+c*exact(geom.center_offset_y_m)
        for xi in (-half_length,half_length):
            for eta in (-half_width,half_width):
                x=cx+c*exact(xi)-s*exact(eta); y=cy+s*exact(xi)+c*exact(eta)
                for axis in axes:
                    p=exact(axis[0])*x+exact(axis[1])*y; q=f.projection(axis)
                    checks+=1
                    if not (exact(q.lo)<=p<=exact(q.hi)): misses+=1
    out=dict(audit='high_precision_corner_containment_falsification',seed=args.seed,samples=args.samples,checked_projections=checks,misses=misses,containment_fraction=(checks-misses)/checks,mpmath_dps=mp.mp.dps,claim='falsification_only_not_a_proof')
    p=Path(args.output); p.parent.mkdir(parents=True,exist_ok=True); p.write_text(json.dumps(out,indent=2)+'\n'); print(json.dumps(out,indent=2))
    if misses: raise SystemExit('footprint projection audit found misses')
if __name__=='__main__': main()
