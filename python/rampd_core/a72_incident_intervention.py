"""Tie real-world operator reports to separately parameterized SIMULATED rule events.

The source report supplies a scenario prior/category, NEVER an observed
physical effective timestamp or a vehicle receipt timestamp.
"""
from __future__ import annotations
from fractions import Fraction as Q
from hashlib import sha256
import json


def make_report_conditioned_simulation(report, *,sim_world_id,rule_effective_at:Q,
      public_issue_at:Q,public_receive_at:Q,authority_id,resource_id):
    if report.get('source_family')!='511NY' or report.get('status')!='DESCRIPTIVE_REPORT_TIMES_ONLY':
        raise ValueError('only valid operator reports as prior')
    if not all(type(t) is Q and t>=0 for t in (rule_effective_at,public_issue_at,public_receive_at)):
        raise ValueError('explicit nonnegative rational simulator clocks required')
    if public_receive_at<public_issue_at:raise ValueError('receipt before message issue')
    if not all(type(s) is str and s for s in (sim_world_id,authority_id,resource_id)):
        raise ValueError('explicit simulated authority and metric resource reference required')
    if report.get('physical_rule_effective_at') is not None or report.get('vehicle_received_at') is not None:
        raise ValueError('untrusted report pretending to be physical event source')
    source_hash=sha256(json.dumps(report,sort_keys=True,ensure_ascii=False,allow_nan=False).encode()).hexdigest()
    return dict(schema='rampd.a72.report_conditioned_simulator_event.v1',
        status='SYNTHETIC_INTERVENTION_CONTRACT_NOT_AN_OBSERVED_RULE',
        scenario_id=sim_world_id,auxiliary_report_sha256=source_hash,
        report_category_prior=report.get('event_type_as_reported'),
        rule_effective_at=str(rule_effective_at),public_issue_at=str(public_issue_at),
        public_receive_at=str(public_receive_at),simulated_authority=authority_id,
        simulated_metric_resource_ref=resource_id,
        effectivity_generated_by_simulator_not_511ny=True,
        actual_traffic_controller_ack_proved=False,hidden_world_complete=False,
        causal_pair_observed=False,all_eight_formal_label_masks_zero=True)
