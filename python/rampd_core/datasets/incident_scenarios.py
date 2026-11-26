"""Geometry-conditioned, future-only proposal factory. No map/permission proof.
Scope: lane centerline proposal, never a lane polygon or actual closure response.
"""
from fractions import Fraction as Q
import math
import numpy as np
from .rule_overlay import RuleOverlay,ScheduledDelivery,replay_scheduled_world
from .split_manifest import canonical_digest

def lane_proposal(record, *, max_distance=4., min_length=15.):
    s=record['scene']; m=s['manifest']; k=m['current_time_index']; idx=m['metadata']['source_track_indices'].index(m['metadata']['sdc_track_index']); ego=s['tracks'][idx]['states'][k]
    if ego['valid'] is not True: raise ValueError('invalid ego at cutoff')
    p=np.array([ego['x'],ego['y']]); yaw=ego['heading']; forward=np.array([math.cos(yaw),math.sin(yaw)])
    options=[]
    for f in s['map_context']['primitives']:
        if f['kind']!='lane' or len(f['vertices'])<2: continue
        v=np.array([[x['x'],x['y']] for x in f['vertices']],dtype=float); delta=np.diff(v,axis=0); lengths=np.linalg.norm(delta,axis=1); total=float(lengths.sum()); good=lengths>1e-6
        if total<min_length or not good.any(): continue
        u=delta[good]/lengths[good,None]; a=v[:-1][good]; t=np.clip(((p-a)*u).sum(1),0,lengths[good]); proj=a+t[:,None]*u; d=np.linalg.norm(proj-p,axis=1); j=int(d.argmin()); alignment=float(u[j]@forward)
        if d[j]>max_distance or alignment<.7: continue
        # Require at least 10 m of mapped centerline ahead of ego projection.
        arc=float(np.r_[0.,np.cumsum(lengths)][np.flatnonzero(good)[j]]+t[j]); remaining=total-arc
        if remaining<10.: continue
        options.append((float(d[j]),-alignment,str(f['feature_id']),v,arc,total))
    if not options: raise ValueError('no nearby aligned lane with downstream extent')
    dist,neg,lane,v,arc,total=min(options,key=lambda x:x[:3]); return dict(lane_id=lane,centerline=v.tolist(),ego_distance_m=dist,heading_alignment=-neg,ego_arc_m=arc,centerline_length_m=total,scope='CENTERLINE_PROPOSAL_ONLY_NOT_RESOURCE_POLYGON')

def propose(record, *, seed=7, query_steps=30):
    s=record['scene'];m=s['manifest']; k=m['current_time_index']; t=Q(str(m['timestamps'][k])); lane=lane_proposal(record)
    # Deliberately fixed illustrative clocks; no empirical 511NY latency claim.
    event=RuleOverlay(m['scenario_id'],record['record_sha256'],f"{m['scenario_id']}:closure:{seed}",lane['lane_id'],'LANE_CLOSURE',str(t+Q(1,10)),str(t+Q(8,10)),str(t+Q(4)),str(t+Q(2,10)),None,'SIMULATED_ROAD_AUTHORITY',seed,True)
    idx=m['metadata']['source_track_indices'].index(m['metadata']['sdc_track_index']); ego_id=s['tracks'][idx]['track_id']
    actors=[a for a in s['tracks'] if a['track_id']!=ego_id and a['states'][k]['valid'] is True]
    ex,ey=s['tracks'][idx]['states'][k]['x'],s['tracks'][idx]['states'][k]['y']
    actors.sort(key=lambda a:(math.hypot(a['states'][k]['x']-ex,a['states'][k]['y']-ey),str(a['track_id'])))
    pub=str(t+Q(3,10)); ds=[ScheduledDelivery(str(ego_id),pub,str(t+Q(12,10)))];
    if actors: ds.append(ScheduledDelivery(str(actors[0]['track_id']),pub,str(t+Q(5,10))))
    if len(actors)>1: ds.append(ScheduledDelivery(str(actors[1]['track_id']),pub,None))
    row=replay_scheduled_world(record,event,ds,query_steps=query_steps);row.update(lane_proposal=lane,ego_id=str(ego_id),clock_prior='DECLARED_ILLUSTRATIVE_NOT_EMPIRICAL',scenario_spec_sha256=canonical_digest({'event':event.__dict__,'deliveries':[d.__dict__ for d in ds],'lane':lane}));return row
