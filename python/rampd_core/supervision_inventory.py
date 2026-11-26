"""Audit which paper losses have defensible labels in one WOMD/AV2 scene.

An inventory is NOT a label generator and NOT safety or task certification.
It deliberately distinguishes a recorded traffic-light state from exogenous
rule activation/effectivity and a dataset `observed` bit from sensor awareness.
"""
from __future__ import annotations
from .scene_schema import UnifiedScene
from .phase6c import build_scene_forecast_sample
from .logged_factual_labels import factual_joint_labels, sampled_signal_changes


def supervision_inventory(scene: UnifiedScene) -> dict:
    scene.assert_valid()
    sample = build_scene_forecast_sample(scene)
    logged = tuple(t.track_id for t in sample.future_targets if any(t.valid_future_mask))
    benchmark = tuple(t.track_id for t in sample.future_targets
                      if t.benchmark_target and any(t.valid_future_mask))
    factual = factual_joint_labels(sample, 1)
    signal_brackets = sampled_signal_changes(sample)
    future_signal_count = len(sample.future_signal_targets)
    ctx = scene.map_context
    polygons = (() if ctx is None else tuple(p for p in ctx.primitives
                if p.geometry_type == 'polygon'))
    has_complete_polygon_map = bool(ctx is not None and ctx.complete_geometry and polygons)
    actors_with_shapes = set()
    for t in scene.tracks:
        if any(s.valid and s.length is not None and s.width is not None and
               s.length > 0 and s.width > 0 for s in t.states):
            actors_with_shapes.add(t.track_id)
    geometry_candidates = tuple(sorted(actors_with_shapes.intersection(logged)))
    occupancy_ready = bool(has_complete_polygon_map and geometry_candidates)
    return {
        'schema':'rampd.phase6c.supervision-inventory.v2',
        'dataset':sample.dataset, 'split':sample.split,
        'scenario_id':sample.scenario_id, 'future_available':sample.future_available,
        'labels':{
            'L_joint':{'status':('LOGGED_EGO_PATH_SURROGATE' if factual.usable else
                                 'LOGGED_TRAJECTORY_ONLY' if logged else 'UNAVAILABLE'),
                       'conditioned_prefix_status':factual.status, 'prefix_probe_steps':1,
                       'target_track_ids':list(logged),
                       'benchmark_track_ids':list(benchmark),
                       'counterfactual_response':'UNAVAILABLE'},
            'L_event':{'status':'AUXILIARY_SIGNAL_STATE_ONLY' if future_signal_count else 'UNAVAILABLE',
                       'future_logged_signal_count':future_signal_count,
                       'auxiliary_sampled_change_brackets':len(signal_brackets),
                       'exogenous_activation_and_effectivity':'UNAVAILABLE'},
            'L_occupancy':{'status':'CANDIDATE_GEOMETRY_REQUIRES_RESOURCE_AND_SURFACE_BINDING' if occupancy_ready else 'NEEDS_GEOMETRY',
                           'actors_with_box_dimensions':len(geometry_candidates),
                           'complete_map_with_polygons':has_complete_polygon_map,
                           'formal_permission_and_capacity':'UNAVAILABLE'},
            'L_observation':{'status':'UNAVAILABLE',
                              'dataset_observed_bit':'history_split_not_sensor_awareness',
                              'sensor_visibility':'UNAVAILABLE', 'silence_clock':'UNAVAILABLE'},
            'L_viability':{'status':'CERTIFICATE_OR_COMPLETE_ORACLE_REQUIRED',
                            'unknown_is_not_negative':True},
            'L_margin':{'status':'VERIFIED_REACHABLE_TUBE_REQUIRED'},
            'L_deadline':{'status':'PROTOCOL_AND_SCHEDULER_REQUIRED'},
            'L_causal':{'status':'PAIRED_INTERVENTION_REQUIRED'},
        },
        'certified':False,
    }


__all__=['supervision_inventory']
