"""RAPID-AD dynamic traffic-control scenario implemented on MARSHAL's harness."""
from __future__ import annotations

import json
import logging
import math
import os
from pathlib import Path
from typing import Any

from marshal_bench.actors.gesture_engine import GestureID
from marshal_bench.actors.scene_actors import spawn_occluder
from marshal_bench.controllers import make_controller
from marshal_bench.scenarios._common import run_scenario
from marshal_bench.utils.carla_api_compat import import_carla
from marshal_bench.utils.logging_utils import EpisodeLogger

from rapid_ad.controllers import DynamicDirectiveOracleController
from rapid_ad.interventions import EvidenceFrameHold
from rapid_ad.timing import estimate_time_to_anchor_s, evidence_gap_active

log = logging.getLogger("rapid_ad.scenario")


def _enum(name: str) -> GestureID:
    key = str(name).upper()
    return getattr(GestureID, key, GestureID.STOP)


def _case_from_config(config: dict) -> dict:
    case = dict(config.get("rapid_ad") or {})
    raw = os.environ.get("RAPID_AD_CASE_JSON")
    if raw:
        try:
            env_case = json.loads(raw)
            if isinstance(env_case, dict):
                case.update(env_case)
        except Exception as exc:
            raise ValueError(f"Invalid RAPID_AD_CASE_JSON: {exc}") from exc
    defaults = {
        "case_id": "manual_case",
        "task": "go_to_stop",
        "control_transition": True,
        "evidence_gap": False,
        "gap_timing": "none",
        "phase": "late",
        "transition_distance_m": 9.0,
        "release_wait_after_start_s": 3.0,
        "gap_span_m": float((config.get("scene") or {}).get("evidence_gap_span_m", 2.5)),
        "gap_duration_s": float((config.get("scene") or {}).get("evidence_gap_duration_s", 1.0)),
        "evidence_mode": "frame_hold",
        "seed": int(config.get("seed", 1)),
    }
    for key, value in defaults.items():
        case.setdefault(key, value)
    if case["task"] not in {"go_to_stop", "stop_to_go"}:
        raise ValueError("rapid_ad.task must be 'go_to_stop' or 'stop_to_go'")
    if case["gap_timing"] not in {"none", "pre", "overlap", "post"}:
        raise ValueError("gap_timing must be one of none/pre/overlap/post")
    if not case["evidence_gap"]:
        case["gap_timing"] = "none"
    if case["gap_timing"] != "none":
        case["evidence_gap"] = True
    return case


def _projected_distance(ctx: Any, timeline: dict) -> tuple[float, float, float, float]:
    ego = ctx.ego
    tf = ego.get_transform()
    loc = tf.location
    fx, fy = timeline["forward_x"], timeline["forward_y"]
    progress = (float(loc.x) - timeline["origin_x"]) * fx + (float(loc.y) - timeline["origin_y"]) * fy
    d_line = timeline["line_station_m"] - progress
    velocity = ego.get_velocity()
    speed = math.sqrt(float(velocity.x) ** 2 + float(velocity.y) ** 2 + float(velocity.z) ** 2)
    half_length = 2.4
    try:
        half_length = float(ego.bounding_box.extent.x)
    except Exception:
        pass
    return d_line, speed, progress, half_length


def _initialize_geometry(ctx: Any, config: dict, timeline: dict) -> None:
    if timeline.get("geometry_ready"):
        return
    # Use the actor's realized transform, not the requested spawn transform.
    # This remains correct if MARSHAL applies a spawn fallback or a small lane offset.
    tf = ctx.ego.get_transform()
    origin_x, origin_y = float(tf.location.x), float(tf.location.y)
    fwd = tf.get_forward_vector()
    fx, fy = float(fwd.x), float(fwd.y)
    officer_actor = None
    try:
        officer_actor = ctx.officer.get_actor() if ctx.officer is not None else None
    except Exception:
        officer_actor = None
    if officer_actor is None:
        timeline["geometry_error"] = "officer actor unavailable"
        return
    officer_loc = officer_actor.get_location()
    officer_station = (float(officer_loc.x) - origin_x) * fx + (float(officer_loc.y) - origin_y) * fy
    offset = float(((config.get("scene") or {}).get("control_line_offset_m", 3.0)))
    line_station = officer_station - offset
    timeline.update({
        "origin_x": origin_x,
        "origin_y": origin_y,
        "forward_x": fx,
        "forward_y": fy,
        "officer_station_m": officer_station,
        "line_station_m": line_station,
        "line_x": origin_x + line_station * fx,
        "line_y": origin_y + line_station * fy,
        "control_line_offset_m": offset,
        "geometry_ready": True,
    })
    log.info("RAPID-AD line initialized: officer_station=%.2f m, line_station=%.2f m", officer_station, line_station)


def _gap_active_go_to_stop(
    case: dict, sim_time: float, anchor_time: float | None, time_to_anchor_s: float | None
) -> bool:
    """Schedule an event-relative, approximately fixed-duration RGB frame hold."""
    if case.get("evidence_mode", "frame_hold") == "physical_occluder":
        return False
    return evidence_gap_active(
        enabled=bool(case.get("evidence_gap")),
        timing=str(case.get("gap_timing", "none")),
        now_s=float(sim_time),
        anchor_time_s=anchor_time,
        time_to_anchor_s=time_to_anchor_s,
        duration_s=float(case.get("gap_duration_s", 1.0)),
    )


def _gap_active_stop_to_go(case: dict, sim_time: float, anchor_time: float | None = None) -> bool:
    if case.get("evidence_mode", "frame_hold") == "physical_occluder":
        return False
    if not case.get("evidence_gap") or case.get("gap_timing") == "none":
        return False
    anchor = float(anchor_time if anchor_time is not None else case.get("release_wait_after_start_s", 3.0))
    duration = max(0.1, float(case.get("gap_duration_s", 1.0)))
    timing = str(case.get("gap_timing", "none"))
    if timing == "pre":
        return anchor - duration <= float(sim_time) < anchor
    if timing == "overlap":
        return anchor - duration / 2.0 <= float(sim_time) < anchor + duration / 2.0
    if timing == "post":
        return anchor <= float(sim_time) < anchor + duration
    return False


def _make_tick_hook(config: dict, case: dict, timeline: dict, logger: EpisodeLogger):
    fps = max(1.0, float(config.get("fps", 20)))
    scene = config.get("scene") or {}
    max_decel = max(1.0, float(scene.get("max_brake_decel_mps2", 4.5)))
    reaction = max(0.0, float(scene.get("reaction_budget_s", 0.10)))
    safety_buffer = max(0.1, float(scene.get("safety_buffer_m", 1.0)))

    def _tick(ctx: Any, sim_time: float) -> None:
        if ctx.ego is None or ctx.officer is None:
            return
        _initialize_geometry(ctx, config, timeline)
        if not timeline.get("geometry_ready"):
            return
        d_line, speed, progress, half_length = _projected_distance(ctx, timeline)
        front_clearance = d_line - half_length
        braking_distance = speed * speed / (2.0 * max_decel) + speed * reaction
        recovery_margin = front_clearance - safety_buffer - braking_distance
        timeline["distance_to_control_line_m"] = d_line
        timeline["speed_mps"] = speed
        timeline["ego_progress_m"] = progress
        timeline["front_clearance_m"] = front_clearance
        timeline["stopping_distance_est_m"] = braking_distance
        timeline["recoverability_margin_m"] = recovery_margin
        timeline["last_sim_time"] = float(sim_time)
        previous_anchor_signal = timeline.get("previous_anchor_signal")
        previous_anchor_signal_time = timeline.get("previous_anchor_signal_time")

        task = case["task"]
        transition_enabled = bool(case.get("control_transition"))
        anchor = timeline.get("anchor_time")
        time_to_anchor = None
        if task == "go_to_stop":
            target_margin = case.get("phase_margin_target_m")
            if target_margin is not None:
                anchor_signal = float(recovery_margin)
                anchor_target = float(target_margin)
                anchor_condition = recovery_margin <= anchor_target
                target_description = {"target_margin_m": anchor_target}
            else:
                anchor_signal = float(d_line)
                anchor_target = float(case.get("transition_distance_m", 9.0))
                anchor_condition = d_line <= anchor_target
                target_description = {"target_distance_m": anchor_target}
            time_to_anchor = estimate_time_to_anchor_s(
                anchor_signal, anchor_target,
                float(previous_anchor_signal) if previous_anchor_signal is not None else None,
                float(previous_anchor_signal_time) if previous_anchor_signal_time is not None else None,
                float(sim_time), float(speed),
            )
            timeline["estimated_time_to_anchor_s"] = time_to_anchor
            if anchor is None and anchor_condition:
                timeline["anchor_time"] = float(sim_time)
                timeline["anchor_distance_m"] = float(d_line)
                timeline["anchor_margin_m"] = float(recovery_margin)
                timeline["anchor_triggered"] = True
                logger.log_event(
                    "rapid_ad_phase_anchor", t=sim_time,
                    distance_to_control_line_m=d_line,
                    recoverability_margin_m=recovery_margin,
                    **target_description,
                    phase=case.get("phase"),
                )
                if transition_enabled:
                    timeline["current_directive"] = "STOP"
                    timeline["transition_time"] = float(sim_time)
                    timeline["transition_distance_actual_m"] = float(d_line)
                    if not case.get("evidence_gap") and not timeline.get("has_evidence_wrapper"):
                        timeline["raw_evidence_available_time"] = float(sim_time) + 1.0 / fps
                        timeline["evidence_available_time"] = timeline["raw_evidence_available_time"]
                    try:
                        ctx.officer.set_gesture(GestureID.STOP, onset_time=sim_time, duration=None, target_relation="ego")
                    except Exception as exc:
                        timeline["transition_error"] = repr(exc)
                    logger.log_event(
                        "rapid_ad_control_transition", t=sim_time,
                        old_directive="PROCEED", new_directive="STOP",
                        distance_to_control_line_m=d_line,
                        front_clearance_m=front_clearance,
                        recoverability_margin_m=recovery_margin,
                    )
        else:
            release_time = float(case.get("release_wait_after_start_s", 3.0))
            if anchor is None and sim_time >= release_time:
                # Anchor and actual directive transition must share the realized tick.
                # The configured release time is a target; CARLA advances in fixed steps.
                timeline["anchor_time"] = float(sim_time)
                timeline["anchor_triggered"] = True
                timeline["anchor_distance_m"] = float(d_line)
                timeline["anchor_margin_m"] = float(recovery_margin)
                timeline["stop_confirmed_before_release"] = _has_sustained_stop(
                    timeline.get("trace", []), end=release_time - 1.0 / fps,
                    min_front_clearance_m=safety_buffer, fps=fps,
                )
                logger.log_event(
                    "rapid_ad_phase_anchor", t=sim_time,
                    release_anchor_time_s=release_time,
                    stop_confirmed_before_release=timeline["stop_confirmed_before_release"],
                    distance_to_control_line_m=d_line,
                )
                if transition_enabled:
                    timeline["current_directive"] = "PROCEED"
                    timeline["transition_time"] = float(sim_time)
                    timeline["transition_distance_actual_m"] = float(d_line)
                    if not case.get("evidence_gap") and not timeline.get("has_evidence_wrapper"):
                        timeline["raw_evidence_available_time"] = float(sim_time) + 1.0 / fps
                        timeline["evidence_available_time"] = timeline["raw_evidence_available_time"]
                    try:
                        ctx.officer.set_gesture(GestureID.PROCEED, onset_time=sim_time, duration=None, target_relation="ego")
                    except Exception as exc:
                        timeline["transition_error"] = repr(exc)
                    logger.log_event(
                        "rapid_ad_control_transition", t=sim_time,
                        old_directive="STOP", new_directive="PROCEED",
                        distance_to_control_line_m=d_line,
                        front_clearance_m=front_clearance,
                        recoverability_margin_m=recovery_margin,
                        stop_confirmed_before_release=timeline["stop_confirmed_before_release"],
                    )

        # For no-gap cells, record a matched frame time at the phase anchor.
        # In no-transition controls this is a pseudo-anchor, not a new rule cue.
        if (timeline.get("anchor_triggered") and not case.get("evidence_gap")
                and not timeline.get("has_evidence_wrapper")
                and timeline.get("raw_evidence_available_time") is None):
            timeline["raw_evidence_available_time"] = float(sim_time) + 1.0 / fps
            timeline["evidence_available_time"] = timeline["raw_evidence_available_time"]

        if task == "go_to_stop":
            gap_active = _gap_active_go_to_stop(
                case, float(sim_time), timeline.get("anchor_time"), time_to_anchor
            )
        else:
            gap_active = _gap_active_stop_to_go(case, float(sim_time), timeline.get("anchor_time"))
        previous_gap = bool(timeline.get("evidence_gap_active", False))
        timeline["evidence_gap_active"] = bool(gap_active)
        if gap_active and not previous_gap:
            timeline["evidence_gap_start_time"] = float(sim_time)
            logger.log_event(
                "rapid_ad_planned_evidence_gap_start", t=sim_time,
                gap_timing=case.get("gap_timing"),
                distance_to_control_line_m=d_line,
            )
        elif previous_gap and not gap_active:
            timeline["evidence_gap_end_time"] = float(sim_time)
            if not timeline.get("has_evidence_wrapper") and timeline.get("raw_evidence_available_time") is None:
                timeline["raw_evidence_available_time"] = float(sim_time)
                timeline["evidence_available_time"] = float(sim_time)
            logger.log_event(
                "rapid_ad_planned_evidence_gap_end", t=sim_time,
                gap_timing=case.get("gap_timing"),
                distance_to_control_line_m=d_line,
            )

        if timeline.get("current_directive") == "STOP" and front_clearance < -0.25:
            timeline["unsafe_crossing_while_stop"] = True
            if timeline.get("first_unsafe_crossing_time") is None:
                timeline["first_unsafe_crossing_time"] = float(sim_time)
                logger.log_event(
                    "rapid_ad_unsafe_control_line_crossing", t=sim_time,
                    front_clearance_m=front_clearance,
                    distance_to_control_line_m=d_line,
                )

        trace_row = {
            "sim_time": float(sim_time),
            "distance_to_control_line_m": float(d_line),
            "front_clearance_m": float(front_clearance),
            "speed_mps": float(speed),
            "ego_progress_m": float(progress),
            "current_directive": str(timeline.get("current_directive")),
            "control_transition": bool(transition_enabled),
            "transition_time": timeline.get("transition_time"),
            "anchor_time": timeline.get("anchor_time"),
            "evidence_gap_active": bool(gap_active),
            "stopping_distance_est_m": float(braking_distance),
            "recoverability_margin_m": float(recovery_margin),
        }
        timeline.setdefault("trace", []).append(trace_row)
        logger.log_metric_row(
            t=sim_time,
            rapid_ad_distance_to_control_line_m=d_line,
            rapid_ad_front_clearance_m=front_clearance,
            rapid_ad_speed_mps=speed,
            rapid_ad_ego_progress_m=progress,
            rapid_ad_control_state_gt=str(timeline.get("current_directive")),
            rapid_ad_control_transition=int(transition_enabled),
            rapid_ad_anchor_triggered=int(bool(timeline.get("anchor_triggered"))),
            rapid_ad_stopping_distance_est_m=braking_distance,
            rapid_ad_recoverability_margin_m=recovery_margin,
            rapid_ad_unsafe_crossing_while_stop=int(bool(timeline.get("unsafe_crossing_while_stop"))),
            rapid_ad_estimated_time_to_anchor_s=time_to_anchor if time_to_anchor is not None else "",
        )
        timeline["previous_anchor_signal"] = (float(recovery_margin) if task == "go_to_stop" and case.get("phase_margin_target_m") is not None else float(d_line)) if task == "go_to_stop" else None
        timeline["previous_anchor_signal_time"] = float(sim_time) if task == "go_to_stop" else None

    return _tick


def _setup_extra_actors(config: dict, case: dict):
    if case.get("evidence_mode") != "physical_occluder" or not case.get("evidence_gap"):
        return None

    def _setup(world: Any, ego: Any, ego_transform: Any, officer: Any, cfg: dict) -> list:
        scene = cfg.get("scene") or {}
        distance = float(scene.get("physical_occluder_distance_m", 10.0))
        lateral = float(scene.get("physical_occluder_lateral_m", 3.4))
        actors = spawn_occluder(world, ego_transform, distance=distance, lateral=lateral)
        if not actors:
            log.error("RAPID-AD physical occluder failed to spawn")
        return actors

    return _setup


def _has_sustained_stop(
    trace: list[dict], start: float = 0.0, end: float | None = None,
    duration_s: float = 0.5, min_front_clearance_m: float = 0.25,
    fps: float = 20.0,
) -> bool:
    samples = [r for r in trace if float(r.get("sim_time", 0.0)) >= start and (end is None or float(r.get("sim_time", 0.0)) <= end)]
    if len(samples) < 2:
        return False
    need = max(2, int(round(duration_s * max(1.0, fps))))
    run = 0
    for row in samples:
        if float(row.get("speed_mps", 999.0)) < 0.20 and float(row.get("front_clearance_m", -999.0)) >= min_front_clearance_m:
            run += 1
            if run >= need:
                return True
        else:
            run = 0
    return False


def _metrics_rows(path: Path) -> list[dict]:
    import csv
    if not path.is_file():
        return []
    grouped: dict[float, dict] = {}
    with path.open("r", newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            try:
                t = round(float(row["t"]), 4)
            except Exception:
                continue
            item = grouped.setdefault(t, {"sim_time": t})
            key = row.get("key")
            value = row.get("value")
            if key:
                try:
                    value = float(value)
                except (TypeError, ValueError):
                    pass
                item[key] = value
    return [grouped[t] for t in sorted(grouped)]


def _first_brake_response(rows: list[dict], event_time: float | None) -> float | None:
    if event_time is None:
        return None
    before = [r for r in rows if event_time - 0.6 <= r["sim_time"] < event_time]
    after = [r for r in rows if r["sim_time"] >= event_time]
    if not after:
        return None
    pre_brakes = [float(r.get("brake", 0.0) or 0.0) for r in before]
    pre_throttles = [float(r.get("throttle", 0.0) or 0.0) for r in before]
    pre_brake = sorted(pre_brakes)[len(pre_brakes)//2] if pre_brakes else 0.0
    pre_throttle = sorted(pre_throttles)[len(pre_throttles)//2] if pre_throttles else 0.0
    for row in after:
        brake = float(row.get("brake", 0.0) or 0.0)
        throttle = float(row.get("throttle", 0.0) or 0.0)
        if brake >= max(0.20, pre_brake + 0.15) or throttle <= pre_throttle - 0.20:
            return max(0.0, float(row["sim_time"]) - event_time)
    return None


def _resume_latency(trace: list[dict], evidence_time: float | None, allowance_s: float, fps: float = 20.0) -> tuple[float | None, bool]:
    if evidence_time is None:
        return None, False
    samples = [r for r in trace if float(r.get("sim_time", 0.0)) >= evidence_time]
    need = max(2, int(round(0.5 * max(1.0, fps))))
    run = 0
    run_start = None
    first = None
    for row in samples:
        if float(row.get("speed_mps", 0.0)) >= 0.50:
            if run == 0:
                run_start = float(row["sim_time"])
            run += 1
            if run >= need:
                first = float(run_start)
                break
        else:
            run = 0
            run_start = None
    if first is None:
        return None, False
    latency = max(0.0, first - evidence_time)
    return latency, latency <= allowance_s


def _speed_change_latency(
    trace: list[dict], start_time: float | None, direction: str,
    delta_mps: float = 0.30, sustain_s: float = 0.20, fps: float = 20.0,
) -> float | None:
    """First sustained speed change relative to speed at start_time.

    This is a physical-response proxy, separate from the controller's command
    response. It is not used as a substitute for plan-invalidation timestamps.
    """
    if start_time is None or not trace or direction not in {"decrease", "increase"}:
        return None
    before = [r for r in trace if float(r.get("sim_time", 0.0)) <= float(start_time)]
    after = [r for r in trace if float(r.get("sim_time", 0.0)) >= float(start_time)]
    if not before or not after:
        return None
    baseline = float(before[-1].get("speed_mps", 0.0))
    need = max(2, int(round(sustain_s * max(1.0, fps))))
    for i, row in enumerate(after):
        speed = float(row.get("speed_mps", 0.0))
        reached = speed <= baseline - delta_mps if direction == "decrease" else speed >= baseline + delta_mps
        if not reached:
            continue
        tail = after[i:i + need]
        if len(tail) < need:
            continue
        if all(
            (float(r.get("speed_mps", 0.0)) <= baseline - delta_mps if direction == "decrease"
             else float(r.get("speed_mps", 0.0)) >= baseline + delta_mps)
            for r in tail
        ):
            return max(0.0, float(row.get("sim_time", start_time)) - float(start_time))
    return None


def _decision_action_change(events: list[dict], transition_time: float | None) -> tuple[str | None, str | None, float | None]:
    if transition_time is None:
        return None, None, None
    decisions = [e for e in events if e.get("event") == "rapid_ad_decision_input" and e.get("action") is not None and _is_number(e.get("t"))]
    before = [e for e in decisions if float(e["t"]) < float(transition_time)]
    after = [e for e in decisions if float(e["t"]) >= float(transition_time)]
    prior_action = str(before[-1].get("action")) if before else None
    for event in after:
        action = str(event.get("action"))
        if prior_action is not None and action != prior_action:
            return prior_action, action, float(event["t"])
    return prior_action, (str(after[0].get("action")) if after else None), None


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _summarize(config: dict, case: dict, timeline: dict, result: dict, episode_dir: Path) -> dict:
    trace = timeline.get("trace") or []
    rows = _metrics_rows(episode_dir / "metrics.csv")
    task = case["task"]
    transition_expected = bool(case.get("control_transition"))
    transition_time = timeline.get("transition_time") if transition_expected else None
    anchor_time = timeline.get("anchor_time")
    fps = max(1.0, float(config.get("fps", 20)))
    scene = config.get("scene") or {}
    safety_buffer = max(0.1, float(scene.get("safety_buffer_m", 1.0)))
    recoverability_calibrated = bool(scene.get("recoverability_calibrated", False))

    # Evidence availability is meaningful only for a real control transition.
    # Static cells may still run a matched input-mask placebo, but have no new cue.
    evidence_time = timeline.get("raw_evidence_available_time") if transition_expected else None
    if evidence_time is None and transition_expected:
        evidence_time = timeline.get("evidence_available_time")

    try:
        events = json.loads((episode_dir / "events.json").read_text(encoding="utf-8"))
    except Exception:
        events = []
    decision_times = [
        float(e.get("t")) for e in events
        if e.get("event") == "rapid_ad_decision_input"
        and isinstance(e.get("image_age_s"), (int, float))
        and float(e.get("image_age_s")) <= (1.5 / fps)
        and not bool(e.get("mask_active"))
    ]
    decision_evidence_time = None
    if decision_times and transition_time is not None:
        decision_evidence_time = min((t for t in decision_times if t >= float(transition_time)), default=None)
    prior_action, first_post_action, action_change_time = _decision_action_change(events, transition_time)
    action_change_latency_transition = (float(action_change_time) - float(transition_time)) if action_change_time is not None and transition_time is not None else None
    action_change_latency_evidence = (float(action_change_time) - float(evidence_time)) if action_change_time is not None and evidence_time is not None and float(action_change_time) >= float(evidence_time) else None

    def _nearest_value(t: float | None, key: str) -> float | None:
        if t is None or not trace:
            return None
        nearest = min(trace, key=lambda r: abs(float(r["sim_time"]) - float(t)))
        try:
            value = float(nearest.get(key))
            return value if math.isfinite(value) else None
        except (TypeError, ValueError):
            return None

    recovery_at_transition = _nearest_value(transition_time, "recoverability_margin_m")
    recovery_at_evidence = _nearest_value(evidence_time, "recoverability_margin_m")
    recovery_at_decision = _nearest_value(decision_evidence_time, "recoverability_margin_m")
    estimated_recoverable = (recovery_at_evidence is not None and recovery_at_evidence > 0.0)
    physical_recoverability = estimated_recoverable if recoverability_calibrated else None

    moving_before_transition = None
    stop_precondition = None
    stop_success = None
    unsafe = None
    response_latency = None
    resume_latency = None
    resume_within = None
    avoidable_failure_estimated = False

    speed_drop_latency_transition = _speed_change_latency(trace, transition_time, "decrease", fps=fps)
    speed_drop_latency_evidence = _speed_change_latency(trace, evidence_time, "decrease", fps=fps)
    speed_increase_latency_evidence = _speed_change_latency(trace, evidence_time, "increase", fps=fps)

    if task == "go_to_stop":
        if transition_expected and transition_time is not None:
            moving_before_transition = any(
                float(r.get("sim_time", 0.0)) >= float(transition_time) - 1.0
                and float(r.get("sim_time", 0.0)) < float(transition_time)
                and float(r.get("speed_mps", 0.0)) >= 0.50
                for r in trace
            )
            stop_success = _has_sustained_stop(
                trace, start=float(transition_time), duration_s=0.5,
                min_front_clearance_m=safety_buffer, fps=fps,
            )
            unsafe = bool(timeline.get("unsafe_crossing_while_stop", False))
            avoidable_failure_estimated = bool(
                moving_before_transition and estimated_recoverable and (unsafe or not stop_success)
            )
            response_latency = _first_brake_response(rows, evidence_time if evidence_time is not None else transition_time)
        # Static GO cells are controls; stopping is not an applicable outcome.
    else:
        # Also measure the STOP precondition in static placebo cells so they can
        # be paired with release cells; no release latency is scored without a real release.
        stop_precondition = bool(timeline.get("stop_confirmed_before_release")) if timeline.get("stop_confirmed_before_release") is not None else False
        unsafe = bool(timeline.get("unsafe_crossing_while_stop", False))
        if transition_expected and transition_time is not None and stop_precondition:
            resume_latency, resume_within = _resume_latency(
                trace, evidence_time if evidence_time is not None else transition_time,
                float(scene.get("resume_response_allowance_s", 3.0)), fps=fps,
            )

    trace_end_time = float(trace[-1].get("sim_time", 0.0)) if trace else None
    resume_allowance = float(scene.get("resume_response_allowance_s", 3.0))
    liveness_followup_duration = (trace_end_time - float(evidence_time)) if trace_end_time is not None and evidence_time is not None else None
    liveness_followup_complete = (
        task == "stop_to_go" and transition_expected and liveness_followup_duration is not None
        and liveness_followup_duration >= resume_allowance
    ) if task == "stop_to_go" and transition_expected else None
    motion_before_evidence_after_release = (
        any(float(r.get("sim_time", 0.0)) >= float(transition_time)
            and float(r.get("sim_time", 0.0)) < float(evidence_time)
            and float(r.get("speed_mps", 0.0)) >= 0.5 for r in trace)
        if task == "stop_to_go" and transition_expected and transition_time is not None and evidence_time is not None
        else None
    )

    # Strictly separate simulator setup, stimulus exposure, and behavioral outcome.
    setup_errors = result.get("setup_errors") or result.get("scene_setup_errors") or []
    scene_valid_flag = result.get("scene_setup_valid", result.get("setup_valid", True))
    setup_valid = bool(scene_valid_flag) and not bool(setup_errors) and bool(timeline.get("geometry_ready"))
    if timeline.get("geometry_error"):
        setup_valid = False
    anchor_reached = bool(timeline.get("anchor_triggered"))
    transition_applied = (transition_time is not None and timeline.get("transition_error") is None) if transition_expected else None
    phase_target = case.get("phase_margin_target_m") if task == "go_to_stop" else None
    phase_anchor_error = (float(timeline.get("anchor_margin_m")) - float(phase_target)) if anchor_reached and phase_target is not None and timeline.get("anchor_margin_m") is not None else None
    phase_anchor_tolerance = float(scene.get("phase_anchor_tolerance_m", 0.75))
    anchor_time_error = (float(anchor_time) - float(case.get("release_wait_after_start_s"))) if task == "stop_to_go" and anchor_time is not None else None
    if task == "stop_to_go":
        phase_anchor_valid = bool(anchor_reached and anchor_time_error is not None and abs(anchor_time_error) <= max(0.10, 1.0 / fps))
    else:
        phase_anchor_valid = bool(anchor_reached and (phase_anchor_error is None or abs(phase_anchor_error) <= phase_anchor_tolerance))
    gap_planned = bool(case.get("evidence_gap")) and case.get("gap_timing") != "none"
    mask_start = timeline.get("input_mask_start_time")
    mask_end = timeline.get("input_mask_end_time")
    actual_mask_duration = (float(mask_end) - float(mask_start)) if mask_start is not None and mask_end is not None else None
    requested_mask_duration = max(0.1, float(case.get("gap_duration_s", 1.0)))
    mask_duration_ok = (
        actual_mask_duration is not None
        and actual_mask_duration >= max(0.20, 0.50 * requested_mask_duration)
        and actual_mask_duration <= 2.00 * requested_mask_duration + 2.0 / fps
    )
    timing = str(case.get("gap_timing", "none"))
    realized_anchor = anchor_time
    if not gap_planned:
        gap_timing_realized = True
    elif realized_anchor is None or mask_start is None or mask_end is None:
        gap_timing_realized = False
    elif timing == "pre":
        gap_timing_realized = float(mask_start) <= float(realized_anchor) and float(mask_end) <= float(realized_anchor) + 2.0 / fps
    elif timing == "overlap":
        gap_timing_realized = float(mask_start) <= float(realized_anchor) and float(mask_end) >= float(realized_anchor) + 0.25 * requested_mask_duration
    elif timing == "post":
        gap_timing_realized = float(mask_start) <= float(realized_anchor) + 2.0 / fps and float(mask_end) >= float(realized_anchor) + 0.50 * requested_mask_duration
    else:
        gap_timing_realized = False
    if case.get("evidence_mode", "frame_hold") == "frame_hold":
        input_mask_realized = (
            not bool(timeline.get("mask_cache_miss", False))
            and (not gap_planned or (
                mask_start is not None and mask_end is not None
                and int(timeline.get("mask_substitution_count", 0)) > 0
                and mask_duration_ok and gap_timing_realized
            ))
        )
    else:
        # Physical occlusion is experimental only until line-of-sight occlusion is verified.
        input_mask_realized = bool(timeline.get("physical_occlusion_verified", False))

    exposure_valid = bool(
        setup_valid and anchor_reached and phase_anchor_valid
        and ((not transition_expected) or transition_applied)
        and input_mask_realized
    )
    if task == "go_to_stop":
        behavior_precondition_valid = (moving_before_transition is True) if transition_expected else anchor_reached
        valid_for_safety_analysis = bool(exposure_valid and behavior_precondition_valid)
        valid_for_liveness_analysis = False
    else:
        behavior_precondition_valid = bool(stop_precondition)
        # A failure to establish STOP is still a safety outcome, but it is not
        # a valid sample for measuring post-release liveness.
        valid_for_safety_analysis = bool(exposure_valid)
        valid_for_liveness_analysis = bool(
            exposure_valid and behavior_precondition_valid
            and (not transition_expected or liveness_followup_complete)
        )
    causal_valid = bool(
        (valid_for_safety_analysis if task == "go_to_stop" else valid_for_liveness_analysis)
        and ((not transition_expected) or evidence_time is not None)
    )

    if not setup_valid:
        failure_type = "invalid_setup"
    elif not anchor_reached:
        failure_type = "anchor_not_reached"
    elif not phase_anchor_valid:
        failure_type = "phase_anchor_invalid"
    elif not input_mask_realized:
        failure_type = "evidence_intervention_not_realized" if gap_planned else "baseline_frame_guard_not_realized"
    elif transition_expected and not transition_applied:
        failure_type = "transition_not_applied"
    elif transition_expected and task == "go_to_stop" and not moving_before_transition:
        failure_type = "not_exposed_moving"
    elif transition_expected and task == "stop_to_go" and not stop_precondition:
        failure_type = "initial_stop_not_established"
    elif transition_expected and evidence_time is None:
        failure_type = "evidence_availability_unmeasured"
    elif task == "go_to_stop" and transition_expected:
        if recovery_at_evidence is not None and recovery_at_evidence <= 0.0:
            failure_type = "unrecoverable_before_evidence" if (unsafe or not stop_success) else "ok"
        elif unsafe:
            failure_type = "unsafe_continuation"
        elif not stop_success:
            if recovery_at_decision is not None and recovery_at_decision <= 0.0:
                failure_type = "decision_after_recovery_deadline"
            else:
                failure_type = "stop_not_completed"
        else:
            failure_type = "ok"
    elif task == "stop_to_go" and transition_expected:
        if unsafe:
            failure_type = "unsafe_continuation"
        elif not liveness_followup_complete:
            failure_type = "right_censored_after_release"
        elif resume_latency is None or not bool(resume_within):
            failure_type = "stale_retention"
        else:
            failure_type = "ok"
    elif task == "stop_to_go" and unsafe:
        failure_type = "unsafe_continuation"
    elif task == "stop_to_go" and not stop_precondition:
        failure_type = "initial_stop_not_established"
    else:
        failure_type = "ok"

    # Root-cause labels are deliberately diagnostic candidates, not claims about
    # unobservable internal belief or plan states. They use only logged external
    # behavior plus controller-provided decision history when available.
    semantic_fields = {"reasoning", "rationale", "text", "response", "instruction", "state", "plan", "trajectory"}
    decision_semantics_available = any(
        isinstance(e.get("decision_summary"), dict)
        and any(k in semantic_fields and e.get("decision_summary", {}).get(k) not in (None, "") for k in semantic_fields)
        for e in events if e.get("event") == "rapid_ad_decision_input"
    )
    if not setup_valid:
        diagnostic_class = "invalid_setup"
    elif not exposure_valid:
        diagnostic_class = "invalid_or_unmatched_exposure"
    elif not transition_expected:
        diagnostic_class = "static_placebo_control"
    elif evidence_time is None:
        diagnostic_class = "first_fresh_frame_time_unmeasured"
    elif task == "go_to_stop":
        if recovery_at_evidence is not None and recovery_at_evidence <= 0.0:
            diagnostic_class = "estimated_unrecoverable_at_first_fresh_frame"
        elif stop_success and not unsafe:
            diagnostic_class = "safe_stop_after_control_change"
        elif action_change_time is None:
            diagnostic_class = "failed_response_internal_belief_vs_plan_unresolved"
        elif action_change_time < float(evidence_time):
            diagnostic_class = "action_changed_before_first_fresh_frame"
        elif recovery_at_decision is not None and recovery_at_decision <= 0.0:
            diagnostic_class = "action_change_after_estimated_recovery_deadline"
        elif unsafe:
            diagnostic_class = "unsafe_crossing_despite_observed_action_change"
        else:
            diagnostic_class = "action_changed_but_stop_not_completed"
    else:
        if not stop_precondition:
            diagnostic_class = "initial_stop_not_established"
        elif not liveness_followup_complete:
            diagnostic_class = "right_censored_after_release"
        elif resume_latency is None or not bool(resume_within):
            diagnostic_class = "stale_retention_behavior_internal_cause_unresolved"
        else:
            diagnostic_class = "timely_resume_after_release"
    diagnostic_basis = [
        f"failure_type={failure_type}",
        f"recoverability_calibrated={recoverability_calibrated}",
        f"decision_action_change_observed={action_change_time is not None}",
        f"decision_semantics_available={decision_semantics_available}",
        "first fresh frame is not confirmed as visually legible until manual audit",
    ]
    cause_localization_level = "decision_trace_semantics_available" if decision_semantics_available else "external_behavior_only"

    # Margin is summarized only over the control-transition response window, not
    # the whole episode (which may correctly proceed past the virtual line).
    min_margin_window = None
    if task == "go_to_stop" and transition_time is not None:
        window_end = float(transition_time) + 5.0
        if timeline.get("first_unsafe_crossing_time") is not None:
            window_end = min(window_end, float(timeline["first_unsafe_crossing_time"]))
        relevant = [float(r["recoverability_margin_m"]) for r in trace
                    if float(transition_time) <= float(r.get("sim_time", -1)) <= window_end
                    and isinstance(r.get("recoverability_margin_m"), (int, float))]
        min_margin_window = min(relevant) if relevant else None

    collision_count = 0.0
    if rows:
        collision_count = max([float(r.get("collision_count", 0.0) or 0.0) for r in rows] + [0.0])
    max_overshoot = max((max(0.0, -float(r.get("front_clearance_m", 0.0)))
                         for r in trace if r.get("current_directive") == "STOP"), default=0.0)
    # Preserve scalar MARSHAL criterion results alongside the custom virtual-line
    # metrics so reviewers can compare the two independently defined oracles.
    marshal_criteria = {}
    for criterion_name, criterion in (result.get("criteria") or {}).items():
        if not isinstance(criterion, dict):
            continue
        metrics = criterion.get("metrics") or {}
        marshal_criteria[str(criterion_name)] = {
            "passed": criterion.get("passed"),
            "metrics": {str(k): v for k, v in metrics.items()
                        if v is None or isinstance(v, (bool, int, float, str))},
        }
    final = {
        "schema_version": 3,
        "case": case,
        "controller": config.get("controller"),
        "controller_uses_visual_evidence": str(config.get("controller", "")).lower() in {"vlm", "transfuser", "tcp", "interfuser", "openemma", "lmdrive", "full_planner"},
        "controller_is_privileged_oracle": str(config.get("controller", "")).lower() == "rapid_ad_oracle",
        "episode_id": config.get("episode_id"),
        "marshal_success": result.get("success"),
        "marshal_termination": result.get("termination"),
        "marshal_criteria": marshal_criteria,
        "setup_valid": setup_valid,
        "exposure_valid": exposure_valid,
        "behavior_precondition_valid": behavior_precondition_valid,
        "valid_for_safety_analysis": valid_for_safety_analysis,
        "valid_for_liveness_analysis": valid_for_liveness_analysis,
        "valid_for_causal_analysis": causal_valid,
        "setup_errors": setup_errors,
        "anchor_status": "reached" if anchor_reached else "not_reached",
        "anchor_time_s": anchor_time,
        "anchor_distance_m": timeline.get("anchor_distance_m"),
        "anchor_margin_m": timeline.get("anchor_margin_m"),
        "phase_margin_target_m": phase_target,
        "phase_anchor_error_m": phase_anchor_error,
        "phase_anchor_tolerance_m": phase_anchor_tolerance if phase_target is not None else None,
        "phase_anchor_valid": phase_anchor_valid,
        "anchor_time_error_s": anchor_time_error,
        "transition_expected": transition_expected,
        "transition_applied": transition_applied,
        "transition_time_s": transition_time,
        "transition_distance_actual_m": timeline.get("transition_distance_actual_m"),
        "transition_error": timeline.get("transition_error"),
        "planned_gap_start_time_s": timeline.get("evidence_gap_start_time"),
        "planned_gap_end_time_s": timeline.get("evidence_gap_end_time"),
        "input_mask_start_time_s": timeline.get("input_mask_start_time"),
        "input_mask_end_time_s": timeline.get("input_mask_end_time"),
        "requested_mask_duration_s": requested_mask_duration if gap_planned else None,
        "actual_mask_duration_s": actual_mask_duration,
        "mask_duration_ok": mask_duration_ok if gap_planned else None,
        "gap_timing_realized": gap_timing_realized,
        "input_mask_realized": input_mask_realized,
        "mask_substitution_count": int(timeline.get("mask_substitution_count", 0)),
        "mask_cache_miss": bool(timeline.get("mask_cache_miss", False)),
        "visual_audit_required": bool(transition_expected),
        "visual_audit_status": "pending_manual_audit" if transition_expected else "placebo_no_transition",
        "raw_evidence_available_time_s": evidence_time,
        "evidence_available_time_s": evidence_time,
        "first_fresh_frame_time_s": evidence_time,
        "evidence_time_semantics": "first unmasked front-RGB frame delivered after an actual control transition; it is treated as usable evidence only after visual cue audit; null for static placebo cells",
        "controller_evidence_consumed_time_s": decision_evidence_time,
        "last_decision_action_before_transition": prior_action,
        "first_decision_action_after_transition": first_post_action,
        "first_decision_action_change_time_s": action_change_time,
        "decision_action_change_latency_from_transition_s": action_change_latency_transition,
        "decision_action_change_latency_from_evidence_s": action_change_latency_evidence,
        "speed_drop_latency_from_transition_s": speed_drop_latency_transition,
        "speed_drop_latency_from_evidence_s": speed_drop_latency_evidence,
        "speed_increase_latency_from_evidence_s": speed_increase_latency_evidence,
        "recoverability_estimate_calibrated": recoverability_calibrated,
        "recoverability_margin_at_transition_m": recovery_at_transition,
        "recoverability_margin_at_evidence_m": recovery_at_evidence,
        "estimated_recoverable_at_evidence": estimated_recoverable if evidence_time is not None else None,
        "recoverability_model_predicts_recoverable_at_evidence": estimated_recoverable if evidence_time is not None else None,
        # Deprecated compatibility field: an estimated margin is not a physical proof.
        "physically_recoverable_at_evidence": None,
        "recoverability_estimator_disagreement": bool(
            task == "go_to_stop" and evidence_time is not None and stop_success is True
            and recovery_at_evidence is not None and recovery_at_evidence <= 0.0
        ),
        "recoverability_margin_at_controller_decision_m": recovery_at_decision,
        "controller_decision_after_recovery_deadline": (recovery_at_decision is not None and recovery_at_decision <= 0.0),
        "minimum_recoverability_margin_m": min_margin_window,
        "minimum_margin_window_semantics": "minimum from actual GO->STOP transition to first crossing or 5s afterward; null for other tasks",
        "stop_success": stop_success,
        "moving_before_transition_or_anchor": moving_before_transition,
        "stop_confirmed_before_release": stop_precondition,
        "unsafe_crossing_while_stop": unsafe,
        "max_overshoot_while_stop_m": max_overshoot,
        "command_response_latency_s": response_latency,
        # Backward-compatible alias; this is command response, not measured deceleration.
        "observable_brake_response_latency_s": response_latency,
        "resume_latency_s": resume_latency,
        "resume_within_allowance": resume_within,
        "motion_before_evidence_after_release": motion_before_evidence_after_release,
        "resume_allowance_s": resume_allowance if task == "stop_to_go" and transition_expected else None,
        "liveness_followup_duration_s": liveness_followup_duration if task == "stop_to_go" and transition_expected else None,
        "liveness_followup_complete": liveness_followup_complete,
        "collision_count": collision_count,
        "failure_type": failure_type,
        "diagnostic_class": diagnostic_class,
        "diagnostic_basis": diagnostic_basis,
        "cause_localization_level": cause_localization_level,
        "decision_semantics_available": decision_semantics_available,
        "avoidable_failure_estimated": avoidable_failure_estimated if task == "go_to_stop" else (
            bool(transition_expected and stop_precondition and liveness_followup_complete and (resume_latency is None or not resume_within))
            if transition_expected and stop_precondition and liveness_followup_complete else (False if not transition_expected else None)
        ),
        "avoidable_failure": (avoidable_failure_estimated if recoverability_calibrated else None) if task == "go_to_stop" else (
            bool(transition_expected and stop_precondition and liveness_followup_complete and (resume_latency is None or not resume_within))
            if transition_expected and stop_precondition and liveness_followup_complete else (False if not transition_expected else None)
        ),
        "trace_samples": len(trace),
        "terminated_reason": result.get("terminated_reason"),
        "privileged_ground_truth_provided": bool(result.get("privileged_ground_truth_provided", False)),
        "diagnostic_frames": timeline.get("diagnostic_frames", []),
        "notes": [
            "Static control cells are placebo controls; they have no control-transition evidence time and release latency is not applicable without a release.",
            "Recoverability margin is an analytical estimate unless scene.recoverability_calibrated is explicitly true after vehicle-specific braking calibration.",
            "For black-box controllers, belief-update and plan-invalidation times are not directly observable; report external response latency only.",
            "Frame holding changes only the front-RGB input. Do not interpret it as physical occlusion or as masking other sensor modalities.",
            "The pre/overlap mask start is predicted from recent margin slope; only measured mask timestamps determine realized timing.",
            "Dynamic cue visibility must be manually audited from diagnostic frames before final causal claims.",
            "Invalid setup/exposure episodes must be reported and excluded from causal outcome denominators.",
        ],
    }
    return final

def run(client: Any, config: dict, logger: EpisodeLogger) -> dict:
    import_carla()
    case = _case_from_config(config)
    config["rapid_ad"] = case
    config["town"] = config.get("town") or "Town03"
    # Keep both common MARSHAL config spellings set, so the static background
    # signal remains green regardless of which helper consumes the field.
    config["traffic_light_state"] = "Green"
    config["traffic_light"] = dict(config.get("traffic_light") or {})
    config["traffic_light"].update({"state": "Green", "freeze": True, "pin": True})
    config.setdefault("weather", "ClearNoon")
    config.setdefault("visibility", "full")
    config["timeout_sec"] = float(config.get("timeout_sec", 22))
    config["fps"] = float(config.get("fps", 20))
    config["expected_behavior"] = dict(config.get("expected_behavior") or {})
    # HOLD prevents MARSHAL's static STOP/PROCEED early-termination criteria
    # from truncating a dynamic episode. RAPID-AD metrics are scored separately.
    config["expected_behavior"]["action"] = "HOLD"
    config["officer"] = dict(config.get("officer") or {})
    task = case["task"]
    initial = "PROCEED" if task == "go_to_stop" else "STOP"
    config["officer"].update({
        "authority_type": "flagger",
        "authorized": True,
        "gesture": initial,
        "onset_time": 0.0,
        "duration": None,
        "target_relation": "ego",
        "distance": float(config["officer"].get("distance", 18.0)),
        "lateral_offset": float(config["officer"].get("lateral_offset", 3.2)),
        "use_skeleton": True,
        "use_debug_visuals": False,
        "hand_prop": None,
    })
    scene = dict(config.get("scene") or {})
    scene.setdefault("control_line_offset_m", 3.0)
    scene.setdefault("max_brake_decel_mps2", 4.5)
    scene.setdefault("reaction_budget_s", 0.10)
    scene.setdefault("safety_buffer_m", 1.0)
    config["scene"] = scene
    config["seed"] = int(case.get("seed", config.get("seed", 1)))

    timeline = {
        "task": task,
        "initial_directive": initial,
        "current_directive": initial,
        "transition_time": None,
        "anchor_time": None,
        "anchor_triggered": False,
        "evidence_gap_active": False,
        "evidence_gap_start_time": None,
        "evidence_gap_end_time": None,
        "estimated_time_to_anchor_s": None,
        "previous_anchor_signal": None,
        "previous_anchor_signal_time": None,
        "mask_substitution_count": 0,
        "physical_occlusion_verified": False,
        "input_mask_start_time": None,
        "input_mask_end_time": None,
        "mask_cache_miss": False,
        "diagnostic_frames": [],
        "evidence_available_time": None,
        "raw_evidence_available_time": None,
        "first_fresh_image_time": None,
        "has_evidence_wrapper": False,
        "unsafe_crossing_while_stop": False,
        "first_unsafe_crossing_time": None,
        "trace": [],
        "geometry_ready": False,
    }

    controller_name = str(config.get("controller") or "tm")
    if controller_name.lower() in {"rapid_ad_oracle", "oracle"}:
        controller = DynamicDirectiveOracleController(config=config, timeline=timeline)
        config["controller"] = "rapid_ad_oracle"
    else:
        controller = make_controller(controller_name, config=config)
    evidence_mode = str(case.get("evidence_mode", "frame_hold"))
    if controller is not None and evidence_mode == "frame_hold":
        controller = EvidenceFrameHold(controller, timeline, logger, fps=float(config["fps"]))
        timeline["has_evidence_wrapper"] = True

    setup_extra_actors = _setup_extra_actors(config, case)
    logger.log_event(
        "rapid_ad_scenario_intent",
        case_id=case.get("case_id"),
        task=task,
        control_transition=bool(case.get("control_transition")),
        evidence_gap=bool(case.get("evidence_gap")),
        gap_timing=case.get("gap_timing"),
        phase=case.get("phase"),
        evidence_mode=evidence_mode,
        initial_directive=initial,
        target_speed_kmh=float((config.get("ego") or {}).get("target_speed", 12.0)),
    )

    result = run_scenario(
        client,
        config,
        logger,
        expected_gesture=_enum(initial),
        expected_action="HOLD",
        name="rapid_ad_factorial",
        setup_extra_actors=setup_extra_actors,
        tick_extra_actors=_make_tick_hook(config, case, timeline, logger),
        controller=controller,
    )
    # The custom metric file is independent of MARSHAL's static-action score.
    logger.flush()
    summary = _summarize(config, case, timeline, result or {}, Path(logger.episode_dir))
    summary["control_line_geometry"] = {
        "origin_x": timeline.get("origin_x"),
        "origin_y": timeline.get("origin_y"),
        "forward_x": timeline.get("forward_x"),
        "forward_y": timeline.get("forward_y"),
        "line_station_m": timeline.get("line_station_m"),
        "line_x": timeline.get("line_x"),
        "line_y": timeline.get("line_y"),
        "control_line_offset_m": timeline.get("control_line_offset_m"),
        "geometry_error": timeline.get("geometry_error"),
    }
    summary["timeline"] = {
        "initial_directive": timeline.get("initial_directive"),
        "final_directive": timeline.get("current_directive"),
        "anchor_time_s": timeline.get("anchor_time"),
        "transition_time_s": timeline.get("transition_time"),
        "transition_error": timeline.get("transition_error"),
        "first_unsafe_crossing_time_s": timeline.get("first_unsafe_crossing_time"),
    }
    (Path(logger.episode_dir) / "rapid_ad_metrics.json").write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")
    (Path(logger.episode_dir) / "rapid_ad_trace.json").write_text(json.dumps(timeline.get("trace") or [], indent=2), encoding="utf-8")
    logger.log_event("rapid_ad_summary", **{k: v for k, v in summary.items() if k not in {"case", "notes", "control_line_geometry", "timeline"}})
    logger.flush()
    return result or {}


__all__ = ["run"]
