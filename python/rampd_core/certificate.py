"""Versioned JSON inclusion witnesses. Replay checks do not establish safety."""
from __future__ import annotations
from dataclasses import asdict, dataclass
from fractions import Fraction
from pathlib import Path
import json
import math
from .interval import Interval
from .model import StateBounds, ControlBounds, BicycleParameters
from .reachability import StepWitness, TubeStatus, check_witness, state_box_widths, PicardOptions

SCHEMA = "rampd.picard-tube.v2"
LEGACY_SCHEMA = "rampd.picard-tube.v1"

def _box(x):
    return [[v.lo, v.hi] for v in (x.as_tuple() if hasattr(x, "as_tuple") else x)]

def _state(data):
    if len(data) != 6: raise ValueError("six state intervals required")
    return StateBounds(*(Interval(*pair) for pair in data))

def _fraction(q): return [str(q.numerator), str(q.denominator)]

def to_dict(result):
    steps = []
    for segment in result.segments:
        w = segment.witness
        steps.append(dict(start_time_exact=_fraction(segment.start_time),
                          end_time_exact=_fraction(segment.end_time), depth=segment.depth,
                          duration_hex=w.duration_s.hex(), initial=_box(w.initial),
                          tube=_box(w.tube), field=_box(w.field), picard_image=_box(w.picard_image),
                          endpoint=_box(w.endpoint), inclusion_margin_lo=list(w.inclusion_margin_lo),
                          width_exact=[_fraction(v) for v in state_box_widths(w.tube)],
                          iterations=w.iterations))
    return dict(schema=SCHEMA, status=result.status.value, reason=result.reason,
                claim="dynamics_outer_enclosure_only", full_support_safety_verified=False,
                model="paper_bicycle_plus_explicit_additive_derivative_box",
                backend=result.backend, native_build=result.native_build,
                initial=_box(result.initial), control=_box(result.control),
                params=asdict(result.params), derivative_disturbance=_box(result.disturbance),
                horizon_hex=result.requested_horizon_s.hex(),
                validated_until_exact=_fraction(result.validated_until),
                endpoint=None if result.endpoint is None else _box(result.endpoint),
                options=asdict(result.options), stats=result.stats, segments=steps)

def save_certificate(result, path):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(to_dict(result), indent=2, allow_nan=False) + "\n", encoding="utf-8")

@dataclass(frozen=True)
class ReplayReport:
    ok: bool
    reason: str
    checked_segments: int

def replay_certificate(path_or_dict) -> ReplayReport:
    """Accept only COMPLETE validated tubes, not an UNKNOWN result's prefix."""
    checked = 0
    try:
        d = path_or_dict if isinstance(path_or_dict, dict) else json.loads(Path(path_or_dict).read_text(encoding="utf-8"))
        if d["schema"] not in (SCHEMA, LEGACY_SCHEMA): raise ValueError("unsupported schema")
        if d["status"] != TubeStatus.VALIDATED.value: raise ValueError("not a complete VALIDATED result")
        if d["claim"] != "dynamics_outer_enclosure_only" or d["full_support_safety_verified"] is not False:
            raise ValueError("unsupported safety claim")
        if d["model"] != "paper_bicycle_plus_explicit_additive_derivative_box":
            raise ValueError("unsupported model")
        params = BicycleParameters(**d["params"])
        control = ControlBounds(*(Interval(*v) for v in d["control"]))
        disturbance = tuple(Interval(*v) for v in d["derivative_disturbance"])
        if len(disturbance) != 6: raise ValueError("invalid disturbance")
        horizon = float.fromhex(d["horizon_hex"])
        if not math.isfinite(horizon) or horizon <= 0: raise ValueError("invalid horizon")
        options = PicardOptions(**d.get("options", {}))
        state = _state(d["initial"]); t = Fraction(0)
        if options.max_tube_widths is not None:
            initial_widths = state_box_widths(state)
            if any(w > cap for w, cap in zip(initial_widths, options.max_tube_widths)):
                raise ValueError("initial state violates configured tube-width limit")
        if not d["segments"]: raise ValueError("empty witness list")
        for record in d["segments"]:
            start = Fraction(*map(int, record["start_time_exact"]))
            end = Fraction(*map(int, record["end_time_exact"]))
            h = float.fromhex(record["duration_hex"])
            if not math.isfinite(h) or h <= 0 or start != t or end != start + Fraction.from_float(h):
                raise ValueError("time discontinuity or invalid duration")
            initial = _state(record["initial"])
            # A wider next initial box is sound, but exact linkage makes audit
            # and accidental certificate tampering detection simpler in v1.
            if initial != state: raise ValueError("broken endpoint-to-initial linkage")
            witness = StepWitness(initial, h, _state(record["tube"]),
                                  tuple(Interval(*v) for v in record["field"]),
                                  _state(record["picard_image"]), _state(record["endpoint"]),
                                  tuple(record["inclusion_margin_lo"]), int(record["iterations"]))
            if not check_witness(witness, control, params, disturbance):
                raise ValueError("Picard witness replay failed")
            widths = state_box_widths(witness.tube)
            if options.max_tube_widths is not None and any(
                    width > cap for width, cap in zip(widths, options.max_tube_widths)):
                raise ValueError("segment violates configured tube-width limit")
            if d["schema"] == SCHEMA:
                claimed = tuple(Fraction(*map(int, pair)) for pair in record["width_exact"])
                if len(claimed) != 6 or any(v != actual for v, actual in zip(claimed, widths)):
                    raise ValueError("exact width metadata mismatch")
            state, t = witness.endpoint, end
            checked += 1
        if t != Fraction.from_float(horizon): raise ValueError("horizon not fully covered")
        if Fraction(*map(int, d["validated_until_exact"])) != t: raise ValueError("coverage metadata mismatch")
        if _state(d["endpoint"]) != state: raise ValueError("terminal endpoint mismatch")
        return ReplayReport(True, "all dynamics inclusion witnesses replayed", checked)
    except (KeyError, ValueError, TypeError, RuntimeError, OverflowError, ZeroDivisionError, OSError) as exc:
        return ReplayReport(False, str(exc), checked)
