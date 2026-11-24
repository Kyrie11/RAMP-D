#!/usr/bin/env python3
"""Headless SUMO traffic-actuated bidirectional logical corridor experiment.
Separate directed SUMO lanes share one logical conflict resource. Not yet a
physically single-lane CARLA geometry or a continuous-world certificate.
"""
import argparse,json,math,shutil,subprocess,sys,traceback,hashlib
from pathlib import Path
from fractions import Fraction as Q
from dataclasses import dataclass
from collections import defaultdict
import xml.etree.ElementTree as ET
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'python'))

ROUTES={'A':('inA','midA','outA'),'B':('inB','midB','outB')}


def network(work,netconvert,traffic=None):
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
    if traffic is None:
        from rampd_core.a58_sumo_profiles import get_profile
        traffic=get_profile('baseline')
    r=ET.Element('routes');ET.SubElement(r,'vType',id='car',length='4.5',
        minGap=str(traffic.min_gap),maxSpeed=str(traffic.car_speed),
        accel=str(traffic.accel),decel=str(traffic.decel),
        emergencyDecel=str(traffic.emergency_decel),sigma=str(traffic.sigma),
        carFollowModel='IDM',tau=str(traffic.tau),speedFactor='1',speedDev=str(traffic.speed_dev))
    for d,edges in ROUTES.items():ET.SubElement(r,'route',id=d,edges=' '.join(edges))
    ET.SubElement(r,'flow',id='a',type='car',route='A',begin='0',end=str(traffic.horizon),period=str(traffic.period_a),departSpeed='0')
    ET.SubElement(r,'flow',id='b',type='car',route='B',begin='1',end=str(traffic.horizon),period=str(traffic.period_b),departSpeed='0')
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



def comfortable_switch_ready(vehicles,bounds,direction,*,reaction_s=.1,decel_mps2=4.,buffer_m=.0):
    """Experimental stop-feasibility screen, NOT a proof of actual behavior.
    Only the terminating movement, upstream fronts, fixed planning parameters.
    """
    if direction not in ROUTES or not all(math.isfinite(x) for x in (reaction_s,decel_mps2,buffer_m)) or reaction_s<0 or decel_mps2<=0 or buffer_m<0:raise ValueError('invalid comfort assumptions')
    bad=[];line=bounds[direction][0]
    for vid,v in vehicles.items():
        if v.route!=direction or not v.front<line or v.speed==0:continue
        d=line-v.front;stop=v.speed*reaction_s+v.speed*v.speed/(2*decel_mps2)+buffer_m
        if d<stop:bad.append((vid,d,stop))
    return not bad,tuple(sorted(bad))

def run(a):
    from rampd_core.a54_signal import SignalPlan,SignalController
    from rampd_core.a56_guard import GuardCase,GuardParent,advance_support
    from rampd_core.a53_rule_models import FlowSnapshot
    from rampd_core.a53b_interlock import ClearanceObservation
    import traci
    work=a.work.resolve();work.mkdir(parents=True,exist_ok=True)
    if any(work.iterdir()):raise ValueError('fresh empty work directory required')
    netconvert=shutil.which(a.netconvert);sumo=shutil.which(a.sumo)
    if not netconvert or not sumo:raise RuntimeError('sumo and netconvert executables required; check eclipse-sumo installation and PATH')
    from rampd_core.a58_sumo_profiles import get_profile
    traffic=get_profile(a.traffic_profile)
    network(work,netconvert,traffic)
    traci.start([sumo,'-n',str(work/'network.xml'),'-r',str(work/'routes.xml'),'--step-length','0.1','--step-method.ballistic','false','--seed',str(a.seed),'--time-to-teleport','-1','--collision.action','warn','--collision.check-junctions','true','--no-step-log','true','--log',str(work/'sumo.log')])
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
        signal_evidence=[]
        last_commanded={}
        metric=[]
        metric_enabled=getattr(a,'metric_samples',False)
        def apply(c):
            for d,display in zip('AB',c.displays):
                n,entry,exit=links[d];s=['r']*n
                for i in exit:s[i]='G'
                for i in entry:s[i]={'GREEN':'G','YELLOW':'y','RED':'r'}[display]
                target=''.join(s);traci.trafficlight.setRedYellowGreenState(d,target)
                returned=traci.trafficlight.getRedYellowGreenState(d)
                if returned!=target:raise ValueError('signal TraCI readback mismatch')
                raw_time=traci.simulation.getTime()
                stamp=Q(round(raw_time*10),10)
                if abs(float(stamp)-raw_time)>1e-6:
                    raise ValueError('SUMO controller command not on 0.1s tick')
                signal_evidence.append(dict(kind='COMMAND_READBACK',time=str(stamp),tls_id=d,
                    desired=target,readback=returned,controller_phase=c.phase,controller_version=c.version,
                    entry_link_indices=sorted(set(entry)),exit_link_indices=sorted(set(exit)),
                    proof_scope='TRACI_SIGNAL_STATE_NOT_FIELD_ACTUATION_ACK'))
                last_commanded[d]=target
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
        p=SignalPlan(Q(1,10),Q(12),Q(25),Q(3),Q(10),Q(1),1,'MUTCD 4O demonstration timings, not field design',Q(a.max_green_extension_s) if (a.comfort_guard or a.stop_reserve_guard) else Q(0))
        c=SignalController.initial('sumo-demo',1,'logical-corridor',p);before=snapshot()
        if before:raise ValueError('fixture must initialize empty')
        from rampd_core.a57_motion import brake_screen
        departure_ids=set(); arrival_ids=set(); entry_ids={d:set() for d in ROUTES}; clear_ids={d:set() for d in ROUTES}
        apply(c);rows=[];violations=[];through=CounterLike();transitions=[];vehicle_trace=[];roster=[];braking=[];switch_blocks=[];guard_exhausted=False
        for k in range(1,a.steps+1):
            old_phase=c.phase;old_displays=c.displays;old_rule_version=c.version;old_since=c.since;traci.simulationStep();t=Q(k,10)
            if abs(traci.simulation.getTime()-float(t))>1e-6:raise ValueError('SUMO time mismatch')
            for d in 'AB':
                observed=traci.trafficlight.getRedYellowGreenState(d)
                signal_evidence.append(dict(kind='POST_STEP_READBACK',time=str(t),tls_id=d,
                    expected=last_commanded[d],observed=observed,proof_scope='TRACI_SIGNAL_STATE_NOT_FIELD_ACTUATION_ACK'))
                if observed!=last_commanded[d]:
                    raise ValueError('SUMO signal state changed contrary to declared controller between ticks')
            if traci.simulation.getStartingTeleportIDList() or traci.simulation.getEndingTeleportIDList():raise ValueError('teleport invalidates route sweep')
            after=snapshot();departed=tuple(traci.simulation.getDepartedIDList());arrived=tuple(traci.simulation.getArrivedIDList());occ,entries=swept_occupants(before,after,bounds,departed,arrived)
            if metric_enabled:
                actors=[]
                for vid,v in sorted(after.items()):
                    x,y=traci.vehicle.getPosition(vid);angle=traci.vehicle.getAngle(vid);width=traci.vehicle.getWidth(vid)
                    if not all(math.isfinite(n) for n in (x,y,angle,width)) or width<=0:raise ValueError('invalid metric snapshot')
                    actors.append(dict(id=vid,front_bumper_xy=[x,y],angle_navigation_deg=angle,length_m=v.length,width_m=width,direction=v.route,lane_id=traci.vehicle.getLaneID(vid),speed_mps=v.speed))
                metric.append(dict(tick=k,time=str(t),rule_version=old_rule_version,phase=old_phase,phase_since=str(old_since),command_epoch=k-1,issue=str(t-Q(1,10)),command=dict(last_commanded),observed_execution={d:traci.trafficlight.getRedYellowGreenState(d) for d in 'AB'},departed=list(departed),arrived=list(arrived),actors=actors,logical_swept_occupants={d:sorted(occ[d]) for d in 'AB'},physical_rule_effective_time=None,physical_ack=None))
            roster.append(dict(time_s=float(t),departed=departed,arrived=arrived))
            if departure_ids.intersection(departed) or arrival_ids.intersection(arrived):raise ValueError('duplicate roster event')
            departure_ids.update(departed);arrival_ids.update(arrived)
            for d in ROUTES:
                entry_ids[d].update(entries[d])
                end=bounds[d][1]
                for vid,v in before.items():
                    if v.route==d and v.front-v.length<=end and (vid in arrived or (vid in after and after[vid].front-after[vid].length>end)):
                        clear_ids[d].add(vid)
            for vid in before.keys()&after.keys():
                dec=(before[vid].speed-after[vid].speed)/.1
                if dec>4.01:braking.append(dict(time_s=float(t),id=vid,deceleration_mps2=dec,phase=old_phase))
            if occ['A'] and occ['B']:violations.append([str(t),'opposing_swept_occupancy'])
            for d,disp in zip('AB',old_displays):
                if disp=='RED' and entries[d]:violations.append([str(t),'red_entry',d,sorted(entries[d])])
                through[d]+=len(entries[d])
            if traci.simulation.getCollidingVehiclesIDList():violations.append([str(t),'sumo_collision'])
            queues={d:sum(v.route==d and bounds[d][0]-a.detector_range_m<=v.front<bounds[d][0] and v.speed<.1 for v in after.values()) for d in 'AB'}
            current=sum(v.front>=bounds[v.route][0] and v.front-v.length<=bounds[v.route][1] for v in after.values())
            evidence=ClearanceObservation(c.last_tick,t,True,not any(occ.values()),'SUMO monotone route sweep fixture',c.controller_id,c.version,c.resource_id)
            flow=FlowSnapshot(t,queues['A'],queues['B'],current)
            ready,blocking=comfortable_switch_ready(after,bounds,old_phase[0]) if a.comfort_guard and old_phase.endswith('GREEN') else (True,())
            if a.stop_reserve_guard and old_phase.endswith('GREEN'):
                d=old_phase[0]; line=bounds[d][0]; blocking=tuple(sorted((vid,line-v.front,brake_screen(v.speed,reaction=a.reaction_s,accel_upper=2.,comfort=4.,standstill_gap=2.,extra=a.extra_stop_m)) for vid,v in after.items() if v.route==d and v.front<line and v.speed>0 and line-v.front<brake_screen(v.speed,reaction=a.reaction_s,accel_upper=2.,comfort=4.,standstill_gap=2.,extra=a.extra_stop_m)))
                ready=not blocking
            request=False
            if old_phase.endswith('GREEN'):
                same,opp=(queues['A'],queues['B']) if old_phase[0]=='A' else (queues['B'],queues['A'])
                request=t-c.since>=p.min_green and opp>0 and (opp-same>=p.queue_advantage or t-c.since>=p.max_green)
            if blocking:switch_blocks.append(dict(time_s=float(t),phase=old_phase,vehicles=blocking,switch_requested=request))
            try:
                _,post=advance_support((GuardParent('runtime',c,(GuardCase('tick',flow,evidence,switch_ready=ready),)),))
                c=post['silence'][0].controller
            except RuntimeError as exc:
                guard_exhausted=True;violations.append([str(t),'comfort_gate_exhausted',str(exc)])
            if not guard_exhausted:apply(c)
            if c.phase!=old_phase:transitions.append(dict(time_s=float(t),from_phase=old_phase,to_phase=c.phase,queue_a=queues['A'],queue_b=queues['B'],sweep_empty=evidence.empty))
            rows.append(dict(time_s=float(t),phase=old_phase,next_phase=c.phase,queue_a=queues['A'],queue_b=queues['B'],swept_a=len(occ['A']),swept_b=len(occ['B']),entries_a=len(entries['A']),entries_b=len(entries['B']),switch_ready=ready,switch_requested=request))
            for vid,v in after.items():vehicle_trace.append(dict(time_s=float(t),id=vid,direction=v.route,front_m=v.front,speed_mps=v.speed,length_m=v.length))
            before=after
            if guard_exhausted:break
        if metric_enabled:
            (work/'metric_actor_trace.jsonl').write_text(''.join(json.dumps(r,allow_nan=False)+'\n' for r in metric))
            (work/'metric_source.json').write_text(json.dumps(dict(status='SAMPLED_SUMO_METRIC_COORDINATES_NOT_SHARED_LANE_PROOF',network_sha256=hashlib.sha256((work/'network.xml').read_bytes()).hexdigest(),routes_sha256=hashlib.sha256((work/'routes.xml').read_bytes()).hexdigest(),actor_trace_sha256=hashlib.sha256((work/'metric_actor_trace.jsonl').read_bytes()).hexdigest(),reference='front_bumper_navigation_deg',ticks=len(metric),formal_labels_authorized=False),indent=2))
        signal_trace=work/'signal_trace.jsonl'
        signal_trace.write_text(''.join(json.dumps(r,allow_nan=False)+'\n' for r in signal_evidence))
        trace=work/'vehicle_trace.jsonl';trace.write_text(''.join(json.dumps(r)+'\n' for r in vehicle_trace));(work/'roster_trace.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in roster));good=not violations and through['A']>0 and through['B']>0 and any(r['to_phase']=='B_GREEN' for r in transitions) and any(r['to_phase']=='A_GREEN' for r in transitions)
        remaining=len(before);pending=traci.simulation.getMinExpectedNumber();drained=remaining==0 and pending==0
        completed=drained and departure_ids==arrival_ids==set().union(*entry_ids.values())==set().union(*clear_ids.values()) and all(entry_ids[d]==clear_ids[d] for d in ROUTES) and len(departure_ids)==traffic.expected_vehicles
        if a.require_drain and not completed:good=False
        if a.require_comfort and braking:good=False
        return dict(status='SUMO_LOGICAL_CORRIDOR_PASS' if good else 'REVIEW_REQUIRED',traffic_profile=traffic.name,expected_vehicles=traffic.expected_vehicles,scope='TRAFFIC_ACTUATED_LOGICAL_CORRIDOR_NOT_PHYSICAL_SINGLE_LANE',sumo_version=traci.getVersion(),dt_s=.1,seed=a.seed,resource_bounds_m=bounds,entries=through,transitions=transitions,violations=violations,steps=rows,trace=str(trace),roster_trace=str(work/'roster_trace.jsonl'),
                    signal_trace=str(signal_trace),signal_records=len(signal_evidence),
                    traci_signal_state_readback_observed=True,physical_signal_actuation_ack_verified=False,comfort_guard=a.comfort_guard,stop_reserve_guard=a.stop_reserve_guard,reaction_s=a.reaction_s,extra_stop_m=a.extra_stop_m,departed_count=len(departure_ids),arrived_count=len(arrival_ids),unique_entries={d:len(v) for d,v in entry_ids.items()},rear_clearances={d:len(v) for d,v in clear_ids.items()},roster_completion_pass=completed,detector_range_m=a.detector_range_m,max_green_extension_s=a.max_green_extension_s if (a.comfort_guard or a.stop_reserve_guard) else 0,comfort_review_required=bool(braking or guard_exhausted),brake_steps=braking,comfort_block_records=switch_blocks,remaining_vehicles=remaining,min_expected_number=pending,drained_at_cutoff=drained,physical_clearance_certified=False,training_labels_generated=False)
    finally:traci.close()


def CounterLike():return {'A':0,'B':0}


def main():
    p=argparse.ArgumentParser();p.add_argument('--traffic-profile',choices=('baseline','dense','slow_reaction','lower_friction_proxy'),default='baseline');p.add_argument('--work',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--plot',type=Path);p.add_argument('--sumo',default='sumo');p.add_argument('--netconvert',default='netconvert');p.add_argument('--seed',type=int,default=17);p.add_argument('--steps',type=int,default=1800);p.add_argument('--comfort-guard',action='store_true');p.add_argument('--stop-reserve-guard',action='store_true');p.add_argument('--reaction-s',type=float,default=.5);p.add_argument('--extra-stop-m',type=float,default=1.); p.add_argument('--max-green-extension-s',type=int,default=20);p.add_argument('--detector-range-m',type=float,default=200.);p.add_argument('--require-drain',action='store_true');p.add_argument('--require-comfort',action='store_true');p.add_argument('--metric-samples',action='store_true');a=p.parse_args()
    # Never overwrite a previous successful report when a work directory is reused.
    # Reuse is an experiment orchestration error, not an ERROR replacement record.
    if a.output.exists():
        print(f'EXISTING_SUMO_REPORT_PRESERVED: {a.output}; use a fresh work AND output path',file=sys.stderr)
        return 4
    try:
        if a.comfort_guard and a.stop_reserve_guard:raise ValueError('choose one guard')
        if not all(math.isfinite(x) and x>=0 for x in (a.reaction_s,a.extra_stop_m)):raise ValueError('bad reaction or margin')
        if not 1<=a.steps<=10000 or not 0<=a.max_green_extension_s<=120 or not math.isfinite(a.detector_range_m) or not 0<a.detector_range_m<=200:raise ValueError('invalid bounded experiment config')
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
