#!/usr/bin/env python3
"""Deterministic workload comparison for fixed-step and width-adaptive tubes.

Timing is descriptive and is not a correctness gate. All methods use the same
initial support, dynamics, control, horizon and MPFR backend. The adaptive
method must satisfy its configured per-coordinate local tube-width limits.
"""
from __future__ import annotations
import argparse
import csv
import json
import statistics
import time
from pathlib import Path
from rampd_core import (BicycleParameters, ControlBounds, Interval, PicardOptions,
                        StateBounds, TubeStatus, integrate, state_box_widths)
from rampd_core.certificate import to_dict, replay_certificate


def _case():
    initial = StateBounds(Interval(0, 0), Interval(0, 0), Interval(-.03, .03),
                          Interval(7.9, 8.1), Interval(0, 0), Interval(0, 0))
    control = ControlBounds.point(0, 0)
    params = BicycleParameters(2.8, .9)
    return initial, control, params, .8


def _run(name, options, repeats):
    initial, control, params, horizon = _case()
    durations=[]; last=None
    for _ in range(repeats):
        t0=time.perf_counter()
        result=integrate(initial,control,params,horizon,options)
        durations.append(time.perf_counter()-t0)
        if result.status != TubeStatus.VALIDATED:
            raise RuntimeError(f"{name} did not validate: {result.reason}; stats={result.stats}")
        last=result
    assert last is not None
    widths=[state_box_widths(seg.witness.tube) for seg in last.segments]
    max_widths=[float(max(row[i] for row in widths)) for i in range(6)]
    replay=replay_certificate(to_dict(last))
    if not replay.ok:
        raise RuntimeError(f"{name} witness replay failed: {replay.reason}")
    if options.max_tube_widths is not None:
        if any(w > cap for w,cap in zip(max_widths,options.max_tube_widths)):
            raise RuntimeError(f"{name} violated its width policy")
    return {
        "method":name,
        "status":last.status.value,
        "accepted_steps":last.stats["accepted_steps"],
        "attempts":last.stats["attempts"],
        "total_subdivisions":last.stats["subdivisions"],
        "schedule_subdivisions":last.stats["schedule_subdivisions"],
        "failure_subdivisions":last.stats["failure_subdivisions"],
        "width_subdivisions":last.stats["width_subdivisions"],
        "width_rejections":last.stats["width_rejections"],
        "max_tube_widths":max_widths,
        "max_accepted_width_ratio":last.stats["max_accepted_width_ratio"],
        "median_wall_time_s":statistics.median(durations),
        "timing_samples_s":durations,
        "witness_replay":replay.ok,
        "witness_segments_replayed":replay.checked_segments,
        "width_limits":options.max_tube_widths,
    }


def run_benchmark(repeats=5):
    if repeats < 1: raise ValueError("repeats must be positive")
    coarse=PicardOptions(max_step_s=.4)
    fine=PicardOptions(max_step_s=.025)
    adaptive=PicardOptions(max_step_s=.4,
        max_tube_widths=(2.2,.8,.1,.3,.1,.01),
        max_depth=20,max_steps=10000,max_attempts=20000,max_width_subdivisions=10000)
    rows=[_run("fixed_coarse_no_width_cap",coarse,repeats),
          _run("fixed_fine_no_width_cap",fine,repeats),
          _run("adaptive_width_cap",adaptive,repeats)]
    by={r["method"]:r for r in rows}
    if by["adaptive_width_cap"]["width_subdivisions"] <= 0:
        raise RuntimeError("benchmark did not exercise width-triggered subdivision")
    if by["adaptive_width_cap"]["accepted_steps"] <= by["fixed_coarse_no_width_cap"]["accepted_steps"]:
        raise RuntimeError("adaptive workload did not refine the coarse schedule")
    return {
        "benchmark":"phase1c_fixed_vs_adaptive_width",
        "classification":"deterministic_synthetic_numerical_benchmark_not_vehicle_experiment",
        "seed":None,
        "initial_support":"psi=[-0.03,0.03] rad; v=[7.9,8.1] m/s; other coordinates point",
        "control":"j=0; steering_rate=0",
        "horizon_s":.8,
        "wheelbase_m":2.8,
        "repeats":repeats,
        "rows":rows,
        "interpretation":"Width caps constrain local enclosure box diameters. They do not assert physical safety or reduce true uncertainty; inability to meet a cap must return UNKNOWN.",
    }


if __name__=="__main__":
    ap=argparse.ArgumentParser()
    ap.add_argument("--output",default="reports/phase1c_benchmark.json")
    ap.add_argument("--repeats",type=int,default=5)
    args=ap.parse_args()
    report=run_benchmark(args.repeats)
    out=Path(args.output); out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(report,indent=2,allow_nan=False)+"\n",encoding="utf-8")
    csv_path=out.with_suffix(".csv")
    with csv_path.open("w",newline="",encoding="utf-8") as f:
        writer=csv.DictWriter(f,fieldnames=["method","status","accepted_steps","attempts","total_subdivisions","width_subdivisions","width_rejections","median_wall_time_s","max_tube_widths"])
        writer.writeheader()
        for row in report["rows"]:
            writer.writerow({k:row[k] for k in writer.fieldnames})
    print(json.dumps(report,indent=2))
    print(f"CSV={csv_path}")
