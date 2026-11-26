"""Offline map inventory and measured landmark registration preflight.
No inferred road/lane matching; a low residual alone is not shared-resource proof.
"""
from pathlib import Path
import hashlib, xml.etree.ElementTree as ET
import numpy as np


def inventory(xodr, net):
    xp,npth=Path(xodr),Path(net); xb,nb=xp.read_bytes(),npth.read_bytes();x,n=ET.fromstring(xb),ET.fromstring(nb)
    if x.tag!='OpenDRIVE' or n.tag!='net':raise ValueError('expected OpenDRIVE and SUMO net XML')
    edges=n.findall('edge'); lanes=[l for e in edges for l in e.findall('lane')];road_ids=[r.get('id') for r in x.findall('road')]; lane_ids=[l.get('id') for l in lanes]
    if not road_ids or not lane_ids or None in road_ids or None in lane_ids or len(set(road_ids))!=len(road_ids) or len(set(lane_ids))!=len(lane_ids):raise ValueError('invalid map roster')
    loc=n.find('location');
    return dict(xodr_sha256=hashlib.sha256(xb).hexdigest(),sumo_net_sha256=hashlib.sha256(nb).hexdigest(),roads=len(road_ids),junctions=len(x.findall('junction')),sumo_edges=len(edges),sumo_internal_edges=sum(e.get('function')=='internal' for e in edges),sumo_lanes=len(lanes),sumo_connections=len(n.findall('connection')),location=dict(loc.attrib) if loc is not None else {},status='MAP_INVENTORY_ONLY',shared_resource_verified=False,cosim_verified=False)


def fit_landmarks(points, *, tolerance_m=.5):
    """Fit isometry in XY with explicit handedness choice, assess holdout only.
    At least 3 noncollinear fit and 3 noncollinear independent holdout anchors.
    Points are independently matched physical landmarks, not nearest guesses.
    """
    if not np.isfinite(tolerance_m) or tolerance_m<=0:raise ValueError('positive tolerance')
    if len({p['id'] for p in points})!=len(points):raise ValueError('duplicate landmark identity')
    if any(p['split'] not in ('fit','holdout') or not p.get('id') for p in points):raise ValueError('landmark split/identity')
    def arrays(s):
        ps=[p for p in points if p['split']==s]; a=np.asarray([p['carla_xy'] for p in ps],dtype=float);b=np.asarray([p['sumo_xy'] for p in ps],dtype=float)
        if len(ps)<3 or a.shape!=(len(ps),2) or b.shape!=a.shape or not np.isfinite(a).all() or not np.isfinite(b).all() or np.linalg.matrix_rank(a-a.mean(0))<2 or np.linalg.matrix_rank(b-b.mean(0))<2:raise ValueError('need noncollinear 2D landmarks in both splits')
        if len(np.unique(a,axis=0))!=len(a) or len(np.unique(b,axis=0))!=len(b):raise ValueError('duplicate landmark coordinates')
        return a,b
    a,b=arrays('fit');c,d=arrays('holdout')
    if set(map(tuple,a))&set(map(tuple,c)) or set(map(tuple,b))&set(map(tuple,d)):raise ValueError('fit/holdout landmark leakage')
    u,_,vt=np.linalg.svd((a-a.mean(0)).T@(b-b.mean(0))); candidates=[]
    for handedness in (1,-1):
        q=np.eye(2);q[-1,-1]=handedness*np.linalg.det(u@vt); R=u@q@vt;t=b.mean(0)-a.mean(0)@R;err=np.linalg.norm(a@R+t-b,axis=1)
        candidates.append((float(np.mean(err**2)),R,t,err))
    _,R,t,err=min(candidates,key=lambda x:x[0]);hold=np.linalg.norm(c@R+t-d,axis=1)
    return dict(status='LANDMARK_RESIDUAL_PASS_NOT_RESOURCE_PROOF' if max(err.max(),hold.max())<=tolerance_m else 'REVIEW_MAP_REGISTRATION',matrix=R.tolist(),translation=t.tolist(),convention='sumo_xy = carla_xy @ matrix + translation',determinant=float(np.linalg.det(R)),fit_max_m=float(err.max()),holdout_max_m=float(hold.max()),fit_rmse_m=float(np.sqrt(np.mean(err**2))),holdout_rmse_m=float(np.sqrt(np.mean(hold**2))),tolerance_m=tolerance_m,shared_resource_verified=False,cosim_verified=False)
