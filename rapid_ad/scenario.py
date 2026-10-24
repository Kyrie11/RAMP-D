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
    spawn_cfg = (config.get("ego") or {}).get("spawn_transform") or {}
    try:
        origin_x = float(spawn_cfg["x"])
        origin_y = float(spawn_cfg["y"])
        yaw = math.radians(float(spawn_cfg["yaw"]))
        fx, fy = math.cos(yaw), math.sin(yaw)
    except Exception:
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


def _gap_active_go_to_stop(case: dict, d_line: float) -> bool:
    if case.get("evidence_mode", "frame_hold") == "physical_occluder":
        return False
    if not case.get("evidence_gap") or case.get("gap_timing") == "none":
        return False
    target = float(case.get("transition_distance_m", 9.0))
    span = max(0.1, float(case.get("gap_span_m", 2.5)))
    timing = case.get("gap_timing")
    if timing == "pre":
        return target < d_line <= target + span
    if timing == "overlap":
        return target - span / 2.0 < d_line <= target + span / 2.0
    if timing == "post":
        return target - span <= d_line <= target
    return False


def _gap_active_stop_to_go(case: dict, sim_time: float) -> bool:
    if case.get("evidence_mode", "frame_hold") == "physical_occluder":
        return False
    if not case.get("evidence_gap") or case.get("gap_timing") == "none":
        return False
    anchor = float(case.get("release_wait_after_start_s", 3.0))
    duration = max(0.1, float(case.get("gap_duration_s", 1.0)))
    timing = case.get("gap_timing")
    if timing == "pre":
        return anchor - duration <= sim_time < anchor
    if timing == "overlap":
        return anchor - duration / 2.0 <= sim_time < anchor + duration / 2.0
    if timing == "post":
        return anchor <= sim_time < anchor + duration
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

        task = case["task"]
        transition_enabled = bool(case.get("control_transition"))
        anchor = timeline.get("anchor_time")
        if task == "go_to_stop":
            target = float(case.get("transition_distance_m", 9.0))
            if anchor is None and d_line <= target:
                timeline["anchor_time"] = float(sim_time)
                timeline["anchor_distance_m"] = float(d_line)
                timeline["anchor_triggered"] = True
                logger.log_event(
                    "rapid_ad_phase_anchor", t=sim_time,
                    distance_to_control_line_m=d_line,
                    target_distance_m=target,
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
                timeline["anchor_time"] = float(release_time)
                timeline["anchor_triggered"] = True
                timeline["anchor_distance_m"] = float(d_line)
                timeline["stop_confirmed_before_release"] = _has_sustained_stop(
                    timeline.get("trace", []), end=release_time - 1.0 / fps
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
            gap_active = _gap_active_go_to_stop(case, d_line)
        else:
            gap_active = _gap_active_stop_to_go(case, float(sim_time))
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
        )

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


def _has_sustained_stop(trace: list[dict], start: float = 0.0, end: float | None = None, duration_s: float = 0.5) -> bool:
    samples = [r for r in trace if float(r.get("sim_time", 0.0)) >= start and (end is None or float(r.get("sim_time", 0.0)) <= end)]
    if len(samples) < 2:
        return False
    need = max(2, int(round(duration_s * 20)))
    run = 0
    for row in samples:
        if float(row.get("speed_mps", 999.0)) < 0.20 and float(row.get("front_clearance_m", -999.0)) > 0.25:
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


def _resume_latency(trace: list[dict], evidence_time: float | None, allowance_s: float) -> tuple[float | None, bool]:
    if evidence_time is None:
        return None, False
    samples = [r for r in trace if float(r.get("sim_time", 0.0)) >= evidence_time]
    need = max(2, int(round(0.5 * 20)))
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


def _summarize(config: dict, case: dict, timeline: dict, result: dict, episode_dir: Path) -> dict:
    trace = timeline.get("trace") or []
    rows = _metrics_rows(episode_dir / "metrics.csv")
    task = case["task"]
    transition_time = timeline.get("transition_time")
    anchor_time = timeline.get("anchor_time")
    evidence_time = timeline.get("raw_evidence_available_time")
    if evidence_time is None:
        evidence_time = timeline.get("evidence_available_time")
    if evidence_time is None and anchor_time is not None and not case.get("evidence_gap"):
        evidence_time = float(anchor_time)
    if evidence_time is None and timeline.get("evidence_gap_end_time") is not None:
        evidence_time = float(timeline["evidence_gap_end_time"])
    # Prefer the first fresh image actually consumed by a model decision, when
    # that interface exposes decision_history (e.g. MARSHAL's VLM controller).
    try:
        events = json.loads((episode_dir / "events.json").read_text(encoding="utf-8"))
    except Exception:
        events = []
    decision_times = [
        float(e.get("t")) for e in events
        if e.get("event") == "rapid_ad_decision_input"
        and isinstance(e.get("image_age_s"), (int, float))
        and float(e.get("image_age_s")) <= (1.5 / max(1.0, float(config.get("fps", 20))))
        and not bool(e.get("mask_active"))
    ]
    decision_evidence_time = None
    if decision_times and transition_time is not None:
        decision_evidence_time = min((t for t in decision_times if t >= float(transition_time)), default=None)

    recovery_at_evidence = None
    if evidence_time is not None and trace:
        nearest = min(trace, key=lambda r: abs(float(r["sim_time"]) - float(evidence_time)))
        recovery_at_evidence = float(nearest.get("recoverability_margin_m", float("nan")))
    physically_recoverable = (recovery_at_evidence is not None and math.isfinite(recovery_at_evidence) and recovery_at_evidence > 0.0)
    recovery_at_decision = None
    if decision_evidence_time is not None and trace:
        nearest_decision = min(trace, key=lambda r: abs(float(r["sim_time"]) - float(decision_evidence_time)))
        recovery_at_decision = float(nearest_decision.get("recoverability_margin_m", float("nan")))

    if task == "go_to_stop":
        stop_success = _has_sustained_stop(trace, start=float(transition_time or 0.0)) if case.get("control_transition") else _has_sustained_stop(trace)
        unsafe = bool(timeline.get("unsafe_crossing_while_stop", False))
        moving_before_transition = False
        anchor_reference = transition_time if transition_time is not None else anchor_time
        if anchor_reference is not None:
            moving_before_transition = any(
                float(r.get("sim_time", 0.0)) >= float(anchor_reference) - 1.0
                and float(r.get("sim_time", 0.0)) < float(anchor_reference)
                and float(r.get("speed_mps", 0.0)) >= 0.50
                for r in trace
            )
        avoidable_failure = bool(case.get("control_transition") and physically_recoverable and (unsafe or not stop_success) and moving_before_transition)
        decision_late = recovery_at_decision is not None and math.isfinite(recovery_at_decision) and recovery_at_decision <= 0.0
        if unsafe and evidence_time is None:
            failure_type = "evidence_availability_unmeasured"
        elif unsafe and not physically_recoverable:
            failure_type = "unrecoverable_before_evidence"
        elif unsafe and decision_late:
            failure_type = "decision_after_recovery_deadline"
        elif unsafe:
            failure_type = "unsafe_continuation"
        elif case.get("control_transition") and moving_before_transition and not stop_success and evidence_time is None:
            failure_type = "evidence_availability_unmeasured"
        elif case.get("control_transition") and moving_before_transition and not stop_success and not physically_recoverable:
            failure_type = "unrecoverable_before_evidence"
        elif case.get("control_transition") and moving_before_transition and not stop_success and physically_recoverable:
            failure_type = "stop_not_completed"
        elif not timeline.get("anchor_triggered") and case.get("control_transition"):
            failure_type = "anchor_not_reached"
        elif not moving_before_transition and case.get("control_transition"):
            failure_type = "not_exposed_moving"
        else:
            failure_type = "ok"
        response_latency = _first_brake_response(rows, evidence_time if evidence_time is not None else transition_time)
        resume_latency, resume_within = None, None
    else:
        release_event = transition_time if case.get("control_transition") else None
        stop_precondition = bool(timeline.get("stop_confirmed_before_release", _has_sustained_stop(trace, end=float(anchor_time or 0.0))))
        stop_success = _has_sustained_stop(trace, end=float(anchor_time or 0.0))
        unsafe = bool(timeline.get("unsafe_crossing_while_stop", False))
        resume_latency, resume_within = _resume_latency(
            trace,
            evidence_time if evidence_time is not None else release_event,
            float((config.get("scene") or {}).get("resume_response_allowance_s", 3.0)),
        )
        if not stop_precondition:
            resume_latency, resume_within = None, None
        avoidable_failure = bool(case.get("control_transition") and stop_precondition and evidence_time is not None and (resume_latency is None or not resume_within))
        if unsafe:
            failure_type = "unsafe_continuation"
        elif case.get("control_transition") and stop_precondition and evidence_time is None:
            failure_type = "evidence_availability_unmeasured"
        elif avoidable_failure:
            failure_type = "stale_retention"
        elif not stop_precondition:
            failure_type = "initial_stop_not_established"
        else:
            failure_type = "ok"
        response_latency = None

    collision_count = 0.0
    if rows:
        collision_count = max([float(r.get("collision_count", 0.0) or 0.0) for r in rows] + [0.0])
    setup_errors = result.get("setup_errors") or result.get("scene_setup_errors") or []
    scene_valid_flag = result.get("scene_setup_valid", result.get("setup_valid", True))
    setup_valid = bool(scene_valid_flag) and not bool(setup_errors) and bool(timeline.get("geometry_ready"))
    if timeline.get("geometry_error"):
        setup_valid = False
    if not timeline.get("anchor_triggered"):
        anchor_status = "not_reached"
    else:
        anchor_status = "reached"
    min_margin = min((float(r.get("recoverability_margin_m", 0.0)) for r in trace), default=None)
    max_overshoot = max((max(0.0, -float(r.get("front_clearance_m", 0.0))) for r in trace if r.get("current_directive") == "STOP"), default=0.0)
    final = {
        "schema_version": 1,
        "case": case,
        "controller": config.get("controller"),
        "controller_uses_visual_evidence": str(config.get("controller", "")).lower() in {"vlm", "transfuser", "tcp", "interfuser", "openemma", "lmdrive", "full_planner"},
        "controller_is_privileged_oracle": str(config.get("controller", "")).lower() == "rapid_ad_oracle",
        "episode_id": config.get("episode_id"),
        "setup_valid": setup_valid,
        "setup_errors": setup_errors,
        "anchor_status": anchor_status,
        "anchor_time_s": anchor_time,
        "transition_time_s": transition_time,
        "transition_distance_actual_m": timeline.get("transition_distance_actual_m"),
        "evidence_gap_start_time_s": timeline.get("evidence_gap_start_time"),
        "evidence_gap_end_time_s": timeline.get("evidence_gap_end_time"),
        "raw_evidence_available_time_s": evidence_time,
        "evidence_available_time_s": evidence_time,
        "evidence_time_semantics": "fresh input frame after the phase anchor; for static controls this is a matched pseudo-anchor, not a new rule cue",
        "controller_evidence_consumed_time_s": decision_evidence_time,
        "recoverability_margin_at_evidence_m": recovery_at_evidence,
        "physically_recoverable_at_evidence": physically_recoverable,
        "recoverability_margin_at_controller_decision_m": recovery_at_decision,
        "controller_decision_after_recovery_deadline": (recovery_at_decision is not None and math.isfinite(recovery_at_decision) and recovery_at_decision <= 0.0),
        "minimum_recoverability_margin_m": min_margin,
        "stop_success": bool(stop_success),
        "moving_before_transition_or_anchor": (moving_before_transition if task == "go_to_stop" else None),
        "stop_confirmed_before_release": timeline.get("stop_confirmed_before_release"),
        "unsafe_crossing_while_stop": unsafe,
        "max_overshoot_while_stop_m": max_overshoot,
        "observable_brake_response_latency_s": response_latency,
        "resume_latency_s": resume_latency,
        "resume_within_allowance": resume_within,
        "collision_count": collision_count,
        "failure_type": failure_type,
        "avoidable_failure": bool(avoidable_failure),
        "trace_samples": len(trace),
        "terminated_reason": result.get("terminated_reason"),
        "privileged_ground_truth_provided": bool(result.get("privileged_ground_truth_provided", False)),
        "notes": [
            "The built-in MARSHAL static expected-action score is not the primary outcome for this dynamic sequence.",
            "For black-box controllers, belief-update and plan-invalidation times are not directly observable; response latency is behavioral evidence only.",
            "In static/no-transition controls, raw_evidence_available_time_s is a matched pseudo-anchor frame time, not a new rule cue.",
            "A failure is labelled avoidable only when the estimated recovery margin at evidence availability is positive.",
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
