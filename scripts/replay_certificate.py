#!/usr/bin/env python3
import argparse
import json
from dataclasses import asdict
from rampd_core import replay_certificate

if __name__ == "__main__":
    p=argparse.ArgumentParser()
    p.add_argument("certificate")
    a=p.parse_args()
    report=replay_certificate(a.certificate)
    print(json.dumps(asdict(report),indent=2))
    raise SystemExit(0 if report.ok else 1)
