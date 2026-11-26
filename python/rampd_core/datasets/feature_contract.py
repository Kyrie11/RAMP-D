"""Phase7A factual feature adapter. No simulator, hidden rule or future route input.
Logged ego future is an explicit offline query, never an encoder feature.
All geometry is bounding-box-center in current ego-local metric frame.
"""
from __future__ import annotations
import math
import numpy as np
from ..scoped_factual_labels import factual

CATEGORIES = ('vehicle','pedestrian','cyclist','other','unknown')
MAP_KINDS = ('lane','road_line','road_edge','stop_sign','crosswalk','speed_bump','driveway','other')
HISTORY_DIM = 10  # xy, sin/cos, velocity xy, length/width, relative time, valid
MAP_DIM = 8 + len(MAP_KINDS)  # endpoints, midpoint, topology degree, kind
HEADS = ('event','joint','occupancy','observation','viability','margin','deadline','causal')

def _onehot(value, choices):
    out = [0.]*len(choices); out[choices.index(value) if value in choices else len(choices)-1] = 1.; return out

def build_features(record, *, horizon=10, history_steps=11, max_agents=128, max_map=256, radius=100.):
    if min(horizon,history_steps,max_agents,max_map) <= 0 or radius <= 0: raise ValueError('feature limits')
    row = factual(record,prefix_steps=horizon)
    scene=record['scene']; manifest=scene['manifest']; k=manifest['current_time_index']; times=manifest['timestamps']
    if not manifest['future_available'] or row['split'] not in ('training','validation'): raise ValueError('future withheld or unsupported split')
    ego=next(a for a in row['history'] if a['id']==row['ego_id']); ex,ey,heading=ego['states'][-1][:3]; c,s=math.cos(heading),math.sin(heading)
    def xy(x,y):
        dx,dy=x-ex,y-ey; return [c*dx+s*dy,-s*dx+c*dy]
    def hist(z,t):
        if z is None: return [0.]*9+[0.]
        x,y,h,vx,vy,l,w=z
        return xy(x,y)+[math.sin(h-heading),math.cos(h-heading),c*vx+s*vy,-s*vx+c*vy,l,w,t-times[k],1.]
    # Rank using public current positions only. No future target existence in selection.
    all_agents=[a for a in row['history'] if a['id']!=row['ego_id']]
    all_agents.sort(key=lambda a:(math.hypot(a['states'][-1][0]-ex,a['states'][-1][1]-ey),a['id']))
    selected=[ego]+all_agents[:max_agents-1]; targets={a['id']:a for a in row['targets']}
    history=[]; categories=[]; out=[]; masks=[]; cv=[]; actual_dt=np.asarray(row['future_times'])-times[k]
    # Fixed 10 Hz query grid: exact future sampling jitter is target metadata, not an online feature.
    dt=np.arange(1,horizon+1,dtype=float)*.1
    if np.max(np.abs(actual_dt-dt))>.02: raise ValueError('future samples outside nominal query tolerance')
    for a in selected:
        h=[hist(z,t) for z,t in zip(a['states'][-history_steps:],row['history_times'][-history_steps:])]
        history.append([[0.]*HISTORY_DIM]*(history_steps-len(h))+h)
        categories.append(_onehot(a['category'],CATEGORIES)); cur=h[-1]
        cv.append([[cur[0]+cur[4]*t,cur[1]+cur[5]*t] for t in dt])
        tar=targets.get(a['id']); valid=tar['valid'] if tar else [False]*horizon
        masks.append(valid); out.append([xy(*p) if v else [0.,0.] for p,v in zip(tar['xy'] if tar else [None]*horizon,valid)])
    if not any(map(any,masks)): raise ValueError('no selected factual targets')
    # Static map only; past logged signal states are not proven ego observations either.
    mc=scene.get('map_context')
    if not mc or mc['scenario_id']!=row['scenario_id'] or mc['coordinate_frame']!=row['coordinate_frame']: raise ValueError('map identity/frame missing')
    segments=[]
    for p in mc['primitives']:
        v=p['vertices']; kind=p['kind']; coords=[xy(q['x'],q['y']) for q in v]
        if not coords: continue
        # Downsample by arc length for learning ONLY. Keep endpoints and corners.
        if p['geometry_type']=='polygon': coords=coords+[coords[0]]
        if len(coords)>2:
            keep=[coords[0]]; travel=0.
            for j in range(1,len(coords)-1):
                u=np.asarray(coords[j])-coords[j-1]; v=np.asarray(coords[j+1])-coords[j]
                travel+=float(np.linalg.norm(u)); den=float(np.linalg.norm(u)*np.linalg.norm(v))
                corner=den>0 and float(u@v)/den<.94
                if travel>=3. or corner: keep.append(coords[j]); travel=0.
            coords=keep+[coords[-1]]
        pairs=list(zip(coords[:-1],coords[1:])) if len(coords)>1 else [(coords[0],coords[0])]
        for j,(a,b) in enumerate(pairs):
            mid=[(a[0]+b[0])/2,(a[1]+b[1])/2]; d=math.hypot(*mid)
            if d<=radius:
                feat=a+b+mid+[len(p['successors']),len(p['predecessors'])]+_onehot(kind,MAP_KINDS)
                segments.append((d,str(p['feature_id']),j,feat))
    segments.sort(key=lambda v:v[:3])
    # A compact list for explicit overlay proposals; not physical resource geometry.
    lane_candidates=list(dict.fromkeys(x[1] for x in segments if x[3][8]))[:8]
    # Round-robin by map kind to avoid one dense lane marking monopolizing the budget.
    from collections import deque
    groups=[deque(x for x in segments if x[3][8+j]) for j in range(len(MAP_KINDS))]
    maps=[]
    while len(maps)<max_map and any(groups):
        for g in groups:
            if g and len(maps)<max_map: maps.append(g.popleft()[3])
    if not maps: raise ValueError('no local static map geometry')
    # Explicit candidate query, separate from scene input. Actual logged path not measured controls.
    candidate=[xy(z[0],z[1])+[float(t)] for z,t in zip(row['candidate_ego_path'][1:],dt)]
    result=dict(schema='rampd.factual_features.v2',scenario_id=row['scenario_id'],source_digest=row['source_digest'],split=row['split'],
        inputs=dict(history=history,category=categories,map=maps,forecast_dt=dt.tolist()),
        candidate=dict(path=candidate,domain='OFFLINE_LOGGED_EGO_PATH_SURROGATE'),
        targets=dict(xy=out,valid=masks,actual_dt=actual_dt.tolist()),baseline_cv=cv,
        actor_ids=[a['id'] for a in selected],ego_id=row['ego_id'],
        stats=dict(future_births_unmodelled=len(row['births_unmodelled']),actors_dropped=len(all_agents)+1-len(selected),map_segments_dropped=len(segments)-len(maps),valid_knots=sum(map(sum,masks))),
        frame=dict(position_reference='bounding_box_center',origin=[ex,ey],yaw=heading),
        context=dict(decision_time_s=times[k],lane_candidates=lane_candidates,query_grid='FIXED_10HZ_APPROXIMATE_SAMPLE_ALIGNMENT',max_sample_time_error_s=float(np.max(np.abs(actual_dt-dt)))),
        heads={h:h=='joint' for h in HEADS},domain='REAL_FACTUAL_LOGGED_EGO_PATH_SURROGATE',formal_sc=False)
    # Check only numeric tensor fields, not arbitrary provenance metadata.
    for value in (*result['inputs'].values(),candidate,out,cv):
        if not np.isfinite(np.asarray(value,dtype=np.float64)).all(): raise ValueError('nonfinite feature')
    return result
