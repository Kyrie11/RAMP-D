#!/usr/bin/env python3
"""Dependency-light static self-test; does not require CARLA or MARSHAL imports."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from rapid_ad.design import build_design, write_design  # noqa: E402
from scripts.analyze_results import interaction_estimates, overall_failure, is_causal_valid  # noqa: E402


def main() -> int:
    smoke = build_design("smoke", [0])
    core = build_design("core", [0])
    full = build_design("all", [0])
    assert len(smoke) == 14, len(smoke)
    assert len(core) == 32, len(core)
    assert len(full) == 32, len(full)
    assert len({c["case_id"] for c in full}) == len(full)
    assert {c["gap_timing"] for c in full} == {"none", "pre", "overlap", "post"}
    assert sum(c["task"] == "go_to_stop" for c in core) == 16
    assert sum(c["task"] == "stop_to_go" for c in core) == 16
    assert sum(bool(c["control_transition"]) for c in core) == 16

    # Static STOP has no release event; absence of a resume must not be a stale-retention failure.
    static_stop = {
        "case": {"task": "stop_to_go", "control_transition": False},
        "failure_type": "ok", "unsafe_crossing_while_stop": False,
        "resume_latency_s": None, "resume_within_allowance": None,
    }
    assert not overall_failure(static_stop)

    # Final causal analysis can require manual cue/mask audit for dynamic transitions.
    dynamic = {"schema_version": 3, "transition_expected": True, "valid_for_causal_analysis": True, "_require_visual_audit": True, "_visual_audit_pass": False}
    assert not is_causal_valid(dynamic)
    dynamic["_visual_audit_pass"] = True
    assert is_causal_valid(dynamic)
    static_placebo = {"valid_for_causal_analysis": True, "transition_expected": False, "_require_visual_audit": True, "_visual_audit_pass": False}
    assert is_causal_valid(static_placebo)

    # A complete matched factorial should produce interaction rows; one block is flagged underpowered.
    synthetic = []
    for task, phases in (("go_to_stop", ("early", "late")), ("stop_to_go", ("short_wait", "long_wait"))):
        for transition in (False, True):
            for phase in phases:
                for gap in ("none", "pre", "overlap", "post"):
                    synthetic.append({
                        "schema_version": 3, "controller": "synthetic", "_run_tag": "selftest",
                        "case": {"task": task, "control_transition": transition, "phase": phase,
                                 "gap_timing": gap, "seed": 0},
                        "setup_valid": True, "exposure_valid": True,
                        "valid_for_safety_analysis": True, "valid_for_liveness_analysis": True,
                        "valid_for_causal_analysis": True, "failure_type": "ok",
                        "unsafe_crossing_while_stop": False, "avoidable_failure_estimated": False,
                    })
    estimates = interaction_estimates(synthetic, bootstrap_samples=50)
    assert estimates and all(row["underpowered_warning"] for row in estimates)

    temp = ROOT / "_selftest_output"
    write_design(smoke, temp)
    manifest = json.loads((temp / "manifest.json").read_text(encoding="utf-8"))
    assert len(manifest) == 14
    print("RAPID-AD v3 self-test passed: smoke=14 core=32 full-factorial cells/seed=32")
    print("Static placebo and paired-interaction guard checks passed.")
    print(f"Temporary manifest: {temp / 'manifest.csv'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
