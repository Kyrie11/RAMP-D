"""Reproducible synthetic Phase 3 fixtures; not traffic-protocol simulations."""
from __future__ import annotations

from dataclasses import replace
from fractions import Fraction
import math

from .interval import Interval
from .model import StateBounds, ControlBounds
from .belief import SupportAtom, BeliefCell
from .vehicle import commonroad_bmw_320i_benchmark
from .invariant import SafeDomain
from .control import RecoveryKind, SampledFeedbackLaw, recovery_candidates, ZERO_GAIN
from .backup import (BackupContract, LocalEvidenceStore, validate_feedback_step,
                     synthesize_backup, StaticObstacle)
from .backup_graph import build_backup_graph, BackupExecutor


def benchmark_contract():
    vehicle = replace(commonroad_bmw_320i_benchmark(), friction_coefficient=0.6)
    domain = SafeDomain(StateBounds(Interval(-50, 100), Interval(-4, 7),
                                   Interval(-0.7, 0.7), Interval(-0.25, 8),
                                   Interval(-3, 2), Interval(-0.45, 0.45)),
                        allowed_modes=(("rule", ("open", "closed")),),
                        required_mode_fields=("rule",), friction=vehicle.bicycle)
    return BackupContract("phase3_bmw_nominal_static_benchmark_v1", domain, vehicle.bicycle,
                          ControlBounds(Interval(-2, 2), Interval(-0.35, 0.35)),
                          vehicle.geometry, 0.25, Interval(-60, 120), Interval(-2.5, 5.5),
                          measurement_error=(Interval(-1e-9, 1e-9), Interval(-1e-9, 1e-9)) +
                                            (Interval(0, 0),) * 4,
                          gate_front_x=15.0)


def joint_cell(cell_id, ego):
    return BeliefCell(cell_id, tuple(SupportAtom(f"{cell_id}:{mode}", ego,
                                               mode=(("rule", mode),))
                                    for mode in ("open", "closed")))


def constant_law(name, jerk, contract, kind=RecoveryKind.BRAKE_TO_STOP):
    return SampledFeedbackLaw(name, kind, (jerk, 0.0), ZERO_GAIN, (0.0,) * 6,
                              contract.control_limits)


def build_braking_graph(contract=None):
    """4 m/s, a=0, jerk -1 for 2 s then +1 for 2 s; terminal hold loop.

    This exact nominal straight profile stops with v=a=0 and travels 8 m.
    Candidate evidence is still obtained from full Picard tubes, analytic
    intersections, swept-body checks and context-bound independent replay.
    It is deliberately a zero-disturbance invariant fixture. Nonzero errors
    are exercised separately and are never rounded away to force a hold loop.
    """
    contract = contract or benchmark_contract()
    if any(w != Interval(0, 0) for w in contract.derivative_disturbance):
        raise ValueError("the exact-stop invariant fixture requires zero process disturbance")
    if contract.decision_period_s != 0.25:
        raise ValueError("the reproducible 16-step fixture uses h=0.25")
    state = StateBounds.point((0, 0, 0, 4, 0, 0))
    cells = [joint_cell("B00", state)]
    intended = []
    for i in range(16):
        jerk = -1.0 if i < 8 else 1.0
        law = constant_law(f"brake_profile_{i:02d}", jerk, contract)
        check = validate_feedback_step(cells[-1].atoms[0], law, contract)
        if check.status != "VALIDATED_LOCAL":
            raise RuntimeError(f"brake profile generation failed at {i}: {check.reason}")
        intended.append(jerk)
        cells.append(joint_cell(f"B{i+1:02d}", check.endpoint))
    # This nonzero public K acts only on measured v/a/psi/delta, all zero
    # on the terminal support. Position uncertainty is retained unchanged.
    hold = SampledFeedbackLaw("terminal_hold_feedback", RecoveryKind.HOLD_BEFORE_GATE,
            (0, 0), ((0, 0, 0, -1, -2, 0), (0, 0, -0.4, 0, 0, -1.5)),
            (8, 0, 0, 0, 0, 0), contract.control_limits)
    store = LocalEvidenceStore(contract)
    reports = []
    populated = []
    for i, cell in enumerate(cells):
        if i < 16:
            j = intended[i]
            candidates = tuple(constant_law(f"brake_{i:02d}_candidate_{q}", value, contract)
                               for q, value in enumerate((j, j*0.5, 0.0)))
            target = cells[i+1]
        else:
            candidates = (hold, constant_law("unsafe_continue_braking", -1, contract))
            target = cells[-1]
        result = synthesize_backup(cell, candidates, (target,), store)
        if result.selected is None:
            raise RuntimeError(f"no executable candidate at {cell.cell_id}: {result.attempts}")
        populated.append(replace(cell, actions=result.actions))
        reports.append(result)
    graph = build_backup_graph(populated, store)
    if len(graph.nodes) != 17:
        raise RuntimeError("brake/hold graph is not closed under every observation")
    return graph, tuple(reports)


def _fraction_interval(value):
    q = Fraction(value)
    approximate = float(q)
    exact_float = Fraction.from_float(approximate)
    return Interval(math.nextafter(approximate, -math.inf) if exact_float > q else approximate,
                    math.nextafter(approximate, math.inf) if exact_float < q else approximate)


def execute_braking_graph(graph, steps=20):
    """Exact-rational straight dynamics audit, separate from the proof engine."""
    source = graph.node_map["B00"].cell
    executor = BackupExecutor(graph, "B00", source, expected_contract_digest=graph.contract_digest)
    x, v, a = map(Fraction, (0, 4, 0))
    h = Fraction.from_float(graph.evidence.contract.decision_period_s)
    trace = []
    for index in range(steps):
        measurement = (float(x), 0, 0, float(v), float(a), 0)
        control = executor.command(measurement, at_time=executor.time)
        j = Fraction.from_float(control[0])
        if control[1] != 0:
            raise RuntimeError("straight rational audit does not support steering")
        x, v, a = x + v*h + a*h*h/2 + j*h*h*h/6, v+a*h+j*h*h/2, a+j*h
        support = joint_cell(f"realized:{index}", StateBounds(
            _fraction_interval(x), Interval(0, 0), Interval(0, 0),
            _fraction_interval(v), _fraction_interval(a), Interval(0, 0)))
        child = executor.advance("silence", support, at_time=executor.next_time)
        trace.append({"step": index+1, "time_s": float(executor.time), "cell_id": child,
                      "control": list(control), "px_m": float(x), "v_mps": float(v),
                      "a_mps2": float(a), "px_exact": str(x), "v_exact": str(v),
                      "a_exact": str(a)})
    return trace, v == 0, a == 0


def template_problem(kind, base=None):
    """One bounded-error recovery step plus explicit terminal-support target.

    The target is a local physical objective, not legal permission to merge.
    Hidden rule labels remain together under the single silence observation.
    """
    kind = RecoveryKind(kind)
    base = base or benchmark_contract()
    error = list(base.measurement_error)
    error[3], error[4] = Interval(-0.01, 0.01), Interval(-0.01, 0.01)
    disturbance = (Interval(-0.005, 0.005), Interval(0, 0), Interval(0, 0),
                   Interval(-0.02, 0.02), Interval(-0.04, 0.04), Interval(0, 0))
    contract = replace(base, contract_id="phase3_bounded_error_" + kind.value,
                       derivative_disturbance=disturbance, measurement_error=tuple(error),
                       gate_front_x=30.0)
    if kind is RecoveryKind.BRAKE_TO_STOP:
        initial = StateBounds(Interval(-0.01, 0.01), Interval(0, 0), Interval(0, 0),
                              Interval(2.995, 3.005), Interval(0, 0), Interval(0, 0))
        reference = (0, 0, 0, 0, 0, 0)
        target = StateBounds(Interval(0.65, 0.85), Interval(-0.01, 0.01), Interval(-0.01, 0.01),
                             Interval(2.8, 2.9999), Interval(-0.6, -0.01), Interval(-0.01, 0.01))
        biases, scales = (0.0,), (0.5, 0.75)
    elif kind is RecoveryKind.HOLD_BEFORE_GATE:
        initial = StateBounds(Interval(-0.01, 0.01), Interval(0, 0), Interval(0, 0),
                              Interval(-0.005, 0.005), Interval(-0.005, 0.005), Interval(0, 0))
        reference = (0, 0, 0, 0, 0, 0)
        target = StateBounds(Interval(-0.05, 0.05), Interval(-0.01, 0.01), Interval(-0.01, 0.01),
                             Interval(-0.025, 0.025), Interval(-0.04, 0.04), Interval(-0.01, 0.01))
        biases, scales = (0.0,), (0.5,)
    elif kind is RecoveryKind.YIELD:
        initial = StateBounds(Interval(-0.01, 0.01), Interval(0, 0), Interval(0, 0),
                              Interval(1.995, 2.005), Interval(0, 0), Interval(0, 0))
        reference = (0, 0, 0, 0.5, 0, 0)
        target = StateBounds(Interval(0.4, 0.6), Interval(-0.01, 0.01), Interval(-0.01, 0.01),
                             Interval(1.8, 1.9999), Interval(-0.5, -0.01), Interval(-0.01, 0.01))
        biases, scales = (0.0,), (0.5, 0.75)
    else:
        initial = StateBounds(Interval(-0.005, 0.005), Interval(0, 0), Interval(0, 0),
                              Interval(1.995, 2.005), Interval(0, 0), Interval(0, 0))
        reference = (0, 3.5, 0, 2, 0, 0)
        target = StateBounds(Interval(0.4, 0.6), Interval(0.00001, 0.05), Interval(0.001, 0.03),
                             Interval(1.95, 2.05), Interval(-0.05, 0.05), Interval(0.01, 0.1))
        biases, scales = (0.0,), (0.5,)
    source = joint_cell("template:" + kind.value, initial)
    target = joint_cell("target:" + kind.value, target)
    candidates = recovery_candidates(kind, reference, contract.control_limits,
                                      jerk_biases=biases, gain_scales=scales)
    return source, candidates, (target,), LocalEvidenceStore(contract)


def run_template_example(kind, base=None):
    source, candidates, targets, store = template_problem(kind, base)
    result = synthesize_backup(source, candidates, targets, store)
    return result, store, source, targets


def expected_failures(base=None):
    base = base or benchmark_contract()
    atom = joint_cell("failure", StateBounds.point((0, 0, 0, 4, 0, 0))).atoms[0]
    law = constant_law("failure_brake", -1, base)
    cases = []
    for name, contract in (
        ("gate_inside_swept_body", replace(base, gate_front_x=3.0)),
        ("blocked_static_corridor", replace(base, obstacles=(
            StaticObstacle("blocked", StateBounds.point((1, 0, 0, 0, 0, 0)), base.geometry),))),
        ("friction_not_available", replace(base,
            params=replace(base.params, friction_coefficient=0.001),
            domain=replace(base.domain, friction=replace(base.params, friction_coefficient=0.001)))),
    ):
        check = validate_feedback_step(atom, law, contract)
        cases.append({"name": name, "status": check.status, "reason": check.reason,
                      "expected_rejection": check.status == "UNKNOWN"})
    # A disturbed exact stationary point cannot be turned into a self-loop by
    # declaring v=0 or clipping negative speed. The posterior must fit exactly.
    stationary = joint_cell("no_robust_point_hold", StateBounds.point((0, 0, 0, 0, 0, 0)))
    disturbed = replace(base, derivative_disturbance=(Interval(0, 0),) * 4 +
                        (Interval(-0.05, 0.05), Interval(0, 0)))
    store = LocalEvidenceStore(disturbed)
    result = synthesize_backup(stationary,
        (constant_law("zero", 0, disturbed, RecoveryKind.HOLD_BEFORE_GATE),), (stationary,), store)
    cases.append({"name": "disturbed_point_hold_not_invariant", "status": result.status,
                  "reason": result.attempts[0]["reason"],
                  "expected_rejection": not result.choices})
    return cases
