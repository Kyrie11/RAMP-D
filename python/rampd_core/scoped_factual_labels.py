"""Scoped label contract. No generic flag can promote a sample to proof truth.
This module produces scoped factual evaluation rows; future is target/candidate,
never history. Other head authorizations remain off until their adapters replay.
"""
from __future__ import annotations
import hashlib,json,math
HEADS=('event','joint','occupancy','observation','viability','margin','deadline','causal')
def sha(o):return hashlib.sha256(json.dumps(o,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
def state(s):
    if s['valid'] is not True:return None
    keys=('x','y','heading','vx','vy','length','width')
    z=[s[k] for k in keys]
    if any(type(v) not in (int,float) or not math.isfinite(v) for v in z) or min(z[-2:])<=0:raise ValueError('invalid valid state')
    return z

def factual(record,*,prefix_steps=10):
    s=record['scene'];m=s['manifest'];t=m['timestamps'];k=m['current_time_index'];tracks=s['tracks'];sid=m['scenario_id'];split=m['split'];h=m['source_digest']
    if m['dataset']!='womd_scenario' or split not in ('train','training','validation','test','testing') or not sid or len(h)!=64 or h!=record['record_sha256'] or m['position_reference']!='bounding_box_center':raise ValueError('source binding')
    if type(k) is not int or type(prefix_steps) is not int or not 0<=k<len(t)-prefix_steps or prefix_steps<=0 or any(not math.isfinite(v) for v in t) or any(b<=a for a,b in zip(t,t[1:])):raise ValueError('clock')
    if len(tracks)!=m['metadata']['source_track_count'] or len({a['track_id'] for a in tracks})!=len(tracks):raise ValueError('roster')
    i=m['metadata']['sdc_track_index'];indices=m['metadata']['source_track_indices']
    if len(indices)!=len(tracks) or len(set(indices))!=len(indices) or i not in indices:raise ValueError('invalid source track indices')
    ego=tracks[indices.index(i)]
    for a in tracks:
        if len(a['states'])!=len(t) or any(b['timestamp']!=c for b,c in zip(a['states'],t)):raise ValueError('unaligned track')
        if any(b.get('observed') is not (j<=k) for j,b in enumerate(a['states'])):raise ValueError('history/future boundary')
    prefix=[state(v) for v in ego['states'][k:k+prefix_steps+1]]
    if any(v is None for v in prefix):raise ValueError('invalid ego prefix')
    history=[];targets=[];births=[]
    for a in tracks:
        z=[state(v) for v in a['states'][:k+1]];f=[state(v) for v in a['states'][k+1:k+prefix_steps+1]]
        if z[-1] is None:
            if any(v is not None for v in f):births.append(a['track_id'])
            continue
        history.append(dict(id=a['track_id'],category=a['category'],states=z))
        if a['track_id']!=ego['track_id']:targets.append(dict(id=a['track_id'],xy=[None if v is None else v[:2] for v in f],valid=[v is not None for v in f]))
    n=sum(sum(a['valid']) for a in targets)
    if not n:raise ValueError('no factual target')
    heads={a:dict(mask=False,reason='no scoped adapter evidence') for a in HEADS}
    heads['joint']=dict(mask=True,domain='REAL_FACTUAL_LOGGED_EGO_PATH_SURROGATE',target='xy',valid_actor_knots=n,training_allowed=False,split_eligible=split in ('train','training'),not_counterfactual=True)
    return dict(schema='rampd.a75.scoped_factual.v1',source_digest=h,scenario_id=sid,split=split,coordinate_frame=m['coordinate_frame'],position_reference=m['position_reference'],history_times=t[:k+1],future_times=t[k+1:k+prefix_steps+1],history=history,ego_id=ego['track_id'],candidate_ego_path=prefix,conditioning='OFFLINE_LOGGED_PREFIX_NOT_MEASURED_CONTROL',targets=targets,births_unmodelled=births,heads=heads,formal_sc=False)

def batch(records,*,split_manifest=None):
    out=[];seen=set()
    for r in records:
        row=factual(r);key=row['scenario_id']
        if key in seen:raise ValueError('duplicate/cross-split scenario identity')
        seen.add(key)
        if split_manifest is not None:
            expected=split_manifest.get(key)
            if expected!={'source_digest':row['source_digest'],'split':row['split']}:raise ValueError('independent split manifest mismatch')
            row['heads']['joint']['training_allowed']=row['heads']['joint']['split_eligible']
        out.append(row)
    return out
