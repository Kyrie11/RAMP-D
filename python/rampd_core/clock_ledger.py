"""Phase 6C finite-run simulator synchronization observability checks.

A ledger checking clock increments is *not* a proof of protocol delivery
bounds, physical model calibration, exact actor co-location, or task safety.
"""
from __future__ import annotations
from dataclasses import dataclass, field
import math


@dataclass(frozen=True)
class CoSimTick:
    step: int
    carla_frame: int
    carla_elapsed_s: float
    sumo_elapsed_s: float
    sumo_actor_count: int
    carla_actor_count: int
    mapped_sumo_to_carla: int
    mapped_carla_to_sumo: int


@dataclass
class CoSimLedger:
    fixed_delta_s: float
    tolerance_s: float = 0.005
    ticks: list[CoSimTick] = field(default_factory=list)

    def __post_init__(self):
        if not math.isfinite(self.fixed_delta_s) or self.fixed_delta_s <= 0:
            raise ValueError("fixed_delta_s must be finite and > 0")
        if not math.isfinite(self.tolerance_s) or not 0 <= self.tolerance_s < self.fixed_delta_s/2:
            raise ValueError("tolerance_s must be finite and < fixed_delta_s / 2")

    def record(self, tick: CoSimTick) -> None:
        for t in (tick.carla_elapsed_s, tick.sumo_elapsed_s):
            if not math.isfinite(t) or t < 0:
                raise ValueError("simulator time must be finite, nonnegative")
        for n in (tick.step, tick.carla_frame, tick.sumo_actor_count,
                  tick.carla_actor_count, tick.mapped_sumo_to_carla,
                  tick.mapped_carla_to_sumo):
            if not isinstance(n, int) or isinstance(n, bool) or n < 0:
                raise ValueError("nonnegative integer frame/count required")
        if tick.step != len(self.ticks):
            raise ValueError("co-sim steps must be contiguous")
        if self.ticks:
            last = self.ticks[-1]
            if tick.carla_frame != last.carla_frame + 1:
                raise ValueError("CARLA frame skipped or another tick owner interfered")
            for label, delta in (("CARLA",tick.carla_elapsed_s-last.carla_elapsed_s),
                                 ("SUMO",tick.sumo_elapsed_s-last.sumo_elapsed_s)):
                if abs(delta-self.fixed_delta_s) > self.tolerance_s:
                    raise ValueError(f"{label} time advance {delta:.6f} differs from fixed step {self.fixed_delta_s}")
            drift = (tick.carla_elapsed_s-self.ticks[0].carla_elapsed_s)-(
                tick.sumo_elapsed_s-self.ticks[0].sumo_elapsed_s)
            if abs(drift) > self.tolerance_s:
                raise ValueError(f"cumulative clock drift {drift:.6f} exceeds threshold")
        self.ticks.append(tick)

    def summary(self) -> dict:
        return {"schema":"rampd.phase6c.cosim-clock-ledger.v1",
                "tick_count":len(self.ticks),"fixed_delta_s":self.fixed_delta_s,
                "clock_increments_checked":len(self.ticks)>=2,
                "status":"PASS" if len(self.ticks)>=2 else "UNKNOWN",
                "protocol_four_clocks_observed":False,
                "continuous_physical_safety_certified":False,
                "ticks":[vars(t) for t in self.ticks]}
