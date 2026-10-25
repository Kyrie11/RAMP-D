"""Pure timing helpers for event-anchored evidence interventions.

The helpers deliberately return *planned* mask state only. Every episode must
also log realized mask timestamps and pass the exposure-validity checks before
it can contribute to a causal estimate.
"""
from __future__ import annotations

from typing import Optional


def estimate_time_to_anchor_s(
    value: float,
    target: float,
    previous_value: Optional[float],
    previous_time_s: Optional[float],
    now_s: float,
    speed_mps: float,
) -> float:
    """Estimate time until a decreasing scalar reaches target.

    Prefer a finite-difference slope from the last simulator tick. If the
    observed slope is not decreasing (e.g. near a stop), fall back to speed as
    a conservative distance/time proxy. The returned value is only a scheduler
    estimate; actual timing is always measured and validated from timestamps.
    """
    delta = float(value) - float(target)
    if delta <= 0.0:
        return 0.0
    slope = None
    if previous_value is not None and previous_time_s is not None:
        dt = float(now_s) - float(previous_time_s)
        if dt > 1e-6:
            slope = (float(value) - float(previous_value)) / dt
    if slope is not None and slope < -0.05:
        tau = delta / (-slope)
    else:
        tau = delta / max(0.5, float(speed_mps))
    return max(0.0, min(float(tau), 120.0))


def evidence_gap_active(
    *,
    enabled: bool,
    timing: str,
    now_s: float,
    anchor_time_s: Optional[float],
    time_to_anchor_s: Optional[float],
    duration_s: float,
) -> bool:
    """Schedule fixed-duration evidence gaps relative to an event anchor.

    pre:     [anchor-duration, anchor)
    overlap: [anchor-duration/2, anchor+duration/2)
    post:    [anchor, anchor+duration)

    Before the anchor, pre/overlap use a predicted time-to-anchor. The realized
    interval can differ due to acceleration or tick discretization; callers
    must validate the measured interval rather than trust this schedule alone.
    """
    if not enabled or timing == "none":
        return False
    duration = max(0.1, float(duration_s))
    now = float(now_s)
    if timing == "pre":
        if anchor_time_s is not None:
            return False
        return time_to_anchor_s is not None and 0.0 < float(time_to_anchor_s) <= duration
    if timing == "overlap":
        if anchor_time_s is not None:
            return now < float(anchor_time_s) + duration / 2.0
        return time_to_anchor_s is not None and 0.0 < float(time_to_anchor_s) <= duration / 2.0
    if timing == "post":
        return anchor_time_s is not None and now < float(anchor_time_s) + duration
    raise ValueError(f"Unsupported evidence-gap timing: {timing}")
