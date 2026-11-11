"""Prediction proposals are kept separate from Phase 4 safety evidence.

MTR/MTR++ and QCNet/QCNeXt expose multimodal densities or scored trajectory
proposals.  A finite mean/scale band is not a support enclosure for a Gaussian
or Laplace tail, and a top-k/NMS result is not a complete set of allowed
behaviours.  This module therefore provides a dependency-free record format
for retaining every supplied mode and an explicit adapter result that can only
be used for ordering.  Conversion to a hard agent tube is intentionally
refused unless an independent response contract is supplied by ``agents.py``
and verified by the full-support verifier.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import hashlib
import json
import math
from typing import Iterable


class ProposalStatus(str, Enum):
    PROPOSAL_ONLY = "PROPOSAL_ONLY"
    UNKNOWN_UNBOUNDED_TAIL = "UNKNOWN_UNBOUNDED_TAIL"
    REJECTED = "REJECTED"


def _finite(value, name):
    value = float(value)
    if not math.isfinite(value):
        raise ValueError(f"{name} must be finite")
    return value


@dataclass(frozen=True)
class PredictionProposal:
    """One complete multimodal trajectory proposal, preserving provenance."""

    actor_id: str
    mode_id: str
    frame_id: str
    t0_s: float
    dt_s: float
    positions: tuple[tuple[float, float], ...]
    score: float
    source: str
    model_version: str
    scales: tuple[tuple[float, float], ...] = ()
    rho: tuple[float, ...] = ()
    velocities: tuple[tuple[float, float], ...] = ()
    valid: tuple[bool, ...] = ()
    reference_point: str = "unknown"
    nms_applied: bool = False

    def __post_init__(self):
        if not self.actor_id or not self.mode_id or not self.frame_id:
            raise ValueError("actor, mode and frame ids are required")
        if not self.source or not self.model_version:
            raise ValueError("prediction provenance is required")
        t0, dt = _finite(self.t0_s, "t0_s"), _finite(self.dt_s, "dt_s")
        if dt <= 0:
            raise ValueError("dt_s must be positive")
        object.__setattr__(self, "t0_s", t0)
        object.__setattr__(self, "dt_s", dt)
        points = tuple(tuple(_finite(v, "position") for v in p) for p in self.positions)
        if not points or any(len(p) != 2 for p in points):
            raise ValueError("positions must be a nonempty sequence of 2D points")
        object.__setattr__(self, "positions", points)
        object.__setattr__(self, "score", _finite(self.score, "score"))
        scales = tuple(tuple(_finite(v, "scale") for v in p) for p in self.scales)
        if scales and (len(scales) != len(points) or any(len(p) != 2 for p in scales)):
            raise ValueError("scales must match positions and be 2D")
        if any(v <= 0 for p in scales for v in p):
            raise ValueError("prediction scales must be positive")
        object.__setattr__(self, "scales", scales)
        rho = tuple(_finite(v, "rho") for v in self.rho)
        if rho and len(rho) != len(points):
            raise ValueError("rho must match positions")
        object.__setattr__(self, "rho", rho)
        velocities = tuple(tuple(_finite(v, "velocity") for v in p) for p in self.velocities)
        if velocities and (len(velocities) != len(points) or any(len(p) != 2 for p in velocities)):
            raise ValueError("velocities must match positions and be 2D")
        object.__setattr__(self, "velocities", velocities)
        if any(not isinstance(v, bool) for v in self.valid):
            raise TypeError("valid mask values must be bool")
        valid = tuple(self.valid)
        if valid and len(valid) != len(points):
            raise ValueError("valid mask must match positions")
        object.__setattr__(self, "valid", valid or (True,) * len(points))
        if not self.reference_point:
            raise ValueError("reference_point must be explicit")

    @classmethod
    def from_mtr_row(cls, actor_id: str, mode_id: str, frame_id: str,
                     t0_s: float, dt_s: float, rows: Iterable[Iterable[float]],
                     score: float, *, source="MTR",
                     model_version="unknown", reference_point="box_center",
                     nms_applied=False):
        """Decode the MTR 7-vector ``x,y,log_std_x,log_std_y,rho,vx,vy``.

        The conversion retains the scales and correlation as metadata.  It
        does not turn them into a finite safety tube.
        """
        positions, scales, rho, velocities = [], [], [], []
        for row in rows:
            values = tuple(float(v) for v in row)
            if len(values) != 7:
                raise ValueError("MTR prediction rows must have 7 values")
            if not all(math.isfinite(v) for v in values):
                raise ValueError("MTR prediction row contains nonfinite value")
            x, y, log_sx, log_sy, corr, vx, vy = values
            sx, sy = math.exp(log_sx), math.exp(log_sy)
            if not (math.isfinite(sx) and math.isfinite(sy) and sx > 0 and sy > 0):
                raise ValueError("MTR log scale does not produce a finite positive scale")
            if abs(corr) > 1:
                raise ValueError("MTR correlation must lie in [-1,1]")
            positions.append((x, y)); scales.append((sx, sy)); rho.append(corr)
            velocities.append((vx, vy))
        return cls(actor_id, mode_id, frame_id, t0_s, dt_s, tuple(positions), score,
                   source, model_version, tuple(scales), tuple(rho), tuple(velocities),
                   reference_point=reference_point, nms_applied=nms_applied)

    def to_dict(self):
        return {
            "actor_id": self.actor_id, "mode_id": self.mode_id,
            "frame_id": self.frame_id, "t0_s": self.t0_s, "dt_s": self.dt_s,
            "positions": [list(p) for p in self.positions], "score": self.score,
            "source": self.source, "model_version": self.model_version,
            "scales": [list(p) for p in self.scales], "rho": list(self.rho),
            "velocities": [list(p) for p in self.velocities],
            "valid": list(self.valid), "reference_point": self.reference_point,
            "nms_applied": bool(self.nms_applied),
        }


@dataclass(frozen=True)
class ProposalSet:
    actor_id: str
    frame_id: str
    proposals: tuple[PredictionProposal, ...]
    source: str
    complete_modes: bool = True

    def __post_init__(self):
        proposals = tuple(self.proposals)
        if not proposals or any(p.actor_id != self.actor_id or p.frame_id != self.frame_id
                                 for p in proposals):
            raise ValueError("proposal set must contain modes for one actor/frame")
        if len({p.mode_id for p in proposals}) != len(proposals):
            raise ValueError("mode ids must be unique")
        if not self.source:
            raise ValueError("proposal source is required")
        object.__setattr__(self, "proposals", proposals)

    def ranked(self):
        return tuple(sorted(self.proposals, key=lambda p: (-p.score, p.mode_id)))

    def top_k(self, k: int):
        if isinstance(k, bool) or not isinstance(k, int) or k <= 0:
            raise ValueError("k must be a positive integer")
        return ProposalSet(self.actor_id, self.frame_id, self.ranked()[:k], self.source,
                           complete_modes=(self.complete_modes and k >= len(self.proposals)))

    def digest(self):
        raw = json.dumps({"actor_id": self.actor_id, "frame_id": self.frame_id,
                          "source": self.source, "complete_modes": self.complete_modes,
                          "proposals": [p.to_dict() for p in self.proposals]},
                         sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
        return "proposal-sha256:" + hashlib.sha256(raw).hexdigest()


@dataclass(frozen=True)
class ProposalAdapterResult:
    status: ProposalStatus
    reason: str
    proposal_set: ProposalSet | None = None


def proposal_only(proposals: Iterable[PredictionProposal], *, source: str) -> ProposalAdapterResult:
    proposals = tuple(proposals)
    if not proposals:
        return ProposalAdapterResult(ProposalStatus.REJECTED, "NO_PROPOSALS")
    if any(p.nms_applied for p in proposals):
        reason = "MODES_RETAINED_BUT_NMS_MAY_HAVE_REMOVED_BEHAVIOURS"
    else:
        reason = "SCORED_PROPOSALS_ONLY_NOT_A_SAFETY_SUPPORT"
    first = proposals[0]
    result = ProposalSet(first.actor_id, first.frame_id, proposals, source,
                         complete_modes=not any(p.nms_applied for p in proposals))
    return ProposalAdapterResult(ProposalStatus.PROPOSAL_ONLY, reason, result)


def hard_support_from_prediction(_proposal_set: ProposalSet):
    """Never infer a deterministic safety tube from a learned density."""
    return ProposalAdapterResult(ProposalStatus.UNKNOWN_UNBOUNDED_TAIL,
                                 "PREDICTION_DENSITY_HAS_UNBOUNDED_OR_UNCALIBRATED_RESIDUAL_TAIL")
