#!/usr/bin/env python3
"""Offline geometry review of actual SUMO raw metric trace, no field ACK or
continuous claim. Polygons must be in the named SUMO net frame and linked by
net SHA. Geometric sampling may miss contacts between ticks."""
import argparse,json,hashlib,math
from pathlib import Path

def vehicle_polygon(row):
    from shapely.geometry import Polygon
    x,y=row['front_bumper_xy'];theta=math.radians(row['angle_navigation_deg']);l=row['length_m'];w=row['width_m'];
    if not all(math.isfinite(v) for v in (x,y,theta,l,w)) or l<=0 or w<=0:raise ValueError('bad geometry')
    fx,fy=math.sin(theta),math.cos(theta);sx,sy=-fy,fx
    return Polygon([(x+a*fx+b*sx,y+a*fy+b*sy) for a,b in ((0,-w/2),(0,w/2),(-l,w/2),(-l,-w/2))])

def review(work,definition):
    from shapely.geometry import Polygon
    source=json.loads((work/'metric_source.json').read_text());raw=(work/'metric_actor_trace.jsonl').read_bytes();network=(work/'network.xml').read_bytes();routes=(work/'routes.xml').read_bytes();h=lambda a:hashlib.sha256(a).hexdigest()
    if h(raw)!=source['actor_trace_sha256'] or h(network)!=source['network_sha256'] or h(routes)!=source['routes_sha256'] or definition['network_sha256']!=h(network):raise ValueError('source/geometry hash mismatch')
    p=Polygon(definition['polygon']);
    if not p.is_valid or p.area<=0:raise ValueError('invalid resource polygon')
    errors=[];prev=set();rows=[];prev_occ=set();last=0
    for line in raw.splitlines():
        t=json.loads(line);ids={r['id'] for r in t['actors']};
        if len(ids)!=len(t['actors']) or ids-prev!=set(t['departed']) or prev-ids!=set(t['arrived']):errors.append('ROSTER_DISAGREEMENT:'+str(t['tick']))
        if t['tick']!=last+1 or t['command_epoch']!=last or t['command']!=t['observed_execution']:errors.append('CLOCK_OR_COMMAND_DISAGREEMENT:'+str(t['tick']))
        from fractions import Fraction as Q
        if Q(t['time'])!=Q(t['tick'],10) or Q(t['issue'])!=Q(last,10):errors.append('CLOCK_TIME_DISAGREEMENT:'+str(t['tick']))
        occ={r['id']:r['direction'] for r in t['actors'] if vehicle_polygon(r).intersects(p)}
        if len(set(occ.values()))>1:errors.append('OPPOSING_SAMPLED_OCCUPANCY:'+str(t['tick']))
        # logical sweep includes observed sampled occupancy if resource mapping is sound.
        logical=set().union(*map(set,t['logical_swept_occupants'].values()))
        if set(occ)-logical:errors.append('METRIC_VS_LOGICAL_DISAGREEMENT:'+str(t['tick']))
        rows.append(dict(tick=t['tick'],occupancy=occ,entries=sorted(set(occ)-prev_occ),exits=sorted(prev_occ-set(occ))));prev=ids;prev_occ=set(occ);last=t['tick']
    if not rows or len(rows)!=source['ticks']:errors.append('INCOMPLETE_TRACE')
    if not any(r['occupancy'] for r in rows):errors.append('NO_SAMPLED_RESOURCE_CONTACT_NONVACUITY')
    return dict(status='DESCRIPTIVE_SAMPLED_METRIC_OCCUPANCY_REVIEW' if not errors else 'REVIEW',errors=errors,rows=rows,physical_shared_lane_proved=False,continuous_sweep_proved=False,physical_ack_proved=False,formal_labels_authorized=False)

def main():
    p=argparse.ArgumentParser();p.add_argument('--work',type=Path,required=True);p.add_argument('--resource-json',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    if a.output.exists():raise SystemExit('REFUSE_OVERWRITE')
    try:r=review(a.work,json.loads(a.resource_json.read_text()))
    except Exception as e:r=dict(status='REVIEW',reason=f'{type(e).__name__}:{e}',formal_labels_authorized=False)
    a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(r,indent=2,allow_nan=False)+'\n');print(r['status']);return 0 if r['status'].startswith('DESCRIPTIVE') else 4
if __name__=='__main__':raise SystemExit(main())
