#!/usr/bin/env python3
"""Headless SUMO traffic-actuated bidirectional logical corridor experiment.
Separate directed SUMO lanes share one logical conflict resource. Not yet a
physically single-lane CARLA geometry or a continuous-world certificate.
"""
import argparse,json,math,shutil,subprocess,sys,traceback
from pathlib import Path
from fractions import Fraction as Q
from dataclasses import dataclass
import xml.etree.ElementTree as ET
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'python'))

ROUTES={'A':('inA','midA','outA'),'B':('inB','midB','outB')}


def network(work,netconvert):
    nodes={'a0':(-200,0),'A':(0,0),'B':(60,0),'b0':(260,0)}
    ns=ET.Element('nodes')
    for id,(x,y) in nodes.items():ET.SubElement(ns,'node',id=id,x=str(x),y=str(y),type='traffic_light' if id in ('A','B') else 'priority')
    es=ET.Element('edges')
    for id,src,dst in [('inA','a0','A'),('midA','A','B'),('outA','B','b0'),('inB','b0','B'),('midB','B','A'),('outB','A','a0')]:
        ET.SubElement(es,'edge',id=id,**{'from':src,'to':dst,'numLanes':'1','speed':'8','spreadType':'right'})
    cs=ET.Element('connections')
    for r in ROUTES.values():
        for l,m in zip(r,r[1:]):ET.SubElement(cs,'connection',**{'from':l,'to':m,'fromLane':'0','toLane':'0'})
    for root,name in ((ns,'nodes'),(es,'edges'),(cs,'connections')):ET.ElementTree(root).write(work/f'{name}.xml')
    cmd=[netconvert,'--node-files',str(work/'nodes.xml'),'--edge-files',str(work/'edges.xml'),'--connection-files',str(work/'connections.xml'),'--no-internal-links','true','--no-turnarounds','true','-o',str(work/'network.xml')]
    result=subprocess.run(cmd,capture_output=True,text=True)
    (work/'netconvert.log').write_text(result.stdout+"\n"+result.stderr)
    result.check_returncode()
    r=ET.Element('routes');ET.SubElement(r,'vType',id='car',length='4.5',minGap='2',maxSpeed='8',accel='2',decel='4',emergencyDecel='8',sigma='0',carFollowModel='IDM',tau='1.5',speedFactor='1',speedDev='0')
    for d,edges in ROUTES.items():ET.SubElement(r,'route',id=d,edges=' '.join(edges))
    ET.SubElement(r,'flow',id='a',type='car',route='A',begin='0',end='120',period='3',departSpeed='0')
    ET.SubElement(r,'flow',id='b',type='car',route='B',begin='1',end='120',period='4',departSpeed='0')
    ET.ElementTree(r).write(work/'routes.xml')

@dataclass(frozen=True)
class Vehicle:
    route:str
    front:float
    length:float
    speed:float


def swept_occupants(before,after,bounds,departed,arrived):
    """Monotone route-coordinate model, full roster; unknown transitions fail.
    Closed interval includes rear clearance. No physical-junction proof implied.
    """
    if set(bounds)!=set(ROUTES) or any(not (math.isfinite(lo) and math.isfinite(hi) and 0<lo<hi) for lo,hi in bounds.values()):raise ValueError('invalid logical corridor bounds')
    if any(v.route not in bounds or not all(math.isfinite(z) for z in (v.front,v.speed,v.length)) or v.front<0 or v.speed<0 or v.length<=0 for v in (*before.values(),*after.values())):raise ValueError('invalid vehicle samples')
    if (set(after)-set(before))!=set(departed) or (set(before)-set(after))!=set(arrived):raise ValueError('unexplained roster change or same-step departure/arrival')
    occupied={'A':set(),'B':set()}; entries={'A':set(),'B':set()}
    for key in before.keys()|after.keys():
        old=before.get(key);new=after.get(key);v=new or old;start,end=bounds[v.route]
        if old and new and (old.route!=new.route or abs(old.length-new.length)>1e-6 or new.front<old.front):raise ValueError('nonmonotone or changed route/body')
        lo=old.front if old else 0.;hi=new.front if new else float('inf')
        if hi>=start and lo-v.length<=end:occupied[v.route].add(key)
        if lo<start<=hi:entries[v.route].add(key)
    return occupied,entries


def run(a):
    from rampd_core.a54_signal import SignalPlan,SignalController
    from rampd_core.a53_rule_models import FlowSnapshot
    from rampd_core.a53b_interlock import ClearanceObservation
    import traci
    work=a.work.resolve();work.mkdir(parents=True,exist_ok=True)
    netconvert=shutil.which(a.netconvert);sumo=shutil.which(a.sumo)
    if not netconvert or not sumo:raise RuntimeError('sumo and netconvert executables required; check eclipse-sumo installation and PATH')
    network(work,netconvert)
    traci.start([sumo,'-n',str(work/'network.xml'),'-r',str(work/'routes.xml'),'--step-length','0.1','--seed',str(a.seed),'--time-to-teleport','-1','--collision.action','warn','--collision.check-junctions','true','--no-step-log','true','--log',str(work/'sumo.log')])
    try:
        lengths={e:traci.lane.getLength(e+'_0') for r in ROUTES.values() for e in r};bounds={d:(lengths[r[0]],lengths[r[0]]+lengths[r[1]]) for d,r in ROUTES.items()}
        links={};
        for d in ROUTES:
            groups=traci.trafficlight.getControlledLinks(d)
            entry=[];exit=[]
            for i,group in enumerate(groups):
                for inc,out,via in group:
                    if (inc,out)==('in'+d+'_0','mid'+d+'_0'):entry.append(i)
                    elif out.startswith('out') and inc.startswith('mid'):exit.append(i)
            if len(set(entry))!=1 or not exit or set(entry)&set(exit):raise ValueError(f'bad entry/exit signal mapping: {d}, {groups}')
            links[d]=(len(groups),entry,exit)
        def apply(c):
            for d,display in zip('AB',c.displays):
                n,entry,exit=links[d];s=['r']*n
                for i in exit:s[i]='G'
                for i in entry:s[i]={'GREEN':'G','YELLOW':'y','RED':'r'}[display]
                target=''.join(s);traci.trafficlight.setRedYellowGreenState(d,target)
                if traci.trafficlight.getRedYellowGreenState(d)!=target:raise ValueError('signal acknowledgement mismatch')
        def snapshot():
            rows={}
            for vid in traci.vehicle.getIDList():
                d=traci.vehicle.getRouteID(vid);r=ROUTES[d];idx=traci.vehicle.getRouteIndex(vid)
                if idx not in range(3) or traci.vehicle.getRoadID(vid)!=r[idx]:raise ValueError('unexpected edge or route')
                front=sum(lengths[e] for e in r[:idx])+traci.vehicle.getLanePosition(vid)
                length=traci.vehicle.getLength(vid);speed=traci.vehicle.getSpeed(vid)
                if not all(math.isfinite(v) for v in (front,length,speed)) or speed<0 or length<=0:raise ValueError('bad vehicle state')
                rows[vid]=Vehicle(d,front,length,speed)
            return rows
        p=SignalPlan(Q(1,10),Q(12),Q(25),Q(3),Q(10),Q(1),1,'MUTCD 4O demonstration timings, not field design')
        c=SignalController.initial('sumo-demo',1,'logical-corridor',p);before=snapshot()
        if before:raise ValueError('fixture must initialize empty')
        apply(c);rows=[];violations=[];through=CounterLike();transitions=[];vehicle_trace=[]
        for k in range(1,a.steps+1):
            old_phase=c.phase;old_displays=c.displays;traci.simulationStep();t=Q(k,10)
            if abs(traci.simulation.getTime()-float(t))>1e-6:raise ValueError('SUMO time mismatch')
            if traci.simulation.getStartingTeleportIDList() or traci.simulation.getEndingTeleportIDList():raise ValueError('teleport invalidates route sweep')
            after=snapshot();occ,entries=swept_occupants(before,after,bounds,traci.simulation.getDepartedIDList(),traci.simulation.getArrivedIDList())
            if occ['A'] and occ['B']:violations.append([str(t),'opposing_swept_occupancy'])
            for d,disp in zip('AB',old_displays):
                if disp=='RED' and entries[d]:violations.append([str(t),'red_entry',d,sorted(entries[d])])
                through[d]+=len(entries[d])
            if traci.simulation.getCollidingVehiclesIDList():violations.append([str(t),'sumo_collision'])
            queues={d:sum(v.route==d and v.front<bounds[d][0] and v.speed<.1 for v in after.values()) for d in 'AB'}
            current=sum(v.front>=bounds[v.route][0] and v.front-v.length<=bounds[v.route][1] for v in after.values())
            evidence=ClearanceObservation(c.last_tick,t,True,not any(occ.values()),'SUMO monotone route sweep fixture',c.controller_id,c.version,c.resource_id)
            c=c.advance(FlowSnapshot(t,queues['A'],queues['B'],current),evidence);apply(c)
            if c.phase!=old_phase:transitions.append(dict(time_s=float(t),from_phase=old_phase,to_phase=c.phase,queue_a=queues['A'],queue_b=queues['B'],sweep_empty=evidence.empty))
            rows.append(dict(time_s=float(t),phase=old_phase,next_phase=c.phase,queue_a=queues['A'],queue_b=queues['B'],swept_a=len(occ['A']),swept_b=len(occ['B']),entries_a=len(entries['A']),entries_b=len(entries['B'])))
            for vid,v in after.items():vehicle_trace.append(dict(time_s=float(t),id=vid,direction=v.route,front_m=v.front,speed_mps=v.speed,length_m=v.length))
            before=after
        trace=work/'vehicle_trace.jsonl';trace.write_text(''.join(json.dumps(r)+'\n' for r in vehicle_trace));good=not violations and through['A']>0 and through['B']>0 and any(r['to_phase']=='B_GREEN' for r in transitions) and any(r['to_phase']=='A_GREEN' for r in transitions)
        return dict(status='SUMO_LOGICAL_CORRIDOR_PASS' if good else 'REVIEW_REQUIRED',scope='TRAFFIC_ACTUATED_LOGICAL_CORRIDOR_NOT_PHYSICAL_SINGLE_LANE',sumo_version=traci.getVersion(),dt_s=.1,seed=a.seed,resource_bounds_m=bounds,entries=through,transitions=transitions,violations=violations,steps=rows,trace=str(trace),physical_clearance_certified=False,training_labels_generated=False)
    finally:traci.close()


def CounterLike():return {'A':0,'B':0}


def main():
    p=argparse.ArgumentParser();p.add_argument('--work',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--plot',type=Path);p.add_argument('--sumo',default='sumo');p.add_argument('--netconvert',default='netconvert');p.add_argument('--seed',type=int,default=17);p.add_argument('--steps',type=int,default=1800);a=p.parse_args()
    try:
        if not 1<=a.steps<=10000:raise ValueError('invalid bounded step count')
        out=run(a)
        if a.plot:
            import matplotlib;matplotlib.use('Agg')
            import matplotlib.pyplot as plt
            r=out['steps'];t=[x['time_s'] for x in r];fig,ax=plt.subplots(2,1,sharex=True,figsize=(10,6))
            for d in 'ab':ax[0].plot(t,[x['queue_'+d] for x in r],label=d.upper());ax[1].plot(t,[x['swept_'+d] for x in r],label=d.upper())
            ax[0].set_ylabel('queued vehicles');ax[1].set_ylabel('swept resource demand');ax[1].set_xlabel('time (s)')
            for z in ax:
                for q in out['transitions']:z.axvline(q['time_s'],ls=':',alpha=.4)
                z.legend()
            fig.tight_layout();a.plot.parent.mkdir(parents=True,exist_ok=True);fig.savefig(a.plot,dpi=150);plt.close(fig)
    except Exception as e:out=dict(status='ERROR',reason=f'{type(e).__name__}: {e}',traceback=traceback.format_exc(),training_labels_generated=False)
    a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(out,indent=2,allow_nan=False)+'\n');return 0 if out['status']=='SUMO_LOGICAL_CORRIDOR_PASS' else 4
if __name__=='__main__':raise SystemExit(main())
