#!/usr/bin/env python3
"""Finite local-law synthesis timing; no real-time/full-system performance claim."""
import argparse
import json
import statistics
import math
from pathlib import Path
from rampd_core import RecoveryKind
from rampd_core.phase3_examples import run_template_example


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', required=True)
    parser.add_argument('--repeats', type=int, default=3)
    args = parser.parse_args()
    if args.repeats < 1:
        raise SystemExit('repeats must be positive')
    rows = []
    for kind in RecoveryKind:
        results = [run_template_example(kind)[0] for _ in range(args.repeats)]
        values = sorted(r.elapsed_s for r in results)
        rows.append({'kind': kind.value,
            'status': 'SYNTHESIZED_LOCAL' if all(r.status == 'SYNTHESIZED_LOCAL' for r in results) else 'FAILED',
            'repeats': args.repeats, 'median_s': statistics.median(values),
            'p95_s': values[math.ceil(0.95*len(values))-1],
            'candidates': len(results[-1].attempts), 'accepted': len(results[-1].choices),
            'classification': 'offline_finite_common_law_search_local_static_scene'})
    payload = {'benchmark': 'phase3_local_public_backup_synthesis', 'rows': rows,
               'full_support_certified': False,
               'note': 'p95 is nearest-rank over the listed few repeats, not a driving latency estimate'}
    Path(args.output).write_text(json.dumps(payload, indent=2)+'\n')
    print(json.dumps(payload, indent=2))
    if any(row['status'] != 'SYNTHESIZED_LOCAL' for row in rows):
        raise SystemExit(1)


if __name__ == '__main__':
    main()
