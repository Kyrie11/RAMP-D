"""Evidence adapter for audited projected diagnostic pairs. Not full-scene truth.
No promotion of the source's training authorization; no continuous/SC label.
"""
from fractions import Fraction as Q
from .incident_response import audit_pair,Closure
from .rule_overlay import clock_bin_target
from .split_manifest import canonical_digest

HEADS=('event','joint','occupancy','observation','viability','margin','deadline','causal')

def export_pair(pair):
    checked=audit_pair(pair)
    if not checked['ok']:raise ValueError('pair trace audit failed: '+str(checked['errors']))
    spec=pair['spec'];c=Closure(**spec['closure']);out=[];edges=[str(Q(j,2)) for j in range(13)]
    for name,run in pair['runs'].items():
        frames=run['frames'];observed_end=Q(frames[-1]['t']); active=run['event'];receipts=spec['receipts']
        # These are declared schedule labels (not observed physical clocks).
        onset=clock_bin_target(edges,kind='EXACT',value=c.effective_on) if active else clock_bin_target(edges,kind='UNKNOWN')
        expiry=clock_bin_target(edges,kind='EXACT',value=c.effective_off) if active else clock_bin_target(edges,kind='UNKNOWN')
        receipt={}
        for i,t in receipts.items():
            if not active:receipt[i]=clock_bin_target(edges,kind='UNKNOWN')
            elif t is not None and Q(t)<=observed_end:receipt[i]=clock_bin_target(edges,kind='EXACT',value=t)
            else:receipt[i]=clock_bin_target(edges,kind='RIGHT_CENSORED',value=str(observed_end))
        out.append(dict(schema='rampd.projected_evidence.v1',family_id=spec['family_id'],split=spec['split'],source_digest=spec['source_digest'],spec_sha256=pair['spec_sha256'],run=name,run_sha256=canonical_digest(run),domain='DECLARED_PROJECTED_MODEL_EVALUATION_ONLY',clock_edges_s=edges,observed_end_s=str(observed_end),complete=run['stop']=='HORIZON' and 'requested_steps' in run and len(frames)==run['requested_steps']+1,declared_event=dict(exists=active,onset=onset,expiry=expiry),sampled_occupancy=[dict(t=f['t'],ids=f['occupied']) for f in frames],message_clock_evidence=receipt,declared_delivery_status={i:('NO_EVENT' if not active else 'DECLARED_NO_DELIVERY' if t is None else 'DECLARED_DELIVERY') for i,t in receipts.items()},local_detection_evidence={i:next((f['t'] for f in frames if f['public'][i].get('local_blocked') is True),None) for i in receipts},physical_execution=None,continuous_occupancy=None,heads={h:False for h in HEADS},training_allowed=False,formal_sc=False,excluded_current=spec['excluded_current']))
    return out


def sampled_projected_2d(pair, widths, *, corridor_width_m=3.5, boundary_buffer_m=.05):
    """Approximate ribbon geometry and projected oriented boxes at samples only.
    Widths must be source-bound by caller. No roadway polygon or physical ACK.
    Not authorized for full-world occupancy, collisions, or continuous proof.
    """
    import math
    from shapely.geometry import LineString, Polygon
    from shapely.ops import substring
    if not math.isfinite(corridor_width_m) or corridor_width_m<=0 or not math.isfinite(boundary_buffer_m) or boundary_buffer_m<0:raise ValueError('geometry parameters')
    spec=pair['spec']; c=Closure(**spec['closure']);ids={x['id'] for x in spec['vehicles']}
    if set(widths)!=ids or any(not math.isfinite(x) or x<=0 for x in widths.values()):raise ValueError('missing footprint widths')
    line=LineString(spec['lane']['centerline'])
    if not line.is_simple or line.length<c.end-1e-8:raise ValueError('route geometry ambiguous')
    r=substring(line,c.start,c.end).buffer(corridor_width_m/2,cap_style=2,join_style=2)
    if not r.is_valid or r.is_empty or r.geom_type!='Polygon':raise ValueError('invalid projected resource polygon')
    rows=[];counts=dict(interior=0,separated=0,ambiguous=0,disagreement=0)
    for name,run in pair['runs'].items():
        prev={i:None for i in ids}
        for f in run['frames']:
            for i,(s,v,l) in f['state'].items():
                label=None;status='ROUTE_OUTSIDE_OR_BOUNDARY'
                if 0<=s-l/2 and s+l/2<=line.length:
                    p=line.interpolate(s); a=line.interpolate(max(0.,s-.05));b=line.interpolate(min(line.length,s+.05));d=math.hypot(b.x-a.x,b.y-a.y)
                    if d>1e-8:
                        cx,sy=(b.x-a.x)/d,(b.y-a.y)/d;w=widths[i];box=Polygon([(p.x+cx*x-sy*y,p.y+sy*x+cx*y) for x,y in ((-l/2,-w/2),(l/2,-w/2),(l/2,w/2),(-l/2,w/2))])
                        if box.distance(r)>boundary_buffer_m:label=False;status='SAMPLED_SEPARATED';counts['separated']+=1
                        elif box.buffer(-boundary_buffer_m).intersection(r.buffer(-boundary_buffer_m)).area>0:label=True;status='SAMPLED_INTERIOR';counts['interior']+=1
                if label is None:counts['ambiguous']+=1
                elif label!=(i in f['occupied']):counts['disagreement']+=1
                change=None if prev[i] is None or label is None else ('entry' if label and not prev[i] else 'exit' if not label and prev[i] else 'stay' if label else 'free')
                rows.append(dict(run=name,t=f['t'],actor=i,occupied=label,status=status,sampled_transition=change));prev[i]=label
    return dict(scope='DECLARED_RIBBON_PROJECTED_BOX_SAMPLED_ONLY',corridor_width_m=corridor_width_m,boundary_buffer_m=boundary_buffer_m,counts=counts,resource_polygon=list(map(list,r.exterior.coords)),rows=rows,training_allowed=False,formal_sc=False)


def bind_projected_widths_from_cache(pair,row):
    """Recover actual logged dimensions, not road geometry. Check exact source
    identifiers and reconstructed projected current poses; no future use."""
    import math
    import numpy as np
    from .incident_response import project
    spec=pair['spec']
    if row['scenario_id']!=spec['family_id'] or row['source_digest']!=spec['source_digest'] or row['split']!=spec['split'] or str(row['ego_id'])!=spec['ego_id'] or abs(float(Q(str(row['context']['decision_time_s']))-Q(spec['cutoff'])))>1e-7:raise ValueError('cache source/clock mismatch')
    f=row['frame'];theta=f['yaw'];c,s=math.cos(theta),math.sin(theta);x,y=f['origin'];byid={str(a):h[-1] for a,h in zip(row['actor_ids'],row['inputs']['history'])};out={}
    for v in spec['vehicles']:
        h=byid.get(v['id'])
        if h is None or h[9]!=1 or abs(h[6]-v['length'])>1e-5:raise ValueError('projected actor missing or length mismatch')
        px,py=h[:2]; pos=[x+c*px-s*py,y+s*px+c*py];yaw=theta+math.atan2(h[2],h[3]);arc,dist,align,u=project(spec['lane']['centerline'],pos,yaw)
        speed=float(u@np.array([c*h[4]-s*h[5],s*h[4]+c*h[5]]))
        if abs(arc-v['s'])>1e-4 or abs(max(speed,0.)-v['v'])>1e-4 or dist>1.25+1e-6 or align<.9-1e-6:raise ValueError('projected initial state mismatch')
        out[v['id']]=h[7]
    return out
