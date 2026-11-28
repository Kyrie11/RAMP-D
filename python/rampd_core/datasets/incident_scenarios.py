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


def extend_unique_route(record, lane, *, max_lanes=12, join_tolerance_m=.10, alignment_min=.90, prepend=False):
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
    back_stop='NOT_REQUESTED'
    if prepend:
        back_stop='MAX_LANES'
        while len(segments)<max_lanes:
            first=segments[0]['lane_id']; f=lanes[first]; preds=list(map(str,f.get('predecessors',[])))
            if len(preds)!=1: back_stop='BRANCH_OR_NO_PREDECESSOR';break
            prev=preds[0]
            if prev in {v['lane_id'] for v in segments}:back_stop='CYCLE';break
            if prev not in lanes:back_stop='MISSING_PREDECESSOR';break
            g=lanes[prev]; q=points(g)
            if len(q)<2 or not np.isfinite(q).all():back_stop='INVALID_PREDECESSOR';break
            # Do not assume intent at an upstream fork either.
            if list(map(str,g.get('successors',[])))!=[first]:back_stop='BRANCH_OR_NONRECIPROCAL';break
            if f.get('attributes',{}).get('lane_type')!=g.get('attributes',{}).get('lane_type'):back_stop='LANE_TYPE_CHANGE';break
            gap=float(np.linalg.norm(q[-1]-line[0]));align=float(tangent(q,True)@tangent(line,False))
            if gap>join_tolerance_m or align<alignment_min:back_stop='GEOMETRIC_JOIN_REJECTED';break
            ln=length(q);shift=ln+gap
            segments=[dict(lane_id=prev,start_m=0.,end_m=ln)]+[dict(x,start_m=x['start_m']+shift,end_m=x['end_m']+shift) for x in segments]
            joins.insert(0,dict(from_lane=prev,to_lane=first,gap_m=gap,alignment=align));line=np.concatenate((q,line[1:] if gap==0 else line),axis=0)
    # Recompute original ego arc after prepending; no future route inference.
    ego_arc=lane.get('ego_arc_m')
    if ego_arc is not None:ego_arc+=next(x['start_m'] for x in segments if x['lane_id']==str(lane['lane_id']))
    return dict(lane,centerline=line.tolist(),centerline_length_m=length(line),ego_arc_m=ego_arc,route_segments=segments,route_joins=joins,route_stop=stop,upstream_stop=back_stop,scope='DECLARED_UNIQUE_SUCCESSOR_CENTERLINE_NOT_RESOURCE_POLYGON')


def resource_applicability(spec, *, straight_turn_deg=15.):
    """Map-centerline-only candidate check. Never promotes a rule to legal scope.
    Distinguishes scenario types that require additional geometry/controller facts.
    """
    c=spec['closure']; start,end=float(c['start']),float(c['end']);line=np.asarray(spec['lane']['centerline'],float)
    if line.ndim!=2 or line.shape[1]!=2 or len(line)<2 or not np.isfinite(line).all():raise ValueError('route geometry')
    lens=np.linalg.norm(np.diff(line,axis=0),axis=1);arc=np.r_[0.,np.cumsum(lens)]
    if not 0<=start<end<=arc[-1]+1e-8:raise ValueError('resource outside route')
    directions=np.diff(line,axis=0)[(lens>1e-6)&(arc[:-1]<end+5)&(arc[1:]>start-5)]
    if not len(directions):raise ValueError('resource tangent missing')
    u=directions/np.linalg.norm(directions,axis=1)[:,None]
    # Cumulative change, not merely the largest discretization turn.
    angle=float(np.degrees(np.arccos(np.clip((u[1:]*u[:-1]).sum(-1),-1,1))).sum()) if len(u)>1 else 0.
    ids=[str(x['lane_id']) for x in spec['lane'].get('route_segments',[]) if x['end_m']>start and x['start_m']<end]
    if not ids and 'lane_id' in spec['lane']:ids=[str(spec['lane']['lane_id'])]
    segments=spec['lane'].get('route_segments',[]); joins=spec['lane'].get('route_joins',[])
    gap_in_scope=any(j['gap_m']>1e-8 and start<segments[k+1]['start_m'] and end>segments[k]['end_m'] for k,j in enumerate(joins) if k+1<len(segments))
    return dict(scope='CENTERLINE_APPLICABILITY_NOT_LEGAL_OR_PHYSICAL_PROOF',resource_lane_ids=ids,turn_deg_in_buffer=angle,resource_crosses_approximate_join=gap_in_scope,
        centerline_straight_closure_candidate=bool(angle<=straight_turn_deg and not gap_in_scope),
        type_requirements={'LANE_CLOSURE':'NEEDS_LANE_BOUNDARY_AND_LEGAL_EXIT_OR_REROUTE','TEMPORARY_SPEED_LIMIT':'NEEDS_LANE_SCOPE_SPEED_VALUE_AND_COMPLIANCE_MODEL','ALTERNATING_DIRECTION':'NEEDS_SHARED_2D_RESOURCE_OPPOSING_ROUTES_INTERLOCK_CLEARANCE','STOP_SLOW':'NEEDS_VISIBLE_CONTROL_STATION_AND_AUTHORIZED_DIRECTION'},
        physical_resource_verified=False,formal_sc=False)


def route_integrity(lane):
    """Check declared route ledger against its actual polyline, not raw topology.
    Nonzero joins remain approximate. A self-crossing route is not eligible for
    unique longitudinal projection. No guarantee of downstream route intent.
    """
    from shapely.geometry import LineString
    line=np.asarray(lane['centerline'],float)
    if line.ndim!=2 or line.shape[1]!=2 or len(line)<2 or not np.isfinite(line).all():raise ValueError('invalid polyline')
    lengths=np.linalg.norm(np.diff(line,axis=0),axis=1); L=float(lengths.sum());seg=lane.get('route_segments',[dict(lane_id=lane['lane_id'],start_m=0.,end_m=L)]);joins=lane.get('route_joins',[])
    errors=[]
    if not math.isclose(L,float(lane['centerline_length_m']),abs_tol=1e-6,rel_tol=1e-9):errors.append('LENGTH')
    if not LineString(line).is_simple:errors.append('SELF_INTERSECTION')
    if len({str(s['lane_id']) for s in seg})!=len(seg) or len(joins)!=len(seg)-1:errors.append('ROSTER')
    if abs(seg[0]['start_m'])>1e-6 or abs(seg[-1]['end_m']-L)>1e-6 or any(s['end_m']<=s['start_m'] for s in seg):errors.append('ARCLENGTH')
    arc=np.r_[0.,np.cumsum(lengths)]
    for i,j in enumerate(joins):
        if i+1>=len(seg):break
        a,b=seg[i:i+2];gap=b['start_m']-a['end_m'];u=np.argmin(abs(arc-a['end_m']));v=np.argmin(abs(arc-b['start_m']))
        if str(j['from_lane'])!=str(a['lane_id']) or str(j['to_lane'])!=str(b['lane_id']) or gap< -1e-8 or abs(gap-j['gap_m'])>1e-6 or max(abs(arc[u]-a['end_m']),abs(arc[v]-b['start_m']))>1e-6 or abs(np.linalg.norm(line[u]-line[v])-j['gap_m'])>1e-6:errors.append('JOIN_LEDGER')
        before=np.flatnonzero((lengths>1e-6)&(np.arange(len(lengths))<u));after=np.flatnonzero((lengths>1e-6)&(np.arange(len(lengths))>=v))
        if not len(before) or not len(after):errors.append('JOIN_TANGENT');continue
        ii,jj=before[-1],after[0];alignment=float((line[ii+1]-line[ii])@(line[jj+1]-line[jj])/(lengths[ii]*lengths[jj]))
        if abs(alignment-j['alignment'])>1e-6 or alignment<.9-1e-8 or gap>.1+1e-8:errors.append('JOIN_TANGENT')
    return dict(ok=not errors,errors=sorted(set(errors)),length_m=L,joins=len(joins),approximate_joins=sum(j['gap_m']>1e-8 for j in joins),scope='POLYLINE_LEDGER_NOT_RAW_TOPOLOGY_OR_PHYSICAL_ROUTE')


def verify_route_source(record, lane):
    """Independently bind the route ledger to the supplied normalized raw map.
    Requires original record access; does not verify source bytes by itself.
    Every edge must be reciprocal and every segment must match raw vertices.
    No future trajectory or inferred route choice is used.
    """
    geometry=route_integrity(lane);errors=list(geometry['errors'])
    raw=[f for f in record['scene']['map_context']['primitives'] if f['kind']=='lane']
    table={str(f['feature_id']):f for f in raw}
    if len(table)!=len(raw):raise ValueError('duplicate source lane')
    segments=lane.get('route_segments',[dict(lane_id=lane['lane_id'],start_m=0.,end_m=geometry['length_m'])]);ids=[str(s['lane_id']) for s in segments];parts=[];length=0.
    if str(lane['lane_id']) not in ids:errors.append('ROOT_LANE')
    for j,(lid,seg) in enumerate(zip(ids,segments)):
        if lid not in table:errors.append('MISSING_SOURCE_LANE');break
        f=table[lid];q=np.asarray([[p['x'],p['y']] for p in f['vertices']],float)
        if q.ndim!=2 or len(q)<2 or not np.isfinite(q).all():errors.append('SOURCE_VERTICES');break
        gap=0.
        if j:
            prior=table[ids[j-1]]
            if lid not in list(map(str,prior.get('successors',[]))) or ids[j-1] not in list(map(str,f.get('predecessors',[]))):errors.append('SOURCE_TOPOLOGY')
            if prior.get('attributes',{}).get('lane_type')!=f.get('attributes',{}).get('lane_type'):errors.append('SOURCE_LANE_TYPE')
            gap=float(np.linalg.norm(parts[-1][-1]-q[0]))
        start=length+gap;length=start+float(np.linalg.norm(np.diff(q,axis=0),axis=1).sum())
        if max(abs(start-seg['start_m']),abs(length-seg['end_m']))>1e-6:errors.append('SOURCE_ARCLENGTH')
        parts.append(q if not j or gap else q[1:])
    if not parts or len(parts)!=len(ids) or not np.array_equal(np.concatenate(parts,axis=0),np.asarray(lane['centerline'],float)):errors.append('SOURCE_POLYLINE')
    return dict(ok=not errors,errors=sorted(set(errors)),lane_ids=ids,scope='NORMALIZED_SOURCE_MAP_TOPOLOGY_NOT_ROUTE_INTENT_OR_PHYSICAL_PROOF')
