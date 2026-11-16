"""Phase 6C offline candidate interface: leakage-free baseline and *soft* ranking.

This is deliberately NOT a learned RAMP-D joint decoder, RuleNet network,
winning-set solver, resource monitor, or safety certificate.  The constant
world-velocity baseline diagnoses dataset wiring; learned proposals can later
be plugged into the existing `ProposalSet` protocol.  Only a verifier with an
independent full environment-support contract may issue safety conclusions.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
import math
from typing import Mapping, Sequence

from .forecast import PredictionProposal, ProposalSet
from .scene_schema import UnifiedScene, SceneTrack


@dataclass(frozen=True)
class ForecastJob:
    dataset: str
    split: str
    scenario_id: str
    source_digest: str
    scene: UnifiedScene

    @classmethod
    def from_scene(cls, scene: UnifiedScene) -> "ForecastJob":
        """Strip future *before* presenting input to a predictor."""
        scene.assert_valid()
        m = scene.manifest
        if not m.future_available and any(s.valid for tr in scene.tracks
                                          for s in tr.states[m.current_time_index+1:]):
            raise ValueError("withheld future labels are present in test scene")
        prefix = scene.online_view()
        return cls(m.dataset, m.split, m.scenario_id, m.source_digest, prefix)


def _time_step(scene: UnifiedScene) -> float:
    ts = scene.manifest.timestamps
    if len(ts) < 2:
        raise ValueError("one timestamp cannot determine a forecast sampling step")
    diffs = [b-a for a,b in zip(ts,ts[1:])]
    # Dataset samples must have approximately uniform spacing for this adapter;
    # irregular sampling requires an explicit resampler, not silent 10Hz assumption.
    dt = sorted(diffs)[len(diffs)//2]
    if dt <= 0 or max(abs(d-dt) for d in diffs) > max(1e-6, 0.01*dt):
        raise ValueError("irregular observation timestep, explicit resampling required")
    return dt


def _last_observed_velocity(track: SceneTrack, current: int) -> tuple[float, float] | None:
    observed = [(i, s) for i, s in enumerate(track.states[:current+1])
                if s.valid and s.observed is True and s.x is not None and s.y is not None]
    if not observed or observed[-1][0] != current:
        # Never fill a missing current state from future ground truth.
        return None
    _, last = observed[-1]
    if last.vx is not None and last.vy is not None:
        return last.vx, last.vy
    if len(observed) < 2:
        return None
    _, prev = observed[-2]
    dt = last.timestamp - prev.timestamp
    if dt <= 0:
        return None
    return ((last.x - prev.x) / dt, (last.y - prev.y) / dt)


def constant_velocity_proposals(
    job: ForecastJob, *, horizon_steps: int, include_sdc: bool = False,
    maximum_abs_speed_mps: float = 100.0,
) -> tuple[ProposalSet, ...]:
    """One modal proposal per actor; no response to alternative ego actions.

    Score 0 is a baseline ordering score, *not* a likelihood. All positions
    remain in the input's original box-center coordinates and global/local frame.
    """
    if not isinstance(horizon_steps, int) or isinstance(horizon_steps, bool) or horizon_steps <= 0:
        raise ValueError("horizon_steps must be a positive integer")
    scene = job.scene
    if scene.manifest.future_available or any(t.to_predict for t in scene.tracks):
        raise ValueError("ForecastJob must hold an online, future-free scene")
    h = _time_step(scene)
    idx = scene.manifest.current_time_index
    t0 = scene.manifest.timestamps[idx] + h
    result = []
    for track in scene.tracks:
        if track.is_sdc and not include_sdc:
            continue
        velocity = _last_observed_velocity(track, idx)
        if velocity is None:
            continue
        if math.hypot(*velocity) > maximum_abs_speed_mps:
            continue
        base = track.states[idx]
        points = tuple((base.x + i*h*velocity[0], base.y + i*h*velocity[1])
                       for i in range(1, horizon_steps+1))
        proposal = PredictionProposal(
            actor_id=track.track_id, mode_id="constant_velocity", frame_id=scene.manifest.coordinate_frame,
            t0_s=t0, dt_s=h, positions=points, score=0.0,
            source="phase6c_debug_baseline", model_version="cv-v1-not-learned",
            velocities=(velocity,)*horizon_steps,
            reference_point=scene.manifest.position_reference)
        result.append(ProposalSet(track.track_id, scene.manifest.coordinate_frame,
                                  (proposal,), "phase6c_debug_baseline"))
    return tuple(result)


@dataclass(frozen=True)
class SoftPriority:
    mode_id: str
    combined_score: float
    learned_score: float
    rule_score: float | None
    rule_score_source: str


def soft_rank_proposals(
    proposals: ProposalSet, *, rule_scores: Mapping[str, float] | None = None,
    rule_score_source: str | None = None, rule_weight: float = 1.0,
) -> tuple[SoftPriority, ...]:
    """RuleNet-style ranking hook without falsely claiming RuleNet training.

    Missing rule feature scores are neutral, never converted into hard guards.
    No input mode is filtered, and no scores are a formal-support likelihood.
    """
    if rule_scores is not None and not rule_score_source:
        raise ValueError("rule score provenance required")
    if not math.isfinite(rule_weight) or rule_weight < 0:
        raise ValueError("nonnegative finite rule_weight required")
    allowed = {p.mode_id for p in proposals.proposals}
    if rule_scores is not None and not set(rule_scores).issubset(allowed):
        raise ValueError("rule score references a nonexistent proposal mode")
    ordered = []
    for proposal in proposals.proposals:
        rule = None if rule_scores is None else rule_scores.get(proposal.mode_id)
        if rule is not None and not math.isfinite(float(rule)):
            raise ValueError("nonfinite rule soft score")
        ordered.append(SoftPriority(
            proposal.mode_id,
            proposal.score + rule_weight*(0.0 if rule is None else float(rule)),
            proposal.score, None if rule is None else float(rule),
            "not_available" if rule is None else str(rule_score_source)))
    return tuple(sorted(ordered, key=lambda x: (-x.combined_score, x.mode_id)))


def offline_forecast_metrics(scene: UnifiedScene, sets: Sequence[ProposalSet]) -> dict:
    """ADE/FDE only where a VALID, *available* logged future exists.

    Undefined/missing target entries are skipped, not filled. This is a logged
    action evaluation, not an interventional response or safety bound.
    """
    scene.assert_valid()
    if not scene.manifest.future_available:
        raise ValueError("future labels withheld for this split")
    current = scene.manifest.current_time_index
    ts = scene.manifest.timestamps
    actors = {t.track_id: t for t in scene.tracks}
    out = []
    for pset in sets:
        if pset.actor_id not in actors:
            raise ValueError("prediction actor missing from evaluation scene")
        track = actors[pset.actor_id]
        for p in pset.proposals:
            if p.frame_id != scene.manifest.coordinate_frame or p.reference_point != scene.manifest.position_reference:
                raise ValueError("prediction coordinate/reference contract mismatch")
            distances = []
            for i,(x,y) in enumerate(p.positions):
                index = current+1+i
                if index >= len(ts) or not p.valid[i]:
                    break
                if abs(p.t0_s + i*p.dt_s - ts[index]) > 1e-5:
                    raise ValueError("prediction and truth time axes differ")
                actual = track.states[index]
                if actual.valid and actual.x is not None and actual.y is not None:
                    distances.append((i,math.hypot(x-actual.x,y-actual.y)))
            if distances:
                # FDE requires valid ground truth at the requested horizon's end.
                last_is_valid = distances[-1][0] == len(p.positions)-1
                out.append({"track_id":pset.actor_id, "mode_id":p.mode_id,
                            "valid_steps":len(distances),
                            "ade_m":sum(d for _,d in distances)/len(distances),
                            "fde_m":distances[-1][1] if last_is_valid else None,
                            "fde_valid":last_is_valid})
    return {"schema":"rampd.phase6c.offline-metrics.v1",
            "evaluation":"logged_action_only_not_counterfactual_or_certified",
            "count":len(out),"rows":out}


def stable_split_fingerprint(keys: Sequence[tuple[str, str, str]]) -> str:
    """Hash a stable (dataset,split,scenario_id) sample list for reproducibility."""
    keys = tuple(keys)
    if len(keys) != len(set(keys)):
        raise ValueError("duplicate scene keys within a frozen split")
    return sha256(json.dumps(sorted(keys), separators=(",",":"), ensure_ascii=True).encode()).hexdigest()
