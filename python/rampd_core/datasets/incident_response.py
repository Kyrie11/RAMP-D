"""Declared longitudinal corridor response, not a full WOMD counterfactual.
Projected vehicle centers, constant-acceleration substeps, no lane changes or births.
Only current states are consumed. Raw logs, full map and formal labels stay separate.
"""
from dataclasses import dataclass, asdict
from fractions import Fraction as Q
from itertools import combinations
import math
import numpy as np
from .incident_scenarios import lane_proposal, extend_unique_route, CLOCK_PROFILES, resource_applicability
from .split_manifest import canonical_digest

@dataclass(frozen=True)
class Vehicle:
    id: str
    s: float
    v: float
    length: float

@dataclass(frozen=True)
class Closure:
    # Relative to the common factual cutoff. Separate planned and actual clocks.
    start: float
    end: float
    generation: str = '0.1'
    issue: str = '0.2'
    publication: str = '0.3'
    planned_on: str = '0.8'
    planned_off: str = '4'
    effective_on: str = '0.8'
    effective_off: str = '4'
    def validate(self):
        g,i,p,a,b,on,off=map(Q,(self.generation,self.issue,self.publication,self.planned_on,self.planned_off,self.effective_on,self.effective_off))
        if not 0<=g<=i<=p or not g<=a<b or not g<=on<off or not math.isfinite(self.start) or not math.isfinite(self.end) or not 0<=self.start<self.end: raise ValueError('invalid closure clocks/extent')
    def active(self,t):return Q(self.effective_on)<=t<Q(self.effective_off)


def project(v, p, heading):
    v=np.asarray(v,float); p=np.asarray(p,float); ds=np.diff(v,axis=0); lens=np.linalg.norm(ds,axis=1); good=lens>1e-6
    if not good.any(): raise ValueError('degenerate lane')
    u=ds[good]/lens[good,None]; a=v[:-1][good]; t=np.clip(((p-a)*u).sum(1),0,lens[good]); dist=np.linalg.norm(a+t[:,None]*u-p,axis=1); j=int(dist.argmin())
    arc=float(np.r_[0.,np.cumsum(lens)][np.flatnonzero(good)[j]]+t[j]); return arc,float(dist[j]),float(u[j]@np.array([math.cos(heading),math.sin(heading)])),u[j]


def _projected_spec(meta, lane, current, eid):
    """Shared projection and closure placement; deliberately not polygon membership."""
    if lane['ego_distance_m']>1.25 or lane['centerline_length_m']<25.:raise ValueError('centerline proposal not suitable for longitudinal projection')
    line=lane['centerline']; vehicles=[]; excluded=[]; widths={}; L=lane['centerline_length_m']
    # Recompute length and ego projection, rather than trusting proposal metrics.
    actual_L=float(np.linalg.norm(np.diff(np.asarray(line,float),axis=0),axis=1).sum())
    if not math.isclose(L,actual_L,rel_tol=1e-9,abs_tol=1e-6):raise ValueError('lane length mismatch')
    for aid,category,st in current:
        if category!='vehicle':excluded.append([aid,'NON_VEHICLE']);continue
        x,d,h,u=project(line,[st['x'],st['y']],st['heading']); speed=float(u@np.array([st['vx'],st['vy']])); length=float(st['length'])
        if d>1.25 or h<.9 or speed<-.1 or length<=0 or x-length/2<0 or x+length/2>L:
            excluded.append([aid,'OUTSIDE_PROJECTED_MODEL']);continue
        vehicles.append(Vehicle(aid,x,max(0.,speed),length))
        if st.get('width') is not None and math.isfinite(st['width']) and st['width']>0:widths[aid]=float(st['width'])
    if eid not in {a.id for a in vehicles} or len(vehicles)<2:raise ValueError('requires ego and another aligned vehicle')
    e=next(a for a in vehicles if a.id==eid)
    # Closure starts far enough ahead for nominal braking; no claim of reachability.
    start=e.s+e.length/2+max(8.,e.v*1.5+e.v**2/6+2.)
    if start+8>L:raise ValueError('insufficient downstream extent for closure')
    closure=Closure(start,start+8.)
    others=sorted((a for a in vehicles if a.id!=eid),key=lambda a:(abs(a.s-e.s),a.id))
    receipts={eid:'1.2'}; receipts.update({a.id:('0.5' if j%2==0 else None) for j,a in enumerate(others)})
    scope_lanes=[x['lane_id'] for x in lane.get('route_segments',[dict(lane_id=lane['lane_id'],start_m=0.,end_m=L)]) if x['end_m']>=start and x['start_m']<=start+8.]
    return dict(**meta,ego_id=eid,lane=lane,vehicles=[asdict(a) for a in vehicles],excluded_current=excluded,receipts=receipts,closure=asdict(closure),closure_lane_ids=scope_lanes,projected_widths=widths)


def from_record(record, *, extend_route=False, clock_profile="nominal", prepend_route=False, recipient_policy="all_current_nearest"):
    """Restrictive 1-D projection, never a lane-membership or resource proof."""
    s=record['scene']; m=s['manifest']; k=m['current_time_index']; idx=m['metadata']['source_track_indices'].index(m['metadata']['sdc_track_index']); eid=str(s['tracks'][idx]['track_id']); lane=lane_proposal(record,max_distance=1.25,min_length=2. if extend_route else 25.,min_ahead=0. if extend_route else 10.,min_alignment=.9 if extend_route else .7)
    if prepend_route and not extend_route:raise ValueError("prepend requires route extension")
    if extend_route: lane=extend_unique_route(record,lane,max_lanes=24 if prepend_route else 12,prepend=prepend_route)
    current=[(str(a['track_id']),a['category'],a['states'][k]) for a in s['tracks'] if a['states'][k]['valid'] is True]
    spec=_projected_spec(dict(family_id=m['scenario_id'],split=m['split'],source_digest=record['record_sha256'],cutoff=str(Q(str(m['timestamps'][k]))),scope='WOMD_INITIALIZED_PROJECTED_SUBSCENE_NOT_FULL_WORLD'),lane,current,eid)
    if clock_profile not in CLOCK_PROFILES:raise ValueError('unknown clock profile')
    cp=CLOCK_PROFILES[clock_profile]; c=spec['closure']; c.update({key:cp[key] for key in ('generation','issue','publication','planned_on','planned_off','effective_on','effective_off')});Closure(**c).validate()
    # Full current recipient roster, independent of projected actor inclusion.
    ego=next(st for i,_,st in current if i==eid); others=sorted((z for z in current if z[0]!=eid),key=lambda z:(math.hypot(z[2]['x']-ego['x'],z[2]['y']-ego['y']),z[0]))
    if recipient_policy not in ('all_current_nearest','projected_nearest','route_equipped'):raise ValueError('recipient policy')
    if recipient_policy=='projected_nearest':
        e=next(v for v in spec['vehicles'] if v['id']==eid)
        selected=min((v for v in spec['vehicles'] if v['id']!=eid),key=lambda v:(abs(v['s']-e['s']),v['id']))['id']
    else:selected=others[0][0] if others else None
    all_rec={eid:cp['ego_receipt']};all_rec.update({a[0]:(cp['other_receipt'] if a[0]==selected else None) for a in others})
    if recipient_policy=='route_equipped':
        from .rule_lifecycle import route_equipped_recipients
        cohort=route_equipped_recipients([v['id'] for v in spec['vehicles']],eid,source_digest=spec['source_digest'],other_receipt=cp['other_receipt'],ego_receipt=cp['ego_receipt'])
        all_rec={i:cohort.get(i) for i in all_rec}
        spec['recipient_model']=dict(probability=.5,seed=7,scope='DECLARED_ROUTE_EQUIPMENT_NOT_EMPIRICAL')
    spec.update(receipts={v['id']:all_rec[v['id']] for v in spec['vehicles']},all_current_receipts=all_rec,clock_profile=clock_profile,schedule_source='DECLARED_RAW_PROFILE',recipient_policy=recipient_policy)
    return spec


def from_feature_and_proposal(row, proposal):
    """Reconstruct current state only from a source-bound pilot cache + lane proposal.
    Cannot prove map geometry from cropped features; raw source replay remains required.
    """
    lane=proposal['lane_proposal']; event=proposal['binding']['event']; digest=canonical_digest({'event':event,'deliveries':proposal['deliveries'],'lane':lane})
    if digest!=proposal['scenario_spec_sha256'] or row['scenario_id']!=proposal['family_id'] or row['source_digest']!=proposal['source_digest'] or row['source_digest']!=event['record_sha256'] or row['scenario_id']!=event['scenario_id'] or str(event['lane_id'])!=str(lane['lane_id']) or row['split']!=proposal['split'] or row['ego_id']!=proposal['ego_id'] or Q(str(row['context']['decision_time_s']))!=Q(proposal['decision_time']):raise ValueError('feature/proposal identity mismatch')
    if row['frame']['position_reference']!='bounding_box_center':raise ValueError('unsupported reference point')
    yaw=row['frame']['yaw']; x,y=row['frame']['origin']; c,s=math.cos(yaw),math.sin(yaw); current=[]
    for aid,h,cat in zip(row['actor_ids'],row['inputs']['history'],row['inputs']['category']):
        q=h[-1]
        if q[9]!=1 or q[8]>1e-8:raise ValueError('invalid current state')
        px,py,sn,cs,vx,vy,l,w=q[:8]
        current.append((str(aid),'vehicle' if cat[0]==1 else 'other',dict(x=x+c*px-s*py,y=y+s*px+c*py,heading=yaw+math.atan2(sn,cs),vx=c*vx-s*vy,vy=s*vx+c*vy,length=l,width=w)))
    meta=dict(family_id=row['scenario_id'],split=row['split'],source_digest=row['source_digest'],cutoff=proposal['decision_time'],scope='CACHE_AND_PROPOSAL_PROJECTED_SUBSCENE_NOT_RAW_REPLAY',source_proposal_digest=digest,cache_actors_dropped=row['stats']['actors_dropped'])
    spec=_projected_spec(meta,lane,current,str(row['ego_id']))
    # Replay the supplied proposal, not a newly sampled recipient schedule.
    from .rule_overlay import RuleOverlay,ScheduledDelivery
    ev=RuleOverlay(**event)
    if ev.kind!='LANE_CLOSURE' or not ev.announce_window or ev.receipt is not None:raise ValueError('unsupported proposal rule semantics')
    cutoff=Q(proposal['decision_time']); deliveries=[ScheduledDelivery(**d) for d in proposal['deliveries']]
    if Q(ev.generation)<cutoff or not deliveries or len({d.recipient for d in deliveries})!=len(deliveries) or len({Q(d.publication) for d in deliveries})!=1:raise ValueError('proposal clock/roster')
    for d in deliveries:d.validate(ev)
    rec={d.recipient:None if d.receipt is None else str(Q(d.receipt)-cutoff) for d in deliveries}
    ids={v['id'] for v in spec['vehicles']}
    if not set(map(str,row['actor_ids']))<=rec.keys():raise ValueError('proposal missing cached current recipient')
    if not ids<=rec.keys():raise ValueError('proposal missing projected recipient')
    rel=lambda t:str(Q(t)-cutoff)
    cl=Closure(spec['closure']['start'],spec['closure']['end'],rel(ev.generation),rel(ev.issue),rel(deliveries[0].publication),rel(ev.announced_window()[0]),rel(ev.announced_window()[1]),rel(ev.effective_on),rel(ev.effective_off));cl.validate()
    spec.update(closure=asdict(cl),receipts={i:rec[i] for i in sorted(ids)},schedule_source='BOUND_PROPOSAL',all_current_receipts=rec,unprojected_recipient_count=len(rec)-len(ids))
    return spec


def observation_contract(spec):
    """Optional declared sensor and reaction model; no physical ACK is inferred."""
    o=spec.get('observation_model')
    if o is None:return None
    if set(o)!={'physical_on','physical_off','range_m'}:raise ValueError('observation contract fields')
    on,off=map(Q,(o['physical_on'],o['physical_off']))
    if not Q(spec['closure']['generation'])<=on<off or not math.isfinite(o['range_m']) or o['range_m']<=0:raise ValueError('observation clock/range')
    return o


def observed_public(c,rec,actor_state,t,event,o):
    received=event and rec is not None and Q(rec)<=t
    view={'received':True,'announced_window':[c.planned_on,c.planned_off]} if received else {'received':False}
    if o is not None:
        s,v,l=actor_state
        # Declared perfect local line-of-sight proxy, forward coverage only.
        coverage=s-l/2<=c.end and s+l/2+o['range_m']>=c.start
        view['local_blocked']=bool(event and Q(o['physical_on'])<=t<Q(o['physical_off'])) if coverage else None
    return view


def reaction_evidence(pair):
    """Observed clocks vs behavioral change, never infer human awareness."""
    spec=pair['spec'];o=observation_contract(spec);out={}; lag=Q(spec.get('reaction_delay_s','0'))
    for name,run in pair['runs'].items():
        ref=pair['runs']['NO_EVENT'];com=list(zip(run['frames'],ref['frames']));ids=run['frames'][0]['state']; h=Q(run['decision_dt']);rows={}
        for i in ids:
            first=next((f['t'] for f in run['frames'] if f['public'][i]['received']),None)
            seen=next((f['t'] for f in run['frames'] if f['public'][i].get('local_blocked') is True),None)
            # A vs NO_EVENT isolates rule with same ego policy and response parameters.
            diff=next((str(Q(f['t'])-h) for f,g in com[1:] if abs(f['controls_from_previous'][i]-g['controls_from_previous'][i])>1e-7),None) if name=='A' else None
            rows[i]=dict(message_available_at_tick=first,first_local_positive_tick=seen,first_control_difference_vs_no_event_tick=diff,declared_response_delay_s=str(lag))
        out[name]=rows
    return out


def rollout(spec, *, event=True, ego_brake=False, steps=60, dt='0.1', response='nominal'):
    if type(steps) is not int or steps<=0 or type(event) is not bool or type(ego_brake) is not bool or response not in ('nominal','cautious'):raise ValueError('rollout settings')
    c=Closure(**spec['closure']); c.validate(); h=Q(dt); L=float(spec['lane']['centerline_length_m']); eid=spec['ego_id']; actors=[Vehicle(**a) for a in spec['vehicles']]; rec=spec['receipts']; ids={a.id for a in actors}
    if h<=0 or h>Q(1,10) or c.end>L or len(ids)!=len(actors) or eid not in ids or set(rec)!=ids:raise ValueError('invalid scope/roster')
    if any(v is not None and Q(v)<Q(c.publication) for v in rec.values()):raise ValueError('receipt before publication')
    if any(not all(map(math.isfinite,(a.s,a.v,a.length))) or a.v<0 or a.length<=0 or a.s-a.length/2<0 or a.s+a.length/2>L for a in actors):raise ValueError('invalid initial footprint')
    if any(abs(a.s-b.s)<=(a.length+b.length)/2 for a,b in combinations(actors,2)):raise ValueError('overlapping initial footprints')
    o=observation_contract(spec); lag=Q(spec.get('reaction_delay_s','0'))
    if lag<0:raise ValueError('negative response delay')
    state={a.id:[a.s,a.v,a.length] for a in actors}; frames=[]; violations=[]; stop='HORIZON'; accel_max=1.5; brake_max=4.0; headway=1.4 if response=='nominal' else 2.0
    # Control decisions only on the public fixed grid. Hidden event times never
    # create an extra response update for an uninformed participant.
    ts=[j*h for j in range(steps+1)]
    def occupied(st):return sorted(a for a,(s,v,l) in st.items() if s+l/2>=c.start and s-l/2<=c.end)
    def snapshot(t):
        return dict(t=str(t),rule_active=event and c.active(t),public={a:observed_public(c,rec[a],state[a],t,event,o) for a in sorted(ids)},state={a:list(state[a]) for a in sorted(ids)},occupied=occupied(state),physical_ack=None)
    frames.append(snapshot(Q(0)))
    for t,tn in zip(ts,ts[1:]):
        d=float(tn-t); order=sorted(ids,key=lambda a:state[a][0],reverse=True); controls={}; old={a:list(v) for a,v in state.items()}; current_occ=set(occupied(old))
        for j,a in enumerate(order):
            s,v,l=old[a]; target=8.; acc=max(-brake_max,min(accel_max,(target-v)*.8)); gap=math.inf; lead_v=0.
            if j:
                ls,lv,ll=old[order[j-1]];gap=ls-ll/2-(s+l/2);lead_v=lv
            # A receiver can react to announced future closure, never to hidden actual effectivity.
            aware=event and rec[a] is not None and Q(rec[a])+lag<=t<Q(c.planned_off)
            if o is not None:
                mature=next((f for f in reversed(frames) if Q(f['t'])<=t-lag),None)
                local=mature is not None and mature['public'][a].get('local_blocked') is True
                aware=aware or local
            if aware and s+l/2<=c.start and c.start-(s+l/2)<gap:gap=c.start-(s+l/2);lead_v=0.
            if math.isfinite(gap):
                desired=2.+headway*v+max(0.,v*(v-lead_v)/(2*math.sqrt(accel_max*brake_max)))
                acc=min(acc,accel_max*(1-(v/8.)**4-(desired/max(gap,.05))**2))
            if a==eid and ego_brake and Q('0.4')<=t<Q('2.4'):acc=min(acc,-2.)
            acc=max(-brake_max,min(accel_max,acc)); controls[a]=acc
        # Model integration is monotone forward, stopping within a substep if needed.
        for a,(s,v,l) in old.items():
            ac=controls[a]; effective=min(d,v/-ac) if ac<0 else d; state[a]=[s+v*effective+.5*ac*effective**2,max(0.,v+ac*d),l]
        # Entry time within the constant-acceleration interval; compare with
        # independent actual clock. Float near-boundary cases remain UNKNOWN.
        for a,(s,v,l) in old.items():
            ns=state[a][0]; front=s+l/2; nf=ns+l/2
            if event and front<c.start<=nf:
                dist=c.start-front; ac=controls[a]; disc=max(0.,v*v+2*ac*dist); denom=v+math.sqrt(disc)
                if denom<=0: violations.append(dict(t=[str(t),str(tn)],kind='ENTRY_TIME_UNKNOWN',actor=a));continue
                te=float(t)+2*dist/denom; on,off=float(Q(c.effective_on)),float(Q(c.effective_off))
                if min(abs(te-on),abs(te-off))<=1e-8: kind='ENTRY_CLOCK_BOUNDARY_UNKNOWN'
                elif on<te<off: kind='CLOSED_ENTRY'
                else: continue
                violations.append(dict(t=[str(t),str(tn)],entry_time_s=te,kind=kind,actor=a))
        # A time interval with a possible overlap is not certified collision-free.
        # Conservative swept-interval diagnostic, distinct from sampled overlap.
        for a,b in combinations(sorted(ids),2):
            sa,_,la=old[a];sb,_,lb=old[b];na=state[a][0];nb=state[b][0]
            if abs(na-nb)<=(la+lb)/2 or (sa-sb)*(na-nb)<=0:violations.append(dict(t=[str(t),str(tn)],kind='SAMPLED_OR_ORDER_CROSSING',actors=[a,b]))
            elif max(sa-la/2,sb-lb/2)<=min(na+la/2,nb+lb/2):violations.append(dict(t=[str(t),str(tn)],kind='POSSIBLE_SWEPT_OVERLAP',actors=[a,b]))
        snap=snapshot(tn);snap['controls_from_previous']=controls;snap['entered_since_previous']=sorted(set(snap['occupied'])-current_occ);snap['cleared_since_previous']=sorted(current_occ-set(snap['occupied']));frames.append(snap)
        if any(v['kind']=='SAMPLED_OR_ORDER_CROSSING' and v['t'][-1]==str(tn) for v in violations):stop='MODEL_COLLISION_OR_ORDER_CROSSING';break
        if any(s+l/2>L+1e-8 for s,v,l in state.values()):stop='MODEL_ROUTE_END';break
    return dict(event=event,ego_brake=ego_brake,response=response,frames=frames,violations=violations,stop=stop,decision_dt=str(h),off_grid_receipt_semantics='AVAILABLE_AT_NEXT_CONTROL_TICK',actual_clock_used_only_in_monitor=True,physical_verified=False,formal_sc=False,requested_steps=steps)


def paired(spec,steps=60):
    """Separate rule intervention and ego intervention; keep exogenous schedule fixed for latter."""
    a=rollout(spec,steps=steps); aa=rollout(spec,steps=steps); b=rollout(spec,ego_brake=True,steps=steps); n=rollout(spec,event=False,steps=steps); alt=rollout(spec,ego_brake=True,steps=steps,response='cautious'); alt_a=rollout(spec,steps=steps,response='cautious')
    def delta(x,y):
        pair=list(zip(x['frames'],y['frames'])); eid=spec['ego_id']; ds={i:max(abs(f['state'][i][0]-g['state'][i][0]) for f,g in pair) for i in pair[0][0]['state']};return dict(common_frames=len(pair),ego_m=ds[eid],other_m=max((v for i,v in ds.items() if i!=eid),default=0.),per_actor=ds)
    return dict(schema='rampd.projected_closure_pair.v1',spec=spec,spec_sha256=canonical_digest(spec),runs={'A':a,'AA':aa,'B':b,'NO_EVENT':n,'CAUTIOUS_A':alt_a,'CAUTIOUS_B':alt},aa_equal=a==aa,ego_intervention=delta(a,b),rule_intervention=delta(n,a),alternative_response=delta(alt_a,alt),all_training_masks=False,formal_sc=False,scope='DECLARED_MODEL_DIAGNOSTIC_NOT_REAL_COUNTERFACTUAL')


def audit_pair(pair):
    """Independent trace consistency checks, not an independent behavior oracle.
    Does not rerun the controller or certify continuous geometry.
    """
    spec=pair['spec']; c=Closure(**spec['closure']);c.validate(); o=observation_contract(spec); errors=[];
    if Q(spec.get('reaction_delay_s','0'))<0:raise ValueError('negative response delay')
    ids={a['id'] for a in spec['vehicles']}; rec=spec['receipts']
    if pair['spec_sha256']!=canonical_digest(spec):errors.append('SPEC_HASH')
    if 'all_current_receipts' in spec:
        full=spec['all_current_receipts'];expected=ids|{x[0] for x in spec['excluded_current']}
        if not expected<=full.keys() or (spec.get('schedule_source')=='DECLARED_RAW_PROFILE' and expected!=full.keys()) or any(rec[i]!=full[i] for i in ids):errors.append('FULL_RECIPIENT_ROSTER')
        if any(x is not None and Q(x)<Q(c.publication) for x in full.values()):errors.append('RECEIPT_BEFORE_PUBLICATION')
    if set(pair['runs'])!={'A','AA','B','NO_EVENT','CAUTIOUS_A','CAUTIOUS_B'}:return dict(ok=False,errors=['RUN_ROSTER'],scope='TRACE_CONSISTENCY_ONLY')
    for name,run in pair['runs'].items():
        expected_violations=[]
        expected_event=name!='NO_EVENT';expected_brake=name in ('B','CAUTIOUS_B');expected_response='cautious' if name.startswith('CAUTIOUS') else 'nominal'
        if (run['event'],run['ego_brake'],run['response'])!=(expected_event,expected_brake,expected_response):errors.append(name+':INTERVENTION')
        prev=None; h=Q(run['decision_dt']);frames=run['frames']
        if not frames:errors.append(name+':NO_FRAMES');continue
        for j,f in enumerate(frames):
            t=Q(f['t'])
            if t!=j*h or set(f['state'])!=ids or set(f['public'])!=ids:errors.append(name+':CLOCK_OR_ROSTER');break
            if f['rule_active']!=(expected_event and Q(c.effective_on)<=t<Q(c.effective_off)) or f['physical_ack'] is not None:errors.append(name+':RULE_OR_ACK')
            for a in ids:
                delivered=expected_event and rec[a] is not None and Q(rec[a])<=t
                want={'received':True,'announced_window':[c.planned_on,c.planned_off]} if delivered else {'received':False}
                if o is not None:
                    x,_,l=f['state'][a]
                    covered=x-l/2<=c.end and x+l/2+o['range_m']>=c.start
                    want['local_blocked']=bool(expected_event and Q(o['physical_on'])<=t<Q(o['physical_off'])) if covered else None
                if f['public'][a]!=want:errors.append(name+':PUBLIC_VIEW')
            occ=sorted(a for a in ids if f['state'][a][0]>=c.start-f['state'][a][2]/2 and f['state'][a][0]<=c.end+f['state'][a][2]/2)
            if occ!=f['occupied']:errors.append(name+':SAMPLED_OCCUPANCY')
            if prev is None:
                expected={a['id']:[a['s'],a['v'],a['length']] for a in spec['vehicles']}
                if f['state']!=expected:errors.append(name+':INITIAL_STATE')
            else:
                ctrl=f['controls_from_previous']; d=float(h)
                if set(ctrl)!=ids:errors.append(name+':CONTROL_ROSTER');break
                for a in ids:
                    s0,v0,l0=prev['state'][a]; s1,v1,l1=f['state'][a]; ac=ctrl[a]
                    if not all(map(math.isfinite,(s0,v0,l0,s1,v1,l1,ac))) or not -4.<=ac<=1.5:errors.append(name+':CONTROL_OR_STATE');continue
                    v_expected=max(0.,v0+ac*d)
                    # Trapezoid on moving duration; independent of integration expression.
                    moving_d=d if ac>=0 or v0+ac*d>=0 else v0/(-ac)
                    if abs(s1-s0-(v0+v_expected)*moving_d/2)>1e-8 or abs(v1-v_expected)>1e-8 or l0!=l1:errors.append(name+':KINEMATIC_REPLAY')
                # Independently reconstruct entry time by monotone bisection,
                # rather than the quadratic root used by the simulator.
                for a in ids:
                    s0,v0,l0=prev['state'][a];s1,v1,l1=f['state'][a];ac=ctrl[a]
                    if expected_event and s0+l0/2<c.start<=s1+l1/2:
                        lo,hi=0.,d
                        for _ in range(60):
                            mid=(lo+hi)/2; md=min(mid,v0/(-ac)) if ac<0 else mid
                            if s0+(v0+max(0.,v0+ac*md))*md/2+l0/2<c.start:lo=mid
                            else:hi=mid
                        te=float(t-h)+(lo+hi)/2; on,off=float(Q(c.effective_on)),float(Q(c.effective_off))
                        kind='ENTRY_CLOCK_BOUNDARY_UNKNOWN' if min(abs(te-on),abs(te-off))<=1e-8 else ('CLOSED_ENTRY' if on<te<off else None)
                        if kind:
                            expected_violations.append((str(t-h),str(t),kind,a))
                            hits=[v for v in run['violations'] if v.get('actor')==a and v.get('kind')==kind and v.get('t')==[str(t-h),str(t)]]
                            if len(hits)!=1 or not isinstance(hits[0].get('entry_time_s'),(int,float)) or not math.isfinite(hits[0]['entry_time_s']) or abs(hits[0]['entry_time_s']-te)>1e-7:errors.append(name+':ENTRY_TIME_REPLAY')
                for u,w in combinations(sorted(ids),2):
                    su,_,lu=prev['state'][u];sw,_,lw=prev['state'][w];nu=f['state'][u][0];nw=f['state'][w][0]
                    if abs(nu-nw)<=(lu+lw)/2 or (su-sw)*(nu-nw)<=0:kind='SAMPLED_OR_ORDER_CROSSING'
                    elif max(su-lu/2,sw-lw/2)<=min(nu+lu/2,nw+lw/2):kind='POSSIBLE_SWEPT_OVERLAP'
                    else:kind=None
                    if kind:expected_violations.append((str(t-h),str(t),kind,u,w))
                if sorted(set(occ)-set(prev['occupied']))!=f['entered_since_previous'] or sorted(set(prev['occupied'])-set(occ))!=f['cleared_since_previous']:errors.append(name+':OCCUPANCY_TRANSITION')
            prev=f
        ledger=[(*v['t'],v['kind'],*([v['actor']] if 'actor' in v else v['actors'])) for v in run['violations']]
        if sorted(ledger)!=sorted(expected_violations):errors.append(name+':VIOLATION_LEDGER')
        L=spec['lane']['centerline_length_m'];last=frames[-1]
        if any(v[2]=='SAMPLED_OR_ORDER_CROSSING' and v[1]==last['t'] for v in expected_violations):want_stop='MODEL_COLLISION_OR_ORDER_CROSSING'
        elif any(x+l/2>L+1e-8 for x,v,l in last['state'].values()):want_stop='MODEL_ROUTE_END'
        else:want_stop='HORIZON'
        if run['stop']!=want_stop or (want_stop=='HORIZON' and 'requested_steps' in run and len(frames)!=run['requested_steps']+1):errors.append(name+':STOP_REASON')
    for key,left,right in [('ego_intervention','A','B'),('rule_intervention','NO_EVENT','A'),('alternative_response','CAUTIOUS_A','CAUTIOUS_B')]:
        frames=list(zip(pair['runs'][left]['frames'],pair['runs'][right]['frames']));eid=spec['ego_id'];delta=pair[key]
        if not frames:errors.append(key+':NO_COMMON_FRAMES');continue
        ds={i:max(abs(f['state'][i][0]-g['state'][i][0]) for f,g in frames) for i in ids}
        if delta['common_frames']!=len(frames) or set(delta['per_actor'])!=ids or any(abs(delta['per_actor'][i]-ds[i])>1e-8 for i in ids) or abs(delta['ego_m']-ds[eid])>1e-8 or abs(delta['other_m']-max((v for i,v in ds.items() if i!=eid),default=0.))>1e-8:errors.append(key+':DELTA')
    a,b,aa=(pair['runs'][k] for k in ('A','B','AA'))
    if a!=aa or pair['aa_equal'] is not True:errors.append('AA_REPRODUCTION')
    for f,g in zip(a['frames'],b['frames']):
        same_messages=all({k:v for k,v in f['public'][i].items() if k!='local_blocked'}=={k:v for k,v in g['public'][i].items() if k!='local_blocked'} for i in ids)
        if f['t']!=g['t'] or not same_messages or f['rule_active']!=g['rule_active']:errors.append('EXOGENOUS_OR_PUBLIC_PAIR')
    if pair['all_training_masks'] is not False or pair['formal_sc'] is not False:errors.append('AUTHORIZATION')
    return dict(ok=not errors,errors=sorted(set(errors)),scope='INDEPENDENT_TRACE_CONSISTENCY_NOT_CONTROLLER_ORACLE_OR_SAFETY')


def reconfigure_projected_pair(pair, *, recipient_policy='preserve'):
    """Derive a NEW declared schedule from an audited source pair. Never alters it."""
    import copy
    if not audit_pair(pair)['ok']:raise ValueError('source pair inconsistent')
    spec=copy.deepcopy(pair['spec']); spec['parent_spec_sha256']=pair['spec_sha256']
    if recipient_policy=='preserve':return spec
    if recipient_policy not in ('projected_nearest','route_equipped') or spec.get('schedule_source')!='DECLARED_RAW_PROFILE' or spec.get('clock_profile') not in CLOCK_PROFILES:raise ValueError('reconfiguration requires declared raw profile')
    full=spec['all_current_receipts']; eid=spec['ego_id'];e=next(v for v in spec['vehicles'] if v['id']==eid)
    target=min((v for v in spec['vehicles'] if v['id']!=eid),key=lambda v:(abs(v['s']-e['s']),v['id']))['id']
    cp=CLOCK_PROFILES[spec['clock_profile']]
    spec['all_current_receipts']={i:(cp['ego_receipt'] if i==eid else cp['other_receipt'] if i==target else None) for i in full}
    if recipient_policy=='route_equipped':
        from .rule_lifecycle import route_equipped_recipients
        cohort=route_equipped_recipients(list(spec['receipts']),eid,source_digest=spec['source_digest'],other_receipt=cp['other_receipt'],ego_receipt=cp['ego_receipt'])
        spec['all_current_receipts']={i:cohort.get(i) for i in full}
        spec['recipient_model']=dict(probability=.5,seed=7,scope='DECLARED_ROUTE_EQUIPMENT_NOT_EMPIRICAL')
    spec['receipts']={i:spec['all_current_receipts'][i] for i in spec['receipts']};spec['recipient_policy']=recipient_policy
    return spec
