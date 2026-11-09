"""Validated Picard substeps, exact dyadic scheduling and failure-only bisection.

VALIDATED is a flow-enclosure result, NOT the full-support verifier's CERTIFIED.
A control box is an overapproximation of all measurable control signals within
that box. It does not implement hidden-state-dependent control selection.
"""
from __future__ import annotations
import ctypes as C
from dataclasses import dataclass, field
from enum import Enum
from fractions import Fraction
import math
import time
from .interval import Interval, _LIB, _D, _P, _arrays, _read_pair, _check, backend_name, build_info
from .model import StateBounds, ControlBounds, BicycleParameters, rhs

class TubeStatus(str, Enum):
    VALIDATED = "VALIDATED"
    UNKNOWN = "UNKNOWN"

@dataclass(frozen=True)
class PicardOptions:
    max_iterations: int = 16
    relative_inflation: float = 0.125
    # SI units of the six state coordinates. Search pads, NOT error tolerances.
    absolute_inflation: tuple[float, ...] = (1e-9,) * 6
    max_step_s: float = 0.05
    min_step_s: float = 1e-7
    max_depth: int = 20
    max_steps: int = 10000
    max_attempts: int = 20000
    time_limit_s: float | None = None
    # Per-coordinate upper bounds on the complete local state-box width.
    # Units: m, m, rad, m/s, m/s^2, rad. None disables width adaptation.
    max_tube_widths: tuple[float, ...] | None = None
    # Separate budget for bisections caused by a validated-but-too-wide tube.
    max_width_subdivisions: int = 10000
    def __post_init__(self):
        for name in ("max_iterations", "max_depth", "max_steps", "max_attempts", "max_width_subdivisions"):
            v = getattr(self, name)
            if isinstance(v, bool) or not isinstance(v, int):
                raise ValueError(f"{name} must be an integer")
        if not 1 <= self.max_iterations <= 1000 or not 0 <= self.max_depth <= 60:
            raise ValueError("invalid iteration/depth limits")
        if self.max_steps < 1 or self.max_attempts < 1 or self.max_width_subdivisions < 0:
            raise ValueError("positive step/attempt budgets and nonnegative width-split budget required")
        pads = tuple(float(x) for x in self.absolute_inflation)
        if len(pads) != 6 or any(not math.isfinite(v) or v <= 0 for v in pads):
            raise ValueError("six positive finite absolute inflation pads required")
        object.__setattr__(self, "absolute_inflation", pads)
        if not math.isfinite(self.relative_inflation) or self.relative_inflation < 0:
            raise ValueError("relative_inflation must be finite and nonnegative")
        if self.max_tube_widths is not None:
            limits = tuple(float(x) for x in self.max_tube_widths)
            if len(limits) != 6 or any(not math.isfinite(x) or x <= 0 for x in limits):
                raise ValueError("max_tube_widths must contain six positive finite SI width limits")
            object.__setattr__(self, "max_tube_widths", limits)
        for name in ("max_step_s", "min_step_s", "time_limit_s"):
            v = getattr(self, name)
            if v is None and name == "time_limit_s": continue
            if v is None or not math.isfinite(v) or v <= 0:
                raise ValueError(f"{name} must be finite and positive")

class _Options(C.Structure):
    _fields_ = [("max_iterations", C.c_int), ("relative_inflation", _D), ("absolute_inflation", _D * 6)]

class _Output(C.Structure):
    _fields_ = [("status", C.c_int), ("iterations", C.c_int)] + [
        (name, _D * 6) for name in ("tube_lo", "tube_hi", "field_lo", "field_hi",
                                  "picard_lo", "picard_hi", "endpoint_lo", "endpoint_hi", "inclusion_margin_lo")]

_LIB.rampd_picard_step.argtypes = [_P, _P, _P, _P, _P, _P, _D, _D, C.POINTER(_Options), C.POINTER(_Output)]
_LIB.rampd_picard_step.restype = C.c_int

@dataclass(frozen=True)
class StepWitness:
    initial: StateBounds
    duration_s: float
    tube: StateBounds
    field: tuple[Interval, ...]
    picard_image: StateBounds
    endpoint: StateBounds
    inclusion_margin_lo: tuple[float, ...]
    iterations: int

@dataclass(frozen=True)
class StepResult:
    status: TubeStatus
    reason: str
    iterations: int
    witness: StepWitness | None = None

@dataclass(frozen=True)
class TubeSegment:
    # Exact authoritative time. Floats are for display only.
    start_time: Fraction
    depth: int
    witness: StepWitness
    @property
    def end_time(self):
        return self.start_time + Fraction.from_float(self.witness.duration_s)

@dataclass(frozen=True)
class TubeResult:
    status: TubeStatus
    reason: str
    initial: StateBounds
    control: ControlBounds
    params: BicycleParameters
    disturbance: tuple[Interval, ...]
    requested_horizon_s: float
    segments: tuple[TubeSegment, ...]
    endpoint: StateBounds | None
    stats: dict
    options: PicardOptions
    backend: str = field(default_factory=backend_name)
    native_build: str = field(default_factory=build_info)
    @property
    def validated_until(self):
        return self.segments[-1].end_time if self.segments else Fraction(0)
    @property
    def prefix_endpoint(self):
        return self.segments[-1].witness.endpoint if self.segments else self.initial
    def save(self, path):
        from .certificate import save_certificate
        save_certificate(self, path)

def _disturbance(w):
    values = (Interval(0, 0),) * 6 if w is None else tuple(w)
    if len(values) != 6 or not all(isinstance(v, Interval) for v in values):
        raise ValueError("derivative_disturbance must be six Interval objects")
    return values

def picard_step(initial: StateBounds, control: ControlBounds, params: BicycleParameters,
                duration_s: float, options: PicardOptions | None = None,
                derivative_disturbance=None) -> StepResult:
    """Attempt ONE substep. No bisection occurs inside this function."""
    opts = options or PicardOptions()
    w = _disturbance(derivative_disturbance)
    h = float(duration_s)
    if not math.isfinite(h) or h <= 0:
        raise ValueError("duration_s must be finite and positive")
    xl, xh = _arrays(initial.as_tuple()); ul, uh = _arrays(control.as_tuple()); wl, wh = _arrays(w)
    co = _Options(opts.max_iterations, opts.relative_inflation, (_D * 6)(*opts.absolute_inflation))
    out = _Output()
    _check(_LIB.rampd_picard_step(xl, xh, ul, uh, wl, wh, params.wheelbase_m, h, C.byref(co), C.byref(out)))
    reasons = {1: "ITERATION_LIMIT", 2: "MODEL_DOMAIN", 3: "NUMERIC_RANGE"}
    if out.status != 0:
        return StepResult(TubeStatus.UNKNOWN, reasons.get(out.status, "NATIVE_UNKNOWN"), out.iterations)
    witness = StepWitness(initial, h, StateBounds(*_read_pair(out.tube_lo, out.tube_hi, 6)),
                          _read_pair(out.field_lo, out.field_hi, 6),
                          StateBounds(*_read_pair(out.picard_lo, out.picard_hi, 6)),
                          StateBounds(*_read_pair(out.endpoint_lo, out.endpoint_hi, 6)),
                          tuple(out.inclusion_margin_lo), out.iterations)
    return StepResult(TubeStatus.VALIDATED, "STRICT_PICARD_INCLUSION", out.iterations, witness)

def check_witness(witness: StepWitness, control: ControlBounds, params: BicycleParameters,
                  derivative_disturbance=None) -> bool:
    """Recompute inequalities without rerunning candidate search.

    This is an independent replay of the SEARCH, not an independent arithmetic
    implementation: both paths deliberately share the directed MPFR backend.
    """
    try:
        h = float(witness.duration_s)
        if not math.isfinite(h) or h <= 0: return False
        f = rhs(witness.tube, control, params, _disturbance(derivative_disturbance))
        if len(witness.field) != 6 or len(witness.inclusion_margin_lo) != 6: return False
        for i, (z0, z, fi, fs, ps, es) in enumerate(zip(
            witness.initial.as_tuple(), witness.tube.as_tuple(), f, witness.field,
            witness.picard_image.as_tuple(), witness.endpoint.as_tuple())):
            if not fs.contains(fi): return False
            p = z0 + Interval(0, h) * fs
            e = z0 + Interval.point(h) * fs
            if not ps.contains(p) or not es.contains(e): return False
            if not z.interior_contains(ps) or not z.contains(es): return False
            margin = min((Interval.point(ps.lo) - Interval.point(z.lo)).lo,
                         (Interval.point(z.hi) - Interval.point(ps.hi)).lo)
            claimed = witness.inclusion_margin_lo[i]
            if not math.isfinite(claimed) or not 0 < claimed <= margin: return False
        return True
    except (ValueError, TypeError, RuntimeError, OverflowError):
        return False

def state_box_widths(box: StateBounds) -> tuple[Fraction, ...]:
    """Exact widths of binary64 interval endpoints, represented as rationals.

    Each endpoint is an exact IEEE-754 binary64 number. Subtracting their
    exact Fraction representations gives the exact real diameter, avoiding
    overflow/rounding in a diagnostic width calculation. These widths are
    used for adaptive quality/resource control, never as safety margins.
    """
    return tuple(Fraction.from_float(v.hi) - Fraction.from_float(v.lo)
                 for v in box.as_tuple())


def _width_exceeds(widths: tuple[Fraction, ...], limits: tuple[float, ...] | None) -> bool:
    return limits is not None and any(w > Fraction.from_float(cap) for w, cap in zip(widths, limits))


def _width_ratios(widths: tuple[Fraction, ...], limits: tuple[float, ...] | None):
    if limits is None:
        return None
    return tuple(w / Fraction.from_float(cap) for w, cap in zip(widths, limits))


def _width_report(widths):
    """JSON-safe numeric report; exact values remain in the certificate."""
    out=[]
    for width in widths:
        try:
            value=float(width)
            out.append(value if math.isfinite(value) else "OVERFLOW")
        except OverflowError:
            out.append("OVERFLOW")
    return out


def _ratio_report(ratio):
    try:
        value=float(ratio)
        return value if math.isfinite(value) else "OVERFLOW"
    except OverflowError:
        return "OVERFLOW"


def integrate(initial: StateBounds, control: ControlBounds, params: BicycleParameters,
              horizon_s: float, options: PicardOptions | None = None,
              derivative_disturbance=None) -> TubeResult:
    """Cover the complete binary64 horizon by validated dyadic substeps.

    Phase 1C adds a *quality* constraint: a locally VALIDATED Picard tube is
    accepted only when every coordinate width is within its configured SI
    bound. If it is too wide, the time interval is bisected and both children
    are revalidated from the correct propagated endpoint.

    A width-limit failure is not a physical counterexample. If budgets or the
    minimum step prevent satisfying the width policy, the result is UNKNOWN.
    Width limits do not prove collision avoidance or state safety.
    """
    opts = options or PicardOptions()
    h = float(horizon_s)
    if not math.isfinite(h) or h <= 0: raise ValueError("horizon_s must be finite and positive")
    w = _disturbance(derivative_disturbance)
    start_clock = time.perf_counter()
    initial_widths = state_box_widths(initial)
    max_attempted_exact = [Fraction(0)] * 6
    max_accepted_exact = [Fraction(0)] * 6
    max_width_ratio_exact = None
    max_accepted_ratio_exact = None
    stats = dict(attempts=0, native_iterations=0, accepted_steps=0,
                 subdivisions=0, schedule_subdivisions=0, failure_subdivisions=0,
                 width_subdivisions=0, width_rejections=0, max_depth=0,
                 initial_widths=_width_report(initial_widths),
                 max_attempted_tube_widths=[0.0] * 6,
                 max_accepted_tube_widths=[0.0] * 6,
                 max_width_ratio=None, max_accepted_width_ratio=None, elapsed_s=0.0)
    if _width_exceeds(initial_widths, opts.max_tube_widths):
        stats["max_attempted_tube_widths"] = _width_report(initial_widths)
        max_attempted_exact = list(initial_widths)
        initial_ratios = _width_ratios(initial_widths, opts.max_tube_widths)
        if initial_ratios is not None:
            stats["max_width_ratio"] = _ratio_report(max(initial_ratios))
        stats["elapsed_s"] = time.perf_counter() - start_clock
        return TubeResult(TubeStatus.UNKNOWN, "INITIAL_WIDTH_LIMIT", initial, control,
                          params, w, h, tuple(), None, stats, opts)

    pending = [(Fraction(0), h, 0)]
    segments = []
    state = initial
    failure = ""
    while pending:
        if opts.time_limit_s is not None and time.perf_counter() - start_clock >= opts.time_limit_s:
            failure = "TIME_BUDGET"; break
        if len(segments) >= opts.max_steps:
            failure = "STEP_BUDGET"; break
        t, step_h, depth = pending.pop()
        stats["max_depth"] = max(stats["max_depth"], depth)
        if t != (segments[-1].end_time if segments else Fraction(0)):
            raise RuntimeError("internal noncontiguous schedule")

        need_split = step_h > opts.max_step_s
        local_reason = "MAX_STEP"
        if not need_split:
            if stats["attempts"] >= opts.max_attempts:
                failure = "ATTEMPT_BUDGET"; break
            trial = picard_step(state, control, params, step_h, opts, w)
            stats["attempts"] += 1
            stats["native_iterations"] += trial.iterations
            if opts.time_limit_s is not None and time.perf_counter() - start_clock >= opts.time_limit_s:
                failure = "TIME_BUDGET"; break
            if trial.status == TubeStatus.VALIDATED:
                assert trial.witness is not None
                widths = state_box_widths(trial.witness.tube)
                max_attempted_exact = [max(a, b) for a, b in zip(max_attempted_exact, widths)]
                stats["max_attempted_tube_widths"] = _width_report(max_attempted_exact)
                ratios = _width_ratios(widths, opts.max_tube_widths)
                if ratios is not None:
                    current_ratio = max(ratios)
                    max_width_ratio_exact = current_ratio if max_width_ratio_exact is None else max(max_width_ratio_exact, current_ratio)
                    stats["max_width_ratio"] = _ratio_report(max_width_ratio_exact)
                if _width_exceeds(widths, opts.max_tube_widths):
                    # The Picard inclusion is valid, but this enclosure is too
                    # coarse for the configured abstraction/quality budget.
                    # Do not append it; bisect and recompute both children.
                    local_reason = "WIDTH_LIMIT"
                    stats["width_rejections"] += 1
                else:
                    segments.append(TubeSegment(t, depth, trial.witness))
                    state = trial.witness.endpoint
                    stats["accepted_steps"] += 1
                    max_accepted_exact = [max(a, b) for a, b in zip(max_accepted_exact, widths)]
                    stats["max_accepted_tube_widths"] = _width_report(max_accepted_exact)
                    if ratios is not None:
                        current_accepted_ratio = max(ratios)
                        max_accepted_ratio_exact = (current_accepted_ratio if max_accepted_ratio_exact is None
                                                    else max(max_accepted_ratio_exact, current_accepted_ratio))
                        stats["max_accepted_width_ratio"] = _ratio_report(max_accepted_ratio_exact)
                    continue
            else:
                local_reason = trial.reason

        half = step_h * 0.5
        if depth >= opts.max_depth:
            failure = f"DEPTH_LIMIT:{local_reason}"; break
        if half < opts.min_step_s:
            failure = f"MIN_STEP:{local_reason}"; break
        if half <= 0 or Fraction.from_float(half) * 2 != Fraction.from_float(step_h):
            failure = f"TIME_REPRESENTATION:{local_reason}"; break
        if local_reason == "WIDTH_LIMIT" and stats["width_subdivisions"] >= opts.max_width_subdivisions:
            failure = "WIDTH_SPLIT_BUDGET"; break

        pending.append((t + Fraction.from_float(half), half, depth + 1))
        pending.append((t, half, depth + 1))
        stats["subdivisions"] += 1
        if need_split:
            stats["schedule_subdivisions"] += 1
        elif local_reason == "WIDTH_LIMIT":
            stats["width_subdivisions"] += 1
        else:
            stats["failure_subdivisions"] += 1

    stats["elapsed_s"] = time.perf_counter() - start_clock
    complete = not failure and bool(segments) and segments[-1].end_time == Fraction.from_float(h)
    if not complete and not failure: failure = "INCOMPLETE_HORIZON"
    return TubeResult(TubeStatus.VALIDATED if complete else TubeStatus.UNKNOWN,
                      "COMPLETE_DYNAMICS_ENCLOSURE" if complete else failure,
                      initial, control, params, w, h, tuple(segments), state if complete else None,
                      stats, opts)
