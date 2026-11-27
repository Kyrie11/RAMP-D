"""Geometry-conditioned, future-only proposal factory. No map/permission proof.
Scope: lane centerline proposal, never a lane polygon or actual closure response.
"""
from fractions import Fraction as Q
import math
import numpy as np
from .rule_overlay import RuleOverlay,ScheduledDelivery,replay_scheduled_world
from .split_manifest import canonical_digest

def lane_proposal(record, *, max_distance=4., min_length=15., min_ahead=10., min_alignment=.7):
    s=record['scene']; m=s['manifest']; k=m['current_time_index']; idx=m['metadata']['source_track_indices'].index(m['metadata']['sdc_track_index']); ego=s['tracks'][idx]['states'][k]
    if ego['valid'] is not True: raise ValueError('invalid ego at cutoff')
    p=np.array([ego['x'],ego['y']]); yaw=ego['heading']; forward=np.array([math.cos(yaw),math.sin(yaw)])
    options=[]
    for f in s['map_context']['primitives']:
        if f['kind']!='lane' or len(f['vertices'])<2: continue
        v=np.array([[x['x'],x['y']] for x in f['vertices']],dtype=float); delta=np.diff(v,axis=0); lengths=np.linalg.norm(delta,axis=1); total=float(lengths.sum()); good=lengths>1e-6
        if total<min_length or not good.any(): continue
        u=delta[good]/lengths[good,None]; a=v[:-1][good]; t=np.clip(((p-a)*u).sum(1),0,lengths[good]); proj=a+t[:,None]*u; d=np.linalg.norm(proj-p,axis=1); j=int(d.argmin()); alignment=float(u[j]@forward)
        if d[j]>max_distance or alignment<min_alignment: continue
        # Require at least 10 m of mapped centerline ahead of ego projection.
        arc=float(np.r_[0.,np.cumsum(lengths)][np.flatnonzero(good)[j]]+t[j]); remaining=total-arc
        if remaining<min_ahead: continue
        options.append((float(d[j]),-alignment,str(f['feature_id']),v,arc,total))
    if not options: raise ValueError('no nearby aligned lane with downstream extent')
    dist,neg,lane,v,arc,total=min(options,key=lambda x:x[:3]); return dict(lane_id=lane,centerline=v.tolist(),ego_distance_m=dist,heading_alignment=-neg,ego_arc_m=arc,centerline_length_m=total,scope='CENTERLINE_PROPOSAL_ONLY_NOT_RESOURCE_POLYGON')

# Relative seconds; declared experimental factors, NOT measured traffic statistics.
CLOCK_PROFILES={
 'nominal':dict(generation='0.1',issue='0.2',publication='0.3',planned_on='0.8',planned_off='4',effective_on='0.8',effective_off='4',ego_receipt='1.2',other_receipt='0.5'),
 'early':dict(generation='0.1',issue='0.2',publication='0.3',planned_on='0.8',planned_off='4',effective_on='0.8',effective_off='4',ego_receipt='0.4',other_receipt='0.5'),
 'delayed_effect':dict(generation='0.1',issue='0.2',publication='0.3',planned_on='0.8',planned_off='4',effective_on='1.6',effective_off='5',ego_receipt='1.2',other_receipt='0.5'),
 'late_receipt':dict(generation='0.1',issue='0.2',publication='0.3',planned_on='0.8',planned_off='4',effective_on='0.8',effective_off='4',ego_receipt='4.5',other_receipt='0.5'),
 'no_ego_delivery':dict(generation='0.1',issue='0.2',publication='0.3',planned_on='0.8',planned_off='4',effective_on='0.8',effective_off='4',ego_receipt=None,other_receipt='0.5'),
}

def propose(record, *, seed=7, query_steps=30, clock_profile='nominal'):
    s=record['scene'];m=s['manifest']; k=m['current_time_index']; t=Q(str(m['timestamps'][k])); lane=lane_proposal(record)
    if clock_profile not in CLOCK_PROFILES:raise ValueError('unknown clock profile')
    cp=CLOCK_PROFILES[clock_profile]; ab=lambda key:None if cp[key] is None else str(t+Q(cp[key]))
    event=RuleOverlay(m['scenario_id'],record['record_sha256'],f"{m['scenario_id']}:closure:{seed}:{clock_profile}",lane['lane_id'],'LANE_CLOSURE',ab('generation'),ab('effective_on'),ab('effective_off'),ab('issue'),None,'SIMULATED_ROAD_AUTHORITY',seed,True,ab('planned_on'),ab('planned_off'))
    idx=m['metadata']['source_track_indices'].index(m['metadata']['sdc_track_index']); ego_id=s['tracks'][idx]['track_id']
    actors=[a for a in s['tracks'] if a['track_id']!=ego_id and a['states'][k]['valid'] is True]
    ex,ey=s['tracks'][idx]['states'][k]['x'],s['tracks'][idx]['states'][k]['y']
    actors.sort(key=lambda a:(math.hypot(a['states'][k]['x']-ex,a['states'][k]['y']-ey),str(a['track_id'])))
    pub=ab('publication'); ds=[ScheduledDelivery(str(ego_id),pub,ab('ego_receipt'))];
    if actors: ds.append(ScheduledDelivery(str(actors[0]['track_id']),pub,ab('other_receipt')))
    # Explicitly mark every current actor; None is a declared no-delivery world, not proof of ignorance.
    for a in actors[1:]: ds.append(ScheduledDelivery(str(a['track_id']),pub,None))
    row=replay_scheduled_world(record,event,ds,query_steps=query_steps);row.update(lane_proposal=lane,ego_id=str(ego_id),clock_profile=clock_profile,clock_prior='DECLARED_ILLUSTRATIVE_NOT_EMPIRICAL',scenario_spec_sha256=canonical_digest({'event':event.__dict__,'deliveries':[d.__dict__ for d in ds],'lane':lane}));return row


def extend_unique_route(record, lane, *, max_lanes=12, join_tolerance_m=.10, alignment_min=.90):
    """Map-only route; terminate at branching, missing topology, sharp join or cycle.
    Not route intent, lane membership, or a physical resource certificate.
    """
    primitives=record['scene']['map_context']['primitives']
    lanes={str(f['feature_id']):f for f in primitives if f['kind']=='lane'}
    if len(lanes)!=sum(f['kind']=='lane' for f in primitives): raise ValueError('duplicate lane ids')
    current=str(lane['lane_id']); line=np.asarray(lane['centerline'],float)
    if current not in lanes: raise ValueError('missing initial lane')
    def points(f): return np.asarray([[p['x'],p['y']] for p in f['vertices']],float)
    if not np.array_equal(line,points(lanes[current])):raise ValueError('initial lane geometry mismatch')
    def length(v):return float(np.linalg.norm(np.diff(v,axis=0),axis=1).sum())
    def tangent(v,end):
        diff=np.diff(v,axis=0); norms=np.linalg.norm(diff,axis=1); good=diff[norms>1e-6]
        if not len(good): raise ValueError('degenerate route segment')
        q=good[-1 if end else 0];return q/np.linalg.norm(q)
    total=length(line); segments=[dict(lane_id=current,start_m=0.,end_m=total)]; joins=[]; stop='MAX_LANES'
    for _ in range(max_lanes-1):
        f=lanes[current]; successors=list(map(str,f.get('successors',[])))
        if len(successors)!=1:stop='BRANCH_OR_NO_SUCCESSOR';break
        nxt=successors[0]
        if nxt in {v['lane_id'] for v in segments}:stop='CYCLE';break
        if nxt not in lanes:stop='MISSING_SUCCESSOR';break
        g=lanes[nxt]; q=points(g)
        if len(q)<2 or not np.isfinite(q).all():stop='INVALID_SUCCESSOR';break
        if current not in list(map(str,g.get('predecessors',[]))):stop='MISSING_RECIPROCAL_TOPOLOGY';break
        if f.get('attributes',{}).get('lane_type')!=g.get('attributes',{}).get('lane_type'):stop='LANE_TYPE_CHANGE';break
        gap=float(np.linalg.norm(line[-1]-q[0])); align=float(tangent(line,True)@tangent(q,False))
        if gap>join_tolerance_m or align<alignment_min:stop='GEOMETRIC_JOIN_REJECTED';break
        # Join between mapped endpoints only; no fabricated extension. Nonzero
        # connector length is explicitly retained as a diagnostic approximation.
        joins.append(dict(from_lane=current,to_lane=nxt,gap_m=gap,alignment=align))
        start=total+gap; total=start+length(q);line=np.concatenate((line,q[1:] if gap==0 else q),axis=0)
        segments.append(dict(lane_id=nxt,start_m=start,end_m=total));current=nxt
    return dict(lane,centerline=line.tolist(),centerline_length_m=length(line),route_segments=segments,route_joins=joins,route_stop=stop,scope='DECLARED_UNIQUE_SUCCESSOR_CENTERLINE_NOT_RESOURCE_POLYGON')
