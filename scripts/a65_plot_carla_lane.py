#!/usr/bin/env python3
"""Plot an approximate start-lane corridor and sampled car footprints.

Uses recorded CARLA poses and the *start-lane* straight-line approximation.
It is NOT a map-polygon source, continuous sweep proof, or video sensor trace.
"""
import argparse, json, math
from pathlib import Path

def car_corners(row,bb):
    yaw=math.radians(row['yaw_deg_carla']);c=math.cos(yaw);s=math.sin(yaw)
    center=bb['location_local'];extent=bb['extent']
    pts=[]
    for dx,dy in ((extent['x'],extent['y']),(extent['x'],-extent['y']),
                  (-extent['x'],-extent['y']),(-extent['x'],extent['y']),
                  (extent['x'],extent['y'])):
        px=dx+center['x'];py=dy+center['y']
        pts.append((row['x_m_carla']+c*px-s*py,
                    row['y_m_carla']+s*px+c*py))
    return pts

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--input',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    a=parser.parse_args()
    if a.input.resolve()==a.output.resolve() or a.output.exists():
        raise FileExistsError('REFUSE_OVERWRITE_EVIDENCE')
    import matplotlib;matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    doc=json.loads(a.input.read_text())
    if len(doc.get('trials',[]))!=1 or len(doc['trials'][0].get('samples',[]))<2:
        raise ValueError('ONE_NONEMPTY_CONTROL_TRACE_REQUIRED')
    d=doc['trials'][0];ss=d['samples'];bb=doc['physics']['bounding_box']
    wp=doc['site_audit']['chosen_waypoint']
    if not wp:raise ValueError('NEED_CHOSEN_START_WAYPOINT')
    angle=math.radians(wp['yaw_deg']);ux,uy=math.cos(angle),math.sin(angle)
    nx,ny=-uy,ux;cx,cy=wp['x_m'],wp['y_m']
    lane_halfwidth=next((s.get('lane_audit',{}).get('available_halfwidth_m') for s in ss
                         if s.get('lane_audit',{}).get('available_halfwidth_m') is not None),None)
    if lane_halfwidth is None:raise ValueError('NO_NUMERIC_LANE_WIDTH')
    along=[(r['x_m_carla']-cx)*ux+(r['y_m_carla']-cy)*uy for r in ss]
    amin=min(along)-7;amax=max(along)+7
    fig,ax=plt.subplots(figsize=(11,5),constrained_layout=True)
    for side in (-1,1):
        edge=[(cx+d*ux+side*lane_halfwidth*nx,
               cy+d*uy+side*lane_halfwidth*ny) for d in (amin,amax)]
        ax.plot([v[0] for v in edge],[v[1] for v in edge],linestyle='--',
                label=('Approx start-lane edges' if side==-1 else None))
    ax.plot([r['x_m_carla'] for r in ss],[r['y_m_carla'] for r in ss],
            marker='.',markersize=2,label='Sampled actor reference path')
    indices=sorted(set([0,len(ss)-1,*range(0,len(ss),max(1,len(ss)//8))]))
    for i in indices:
        pts=car_corners(ss[i],bb)
        ax.plot([p[0] for p in pts],[p[1] for p in pts],linewidth=1)
    trigger=d.get('trigger_frame')
    chosen=next((s for s in ss if s.get('frame')==trigger),None)
    if chosen:ax.scatter([chosen['x_m_carla']],[chosen['y_m_carla']],marker='x',s=70,label='Trigger')
    ax.set_aspect('equal',adjustable='box');ax.set_xlabel('CARLA world x (m)');ax.set_ylabel('CARLA world y (m)')
    ax.legend();ax.set_title('Approximate straight-lane diagnostic — NOT swept-polygon proof')
    a.output.parent.mkdir(parents=True,exist_ok=True)
    fig.savefig(a.output,dpi=150);plt.close(fig)
    print(a.output)
if __name__=='__main__':main()
