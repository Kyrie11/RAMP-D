#!/usr/bin/env python3
"""Local Phase 3 synthesis, closed graph, rational execution and failure audit."""
import argparse
import json
from pathlib import Path

from rampd_core import RecoveryKind, save_backup_graph, load_backup_graph
from rampd_core.backup import BackupContract, ASSURANCE_SCOPE
from rampd_core.phase3_examples import (benchmark_contract, build_braking_graph,
    execute_braking_graph, run_template_example, expected_failures)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', required=True)
    parser.add_argument('--graph', required=True)
    parser.add_argument('--trace', required=True)
    parser.add_argument('--config', default='configs/backup_benchmark.json')
    args = parser.parse_args()
    base = BackupContract.from_dict(json.loads(Path(args.config).read_text()))
    graph, searches = build_braking_graph(base)
    save_backup_graph(graph, args.graph)
    replayed = load_backup_graph(args.graph, expected_contract_digest=base.digest)
    trace, stop_v, stop_a = execute_braking_graph(replayed, steps=20)
    Path(args.trace).write_text(json.dumps({'scope': ASSURANCE_SCOPE,
        'audit': 'exact_rational_nominal_straight_dynamics', 'trace': trace}, indent=2)+'\n')
    rows = []
    for kind in RecoveryKind:
        result, _, _, _ = run_template_example(kind, base)
        chosen = result.selected
        rows.append({'kind': kind.value, 'status': result.status,
                     'candidate_count': len(result.attempts), 'accepted_candidates': len(result.choices),
                     'selected_has_feedback': bool(chosen and any(k != 0 for row in chosen.law.gain for k in row)),
                     'reserve_lower': None if chosen is None else chosen.reserve_lower,
                     'synthesis_s': result.elapsed_s,
                     'attempts': list(result.attempts)})
    failures = expected_failures(base)
    success = (len(replayed.nodes) == 17 and stop_v and stop_a and
               all(r['status'] == 'SYNTHESIZED_LOCAL' for r in rows) and
               all(c['expected_rejection'] for c in failures))
    report = {'status': 'PHASE3_LOCAL_DEMO_PASS' if success else 'PHASE3_LOCAL_DEMO_FAILED',
              'assurance_scope': ASSURANCE_SCOPE, 'full_support_certified': False,
              'contract_digest': base.digest,
              'brake_graph': {'retained_nodes': len(replayed.nodes), 'graph_replay': True,
                  'execution_steps': len(trace), 'exact_terminal_v_zero': stop_v,
                  'exact_terminal_a_zero': stop_a, 'stop_displacement_m': trace[15]['px_m'],
                  'nominal_stop_time_s': trace[15]['time_s'],
                  'hidden_modes_per_node': 2, 'observation_label': 'silence',
                  'synthesis_candidate_count': sum(len(r.attempts) for r in searches),
                  'synthesis_s': sum(r.elapsed_s for r in searches)},
              'templates': rows, 'failure_cases': failures}
    Path(args.output).write_text(json.dumps(report, indent=2, allow_nan=False)+'\n')
    print(json.dumps(report, indent=2))
    if not success:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
