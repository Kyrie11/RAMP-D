#!/usr/bin/env python3
"""A dynamics-only demo. No dataset, simulator, or GPU is used."""
import argparse
import json
from rampd_core import (StateBounds, ControlBounds, BicycleParameters, integrate,
                        TubeStatus, replay_certificate, backend_name, build_info)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="reports/demo_certificate.json")
    args = parser.parse_args()
    initial = StateBounds.point([0, 0, 0, 8, 0, 0])
    result = integrate(initial, ControlBounds.point(0, 0), BicycleParameters(2.8, .9), 1.0)
    result.save(args.output)
    replay = replay_certificate(args.output)
    print(json.dumps(dict(status=result.status.value, reason=result.reason,
                          backend=backend_name(), build=build_info(),
                          accepted_steps=len(result.segments),
                          exact_horizon_covered=str(result.validated_until),
                          final_px=None if result.endpoint is None else [result.endpoint.px.lo,result.endpoint.px.hi],
                          includes_analytic_px_8m=result.endpoint is not None and result.endpoint.px.contains(8),
                          witness_replay=replay.ok, full_support_safety_verified=False,
                          certificate=args.output), indent=2))
    return 0 if result.status == TubeStatus.VALIDATED and replay.ok else 1

if __name__ == "__main__":
    raise SystemExit(main())
