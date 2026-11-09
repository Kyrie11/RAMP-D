"""Validated outer enclosures of oriented rectangular vehicle footprints.

The input StateBounds must already enclose the complete continuous-time state
set over the same time interval. This module maps that box to a swept spatial
set enclosure. It does not integrate dynamics or infer a vehicle reference
point: center_offset_* must be calibrated for the model's (px, py) convention.

Pairwise separation is a sufficient proof only. If no tested fixed axis
separates the outer projection intervals, the answer is UNKNOWN (not collision).
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
from fractions import Fraction
from pathlib import Path
import json
import math

from .interval import Interval, IntervalError, square, sqrt, sin, cos
from .model import StateBounds

SCHEMA = "rampd.swept-separation.v1"


@dataclass(frozen=True)
class VehicleGeometry:
    """Fixed vehicle geometry in metres.

    length/width and center offsets are exact configured binary64 constants for
    this computation. `center_offset_x_m/y_m` locate the geometric rectangle
    center relative to the bicycle model's (px,py) reference point in body
    coordinates. Set them to zero ONLY when (px,py) is the body center.
    """
    length_m: float
    width_m: float
    center_offset_x_m: float = 0.0
    center_offset_y_m: float = 0.0

    def __post_init__(self):
        for name in ("length_m", "width_m", "center_offset_x_m", "center_offset_y_m"):
            value = float(getattr(self, name))
            if not math.isfinite(value):
                raise ValueError(f"{name} must be finite")
            object.__setattr__(self, name, value)
        if self.length_m <= 0.0 or self.width_m <= 0.0:
            raise ValueError("vehicle length and width must be positive")

    @property
    def half_length_interval(self) -> Interval:
        return Interval.point(self.length_m) / Interval.point(2.0)

    @property
    def half_width_interval(self) -> Interval:
        return Interval.point(self.width_m) / Interval.point(2.0)


@dataclass(frozen=True)
class Projection:
    lo: float
    hi: float

    def __post_init__(self):
        if not (math.isfinite(self.lo) and math.isfinite(self.hi) and self.lo <= self.hi):
            raise ValueError("invalid projection interval")

    def as_interval(self) -> Interval:
        return Interval(self.lo, self.hi)


@dataclass(frozen=True)
class AABB:
    x: Projection
    y: Projection


@dataclass(frozen=True)
class SweptFootprint:
    """Outer enclosure of the union of all footprints represented by a tube."""
    state_tube: StateBounds
    geometry: VehicleGeometry
    start_time: Fraction
    end_time: Fraction
    vehicle_id: str = "vehicle"

    def __post_init__(self):
        if not isinstance(self.state_tube, StateBounds):
            raise TypeError("state_tube must be StateBounds")
        if not isinstance(self.geometry, VehicleGeometry):
            raise TypeError("geometry must be VehicleGeometry")
        if not isinstance(self.start_time, Fraction) or not isinstance(self.end_time, Fraction):
            raise TypeError("times must be exact fractions")
        if self.start_time < 0 or self.end_time <= self.start_time:
            raise ValueError("swept footprint requires 0 <= start_time < end_time")
        if not isinstance(self.vehicle_id, str) or not self.vehicle_id:
            raise ValueError("vehicle_id must be a nonempty string")

    @classmethod
    def from_segment(cls, segment, geometry: VehicleGeometry, vehicle_id: str = "vehicle"):
        """Map one accepted TubeSegment; its witness tube covers the full step."""
        return cls(segment.witness.tube, geometry, segment.start_time,
                   segment.end_time, vehicle_id)

    @classmethod
    def from_segment_covering(cls, segment, geometry: VehicleGeometry,
                              start_time: Fraction, end_time: Fraction,
                              vehicle_id: str = "vehicle"):
        """Reuse a full-segment tube on a contained subinterval.

        This is conservative (the state box may be wider than necessary) and
        permits pairwise comparison when two adaptive integrators have
        different segment boundaries.
        """
        if start_time < segment.start_time or end_time > segment.end_time or end_time <= start_time:
            raise ValueError("requested subinterval is not covered by source segment")
        return cls(segment.witness.tube, geometry, start_time, end_time, vehicle_id)

    def projection(self, axis: tuple[float, float]) -> Projection:
        """Outward projection enclosure along a fixed, exact-binary64 axis.

        The axis components are treated as exact binary64 real constants.
        They need not be unit length. All geometry arithmetic is MPFR-backed.
        """
        nx, ny = _validate_axis(axis)
        px, py, psi, _v, _a, _delta = self.state_tube.as_tuple()
        c, s = cos(psi), sin(psi)
        ox = Interval.point(self.geometry.center_offset_x_m)
        oy = Interval.point(self.geometry.center_offset_y_m)
        # Geometric rectangle center = reference point + R(psi) * offset.
        center_x = px + c * ox - s * oy
        center_y = py + s * ox + c * oy
        center_projection = Interval.point(nx) * center_x + Interval.point(ny) * center_y

        # Projections of body longitudinal/lateral unit vectors onto axis n.
        longitudinal = Interval.point(nx) * c + Interval.point(ny) * s
        lateral = -Interval.point(nx) * s + Interval.point(ny) * c
        radius = (self.geometry.half_length_interval *
                  Interval(0.0, _abs_upper(longitudinal)))
        radius = radius + (self.geometry.half_width_interval *
                           Interval(0.0, _abs_upper(lateral)))
        # radius.hi is already an outward upper bound. Symmetric expansion
        # encloses every rectangle point for every state in the state tube.
        projected = center_projection + Interval(-radius.hi, radius.hi)
        return Projection(projected.lo, projected.hi)

    @property
    def aabb(self) -> AABB:
        return AABB(self.projection((1.0, 0.0)), self.projection((0.0, 1.0)))


def _abs_upper(x: Interval) -> float:
    # Exact absolute value of finite binary64 endpoints; max bounds |x|.
    return max(abs(x.lo), abs(x.hi))


def _validate_axis(axis) -> tuple[float, float]:
    if len(axis) != 2:
        raise ValueError("separating axis must have two components")
    nx, ny = float(axis[0]), float(axis[1])
    if not (math.isfinite(nx) and math.isfinite(ny)) or (nx == 0.0 and ny == 0.0):
        raise ValueError("separating axis must be finite and nonzero")
    return nx, ny


def _heading_axes(fp: SweptFootprint):
    psi = fp.state_tube.psi
    # The approximate midpoint is used ONLY to choose a fixed candidate axis.
    # Once chosen, its binary64 components are exact constants in the MPFR
    # projection proof. A poor candidate can cause UNKNOWN, never false safety.
    mid = psi.lo / 2.0 + psi.hi / 2.0
    c, s = math.cos(mid), math.sin(mid)
    return ((c, s), (-s, c))


def candidate_axes(a: SweptFootprint, b: SweptFootprint):
    axes = [(1.0, 0.0), (0.0, 1.0)]
    axes.extend(_heading_axes(a))
    axes.extend(_heading_axes(b))
    # Preserve order while removing exact duplicate binary64 directions.
    out, seen = [], set()
    for axis in axes:
        axis = _validate_axis(axis)
        if axis not in seen:
            seen.add(axis)
            out.append(axis)
    return tuple(out)


class SeparationStatus(str, Enum):
    SEPARATED = "SEPARATED"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class SeparationWitness:
    axis: tuple[float, float]
    order: str
    projection_a: Projection
    projection_b: Projection
    projection_gap_lower: float
    clearance_lower_m: float


@dataclass(frozen=True)
class SeparationResult:
    status: SeparationStatus
    reason: str
    witness: SeparationWitness | None
    axes_tested: int


def _axis_separation(a: SweptFootprint, b: SweptFootprint, axis):
    pa, pb = a.projection(axis), b.projection(axis)
    if pa.hi < pb.lo:
        gap = Interval.point(pb.lo) - Interval.point(pa.hi)
        order = "A_BEFORE_B"
    elif pb.hi < pa.lo:
        gap = Interval.point(pa.lo) - Interval.point(pb.hi)
        order = "B_BEFORE_A"
    else:
        return None
    if gap.lo <= 0.0:
        # A positive real gap smaller than binary64's representable lower bound
        # cannot be reported as a positive certified margin.
        return None
    norm_sq = square(Interval.point(axis[0])) + square(Interval.point(axis[1]))
    norm = sqrt(norm_sq)
    if norm.lo <= 0.0:
        return None
    clearance = gap / norm
    if clearance.lo <= 0.0:
        return None
    return SeparationWitness(tuple(axis), order, pa, pb, gap.lo, clearance.lo)


def separate_swept_footprints(a: SweptFootprint, b: SweptFootprint,
                              axes=None) -> SeparationResult:
    """Prove disjoint swept spatial sets, or return UNKNOWN.

    A fixed axis whose outward projection intervals are strictly disjoint is
    a sufficient proof that the two complete swept spatial enclosures do not
    intersect. Since each enclosure is the union-over-time outer bound, this
    is stronger than merely ruling out simultaneous collision. No collision
    conclusion is made when the projections overlap.
    """
    if not isinstance(a, SweptFootprint) or not isinstance(b, SweptFootprint):
        raise TypeError("expected two SweptFootprint objects")
    if (a.start_time, a.end_time) != (b.start_time, b.end_time):
        raise ValueError("swept footprints must cover the same exact time interval")
    test_axes = candidate_axes(a, b) if axes is None else tuple(_validate_axis(v) for v in axes)
    if not test_axes:
        raise ValueError("at least one separating axis is required")
    numerical_failures = 0
    for axis in test_axes:
        try:
            witness = _axis_separation(a, b, axis)
        except (IntervalError, OverflowError):
            numerical_failures += 1
            continue
        if witness is not None:
            return SeparationResult(SeparationStatus.SEPARATED,
                                    "STRICT_OUTER_PROJECTION_GAP", witness, len(test_axes))
    reason = ("NUMERICAL_ENCLOSURE_FAILURE_ON_ALL_USEFUL_AXES" if numerical_failures == len(test_axes)
              else "NO_TESTED_AXIS_PROVED_STRICT_SEPARATION")
    return SeparationResult(SeparationStatus.UNKNOWN, reason, None, len(test_axes))



@dataclass(frozen=True)
class SegmentPairResult:
    start_time: Fraction
    end_time: Fraction
    result: SeparationResult


@dataclass(frozen=True)
class SequenceSeparationResult:
    status: SeparationStatus
    reason: str
    pairs: tuple[SegmentPairResult, ...]


def _validate_segment_partition(segments):
    seq = tuple(segments)
    if not seq:
        raise ValueError("tube segment sequence must be nonempty")
    for i, seg in enumerate(seq):
        if seg.end_time <= seg.start_time:
            raise ValueError("invalid tube segment time interval")
        if i and seq[i-1].end_time != seg.start_time:
            raise ValueError("tube segment sequence must be contiguous and ordered")
    return seq


def separate_tube_sequences(segments_a, geometry_a: VehicleGeometry,
                            segments_b, geometry_b: VehicleGeometry,
                            vehicle_a: str = "A", vehicle_b: str = "B") -> SequenceSeparationResult:
    """Compare two complete tube partitions with potentially different steps.

    The common refinement is the union of both segment-boundary sets. On each
    overlap interval, each source segment's whole-step state tube is reused;
    this is sound but may be conservative. All overlap intervals must be
    separated to return SEPARATED. Any unresolved interval makes the aggregate
    result UNKNOWN. The function never reports COLLISION.
    """
    aa = _validate_segment_partition(segments_a)
    bb = _validate_segment_partition(segments_b)
    if (aa[0].start_time, aa[-1].end_time) != (bb[0].start_time, bb[-1].end_time):
        raise ValueError("tube sequences must cover the same exact overall time interval")
    i = j = 0
    pairs = []
    while i < len(aa) and j < len(bb):
        sa, sb = aa[i], bb[j]
        lo, hi = max(sa.start_time, sb.start_time), min(sa.end_time, sb.end_time)
        if hi > lo:
            fa = SweptFootprint.from_segment_covering(sa, geometry_a, lo, hi, vehicle_a)
            fb = SweptFootprint.from_segment_covering(sb, geometry_b, lo, hi, vehicle_b)
            pairs.append(SegmentPairResult(lo, hi, separate_swept_footprints(fa, fb)))
        if sa.end_time <= sb.end_time:
            i += 1
        if sb.end_time <= sa.end_time:
            j += 1
    if not pairs:
        raise ValueError("tube sequences have no positive-duration common interval")
    unresolved = any(p.result.status is SeparationStatus.UNKNOWN for p in pairs)
    return SequenceSeparationResult(
        SeparationStatus.UNKNOWN if unresolved else SeparationStatus.SEPARATED,
        "AT_LEAST_ONE_SUBINTERVAL_UNRESOLVED" if unresolved else "ALL_COMMON_SUBINTERVALS_SEPARATED",
        tuple(pairs))


def separate_tube_results(result_a, geometry_a: VehicleGeometry,
                          result_b, geometry_b: VehicleGeometry,
                          vehicle_a: str = "A", vehicle_b: str = "B") -> SequenceSeparationResult:
    """Safe high-level entry point: only complete VALIDATED tube results accepted."""
    from .reachability import TubeResult, TubeStatus
    from .certificate import to_dict as tube_certificate_dict, replay_certificate
    for label, result in (("A", result_a), ("B", result_b)):
        if not isinstance(result, TubeResult):
            raise TypeError(f"tube result {label} must be a TubeResult")
        if result.status is not TubeStatus.VALIDATED or result.endpoint is None or not result.segments:
            raise ValueError(f"tube result {label} is not a complete VALIDATED horizon")
        expected_end = Fraction.from_float(result.requested_horizon_s)
        if result.segments[0].start_time != 0 or result.segments[-1].end_time != expected_end:
            raise ValueError(f"tube result {label} does not cover its exact full horizon")
        if result.endpoint != result.segments[-1].witness.endpoint:
            raise ValueError(f"tube result {label} endpoint does not match its final segment")
        replay = replay_certificate(tube_certificate_dict(result))
        if not replay.ok:
            raise ValueError(f"tube result {label} dynamics witness replay failed: {replay.reason}")
    return separate_tube_sequences(result_a.segments, geometry_a,
                                   result_b.segments, geometry_b, vehicle_a, vehicle_b)

def _state_json(state: StateBounds):
    return [[v.lo, v.hi] for v in state.as_tuple()]


def _geometry_json(g: VehicleGeometry):
    return asdict(g)


def _fraction_json(v: Fraction):
    return [str(v.numerator), str(v.denominator)]


def separation_certificate_dict(a: SweptFootprint, b: SweptFootprint,
                                result: SeparationResult):
    if result.status is not SeparationStatus.SEPARATED or result.witness is None:
        raise ValueError("only a proved separation can be serialized as a certificate")
    w = result.witness
    return {
        "schema": SCHEMA,
        "status": result.status.value,
        "claim": "conditional_pairwise_swept_footprint_separation",
        "full_support_safety_verified": False,
        "time_start_exact": _fraction_json(a.start_time),
        "time_end_exact": _fraction_json(a.end_time),
        "vehicle_a": {"id": a.vehicle_id, "state_tube": _state_json(a.state_tube),
                      "geometry": _geometry_json(a.geometry)},
        "vehicle_b": {"id": b.vehicle_id, "state_tube": _state_json(b.state_tube),
                      "geometry": _geometry_json(b.geometry)},
        "axis_exact_binary64": list(w.axis),
        "order": w.order,
        "projection_a": [w.projection_a.lo, w.projection_a.hi],
        "projection_b": [w.projection_b.lo, w.projection_b.hi],
        "projection_gap_lower": w.projection_gap_lower,
        "clearance_lower_m": w.clearance_lower_m,
        "axes_tested": result.axes_tested,
        "assumption": "input_state_tubes_are_sound_over_the_encoded_common_time_interval",
    }


def save_separation_certificate(a: SweptFootprint, b: SweptFootprint,
                                result: SeparationResult, path):
    d = separation_certificate_dict(a, b, result)
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(d, indent=2, allow_nan=False) + "\n", encoding="utf-8")


@dataclass(frozen=True)
class SeparationReplayReport:
    ok: bool
    reason: str


def replay_separation_certificate(path_or_dict) -> SeparationReplayReport:
    """Recompute one fixed-axis proof; does not validate source dynamics tubes."""
    try:
        d = (path_or_dict if isinstance(path_or_dict, dict) else
             json.loads(Path(path_or_dict).read_text(encoding="utf-8")))
        if d.get("schema") != SCHEMA or d.get("status") != SeparationStatus.SEPARATED.value:
            raise ValueError("unsupported or non-separated certificate")
        if d.get("claim") != "conditional_pairwise_swept_footprint_separation":
            raise ValueError("unsupported claim")
        if d.get("full_support_safety_verified") is not False:
            raise ValueError("certificate cannot claim full-support safety")
        start = Fraction(*map(int, d["time_start_exact"]))
        end = Fraction(*map(int, d["time_end_exact"]))
        if start < 0 or end <= start:
            raise ValueError("invalid certificate time interval")
        from .interval import Interval as I
        from .model import StateBounds as SB
        va, vb = d["vehicle_a"], d["vehicle_b"]
        a = SweptFootprint(SB(*(I(*q) for q in va["state_tube"])),
                           VehicleGeometry(**va["geometry"]), start, end, va["id"])
        b = SweptFootprint(SB(*(I(*q) for q in vb["state_tube"])),
                           VehicleGeometry(**vb["geometry"]), start, end, vb["id"])
        axis = _validate_axis(d["axis_exact_binary64"])
        witness = _axis_separation(a, b, axis)
        if witness is None:
            raise ValueError("encoded axis does not prove strict separation")
        if witness.order != d["order"]:
            raise ValueError("separation order mismatch")
        if [witness.projection_a.lo, witness.projection_a.hi] != d["projection_a"]:
            raise ValueError("vehicle A projection mismatch")
        if [witness.projection_b.lo, witness.projection_b.hi] != d["projection_b"]:
            raise ValueError("vehicle B projection mismatch")
        if not (0.0 < d["projection_gap_lower"] <= witness.projection_gap_lower):
            raise ValueError("claimed projection gap is not a valid lower bound")
        if not (0.0 < d["clearance_lower_m"] <= witness.clearance_lower_m):
            raise ValueError("claimed metric clearance is not a valid lower bound")
        return SeparationReplayReport(True, "fixed-axis outward projection gap replayed")
    except (KeyError, ValueError, TypeError, RuntimeError, OverflowError,
            ZeroDivisionError, OSError) as exc:
        return SeparationReplayReport(False, str(exc))
