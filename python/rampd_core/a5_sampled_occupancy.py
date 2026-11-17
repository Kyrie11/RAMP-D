"""Weak, sampled geometry labels. NEVER a hard resource or safety certificate.

Only explicitly selected valid map polygons and center-referenced actor boxes.
2-D overlap assumes the actor and resource share a traffic surface; caller must
justify that assumption or keep the corresponding label masked (e.g. overpass).
"""
from __future__ import annotations
from dataclasses import dataclass
import math
from .phase6c import SceneForecastSample


@dataclass(frozen=True)
class SampledOccupancy:
    actor_id: str
    resource_id: str
    timestamp_s: float
    occupied: bool | None
    transition: str | None
    status: str
    source: str = 'SAMPLED_2D_GEOMETRY_ONLY'


def sampled_occupancy_labels(sample: SceneForecastSample,
                             actor_resource_pairs: tuple[tuple[str,str],...], *,
                             boundary_buffer_m: float) -> tuple[SampledOccupancy,...]:
    """Explicit actor/polygon pairs have independently justified same-surface relation.

    Polygon IDs are descriptive map geometry, not automatically legal resources.
    `boundary_buffer_m` masks ambiguous near-boundary labels; this is a training
    design threshold, not a proof of geometric or localization uncertainty.
    Transitions are sampled changes, not continuous entry/stay/exit certificates.
    """
    from shapely.geometry import Polygon
    if not math.isfinite(boundary_buffer_m) or boundary_buffer_m < 0:
        raise ValueError('finite nonnegative boundary buffer required')
    pairs=tuple(tuple(p) for p in actor_resource_pairs)
    if len(set(pairs))!=len(pairs) or any(len(p)!=2 for p in pairs):
        raise ValueError('unique actor/polygon pairs required')
    if not sample.future_available: return ()
    ctx=sample.map_context_history
    primitives={} if ctx is None else {p.feature_id:p for p in ctx.primitives}
    history={t.track_id:t for t in sample.history_tracks}
    future={t.track_id:t for t in sample.future_targets}
    rows=[]
    for aid,rid in pairs:
        h=history.get(aid); f=future.get(aid); r=primitives.get(rid)
        region=None
        if r is not None and r.geometry_type=='polygon':
            p=Polygon([(v.x,v.y) for v in r.vertices])
            if p.is_valid and p.area>0: region=p
        def classify(state,valid):
            if h is None or not any(h.valid_observation_mask): return None,'NO_OBSERVED_ACTOR_HISTORY'
            if not valid or state is None: return None,'MISSING_TRACK_STATE'
            if sample.position_reference!='bounding_box_center': return None,'UNSUPPORTED_REFERENCE_POINT'
            if region is None: return None,'MISSING_OR_INVALID_POLYGON'
            if any(v is None or not math.isfinite(v) for v in (state.x,state.y,state.heading,state.length,state.width)) or state.length<=0 or state.width<=0:
                return None,'MISSING_FOOTPRINT_DIMENSIONS'
            c,s=math.cos(state.heading),math.sin(state.heading)
            hl,hw=.5*state.length,.5*state.width
            polygon=Polygon([(state.x+c*x-s*y,state.y+s*x+c*y) for x,y in
                            ((-hl,-hw),(hl,-hw),(hl,hw),(-hl,hw))])
            if not polygon.is_valid or polygon.area<=0: return None,'INVALID_FOOTPRINT'
            if polygon.distance(region)>boundary_buffer_m: return False,'SAMPLED_SEPARATED'
            # Erode both shapes to mask grazing contact and thin overlaps.
            a=polygon.buffer(-boundary_buffer_m); b=region.buffer(-boundary_buffer_m)
            if not a.is_empty and not b.is_empty and a.intersection(b).area>0:
                return True,'SAMPLED_INTERIOR_OVERLAP'
            return None,'BOUNDARY_AMBIGUOUS'
        prev,_=classify(h.states[-1] if h else None,bool(h and h.valid_observation_mask[-1]))
        for i,t in enumerate(sample.future_timestamps_s):
            current,status=classify(f.states[i] if f else None,bool(f and f.valid_future_mask[i]))
            change=None if prev is None or current is None else {
                (False,False):'sampled_free',(False,True):'sampled_entry',
                (True,True):'sampled_stay',(True,False):'sampled_exit'}[(prev,current)]
            rows.append(SampledOccupancy(aid,rid,t,current,change,status))
            prev=current
    return tuple(rows)
