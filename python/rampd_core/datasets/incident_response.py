"""Declared longitudinal corridor response, not a full WOMD counterfactual.
Projected vehicle centers, constant-acceleration substeps, no lane changes or births.
Only current states are consumed. Raw logs, full map and formal labels stay separate.
"""
from dataclasses import dataclass, asdict
from fractions import Fraction as Q
from itertools import combinations
import math
import numpy as np
from .incident_scenarios import lane_proposal
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
    line=lane['centerline']; vehicles=[]; excluded=[]; L=lane['centerline_length_m']
    # Recompute length and ego projection, rather than trusting proposal metrics.
    actual_L=float(np.linalg.norm(np.diff(np.asarray(line,float),axis=0),axis=1).sum())
    if not math.isclose(L,actual_L,rel_tol=1e-9,abs_tol=1e-6):raise ValueError('lane length mismatch')
    for aid,category,st in current:
        if category!='vehicle':excluded.append([aid,'NON_VEHICLE']);continue
        x,d,h,u=project(line,[st['x'],st['y']],st['heading']); speed=float(u@np.array([st['vx'],st['vy']])); length=float(st['length'])
        if d>1.25 or h<.9 or speed<-.1 or length<=0 or x-length/2<0 or x+length/2>L:
            excluded.append([aid,'OUTSIDE_PROJECTED_MODEL']);continue
        vehicles.append(Vehicle(aid,x,max(0.,speed),length))
    if eid not in {a.id for a in vehicles} or len(vehicles)<2:raise ValueError('requires ego and another aligned vehicle')
    e=next(a for a in vehicles if a.id==eid)
    # Closure starts far enough ahead for nominal braking; no claim of reachability.
    start=e.s+e.length/2+max(8.,e.v*1.5+e.v**2/6+2.)
    if start+8>L:raise ValueError('insufficient downstream extent for closure')
    closure=Closure(start,start+8.)
    others=sorted((a for a in vehicles if a.id!=eid),key=lambda a:(abs(a.s-e.s),a.id))
    receipts={eid:'1.2'}; receipts.update({a.id:('0.5' if j%2==0 else None) for j,a in enumerate(others)})
    return dict(**meta,ego_id=eid,lane=lane,vehicles=[asdict(a) for a in vehicles],excluded_current=excluded,receipts=receipts,closure=asdict(closure))


def from_record(record):
    """Restrictive 1-D projection, never a lane-membership or resource proof."""
    s=record['scene']; m=s['manifest']; k=m['current_time_index']; idx=m['metadata']['source_track_indices'].index(m['metadata']['sdc_track_index']); eid=str(s['tracks'][idx]['track_id']); lane=lane_proposal(record,max_distance=1.25,min_length=25.)
    current=[(str(a['track_id']),a['category'],a['states'][k]) for a in s['tracks'] if a['states'][k]['valid'] is True]
    return _projected_spec(dict(family_id=m['scenario_id'],split=m['split'],source_digest=record['record_sha256'],cutoff=str(Q(str(m['timestamps'][k]))),scope='WOMD_INITIALIZED_PROJECTED_SUBSCENE_NOT_FULL_WORLD'),lane,current,eid)


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
        current.append((str(aid),'vehicle' if cat[0]==1 else 'other',dict(x=x+c*px-s*py,y=y+s*px+c*py,heading=yaw+math.atan2(sn,cs),vx=c*vx-s*vy,vy=s*vx+c*vy,length=l)))
    meta=dict(family_id=row['scenario_id'],split=row['split'],source_digest=row['source_digest'],cutoff=proposal['decision_time'],scope='CACHE_AND_PROPOSAL_PROJECTED_SUBSCENE_NOT_RAW_REPLAY',source_proposal_digest=digest,cache_actors_dropped=row['stats']['actors_dropped'])
    return _projected_spec(meta,lane,current,str(row['ego_id']))


def rollout(spec, *, event=True, ego_brake=False, steps=60, dt='0.1', response='nominal'):
    if type(steps) is not int or steps<=0 or type(event) is not bool or type(ego_brake) is not bool or response not in ('nominal','cautious'):raise ValueError('rollout settings')
    c=Closure(**spec['closure']); c.validate(); h=Q(dt); L=float(spec['lane']['centerline_length_m']); eid=spec['ego_id']; actors=[Vehicle(**a) for a in spec['vehicles']]; rec=spec['receipts']; ids={a.id for a in actors}
    if h<=0 or h>Q(1,10) or c.end>L or len(ids)!=len(actors) or eid not in ids or set(rec)!=ids:raise ValueError('invalid scope/roster')
    if any(v is not None and Q(v)<Q(c.publication) for v in rec.values()):raise ValueError('receipt before publication')
    if any(not all(map(math.isfinite,(a.s,a.v,a.length))) or a.v<0 or a.length<=0 or a.s-a.length/2<0 or a.s+a.length/2>L for a in actors):raise ValueError('invalid initial footprint')
    if any(abs(a.s-b.s)<=(a.length+b.length)/2 for a,b in combinations(actors,2)):raise ValueError('overlapping initial footprints')
    state={a.id:[a.s,a.v,a.length] for a in actors}; frames=[]; violations=[]; stop='HORIZON'; accel_max=1.5; brake_max=4.0; headway=1.4 if response=='nominal' else 2.0
    # Control decisions only on the public fixed grid. Hidden event times never
    # create an extra response update for an uninformed participant.
    ts=[j*h for j in range(steps+1)]
    def occupied(st):return sorted(a for a,(s,v,l) in st.items() if s+l/2>=c.start and s-l/2<=c.end)
    def snapshot(t):
        return dict(t=str(t),rule_active=event and c.active(t),public={a:({'received':True,'announced_window':[c.planned_on,c.planned_off]} if event and rec[a] is not None and Q(rec[a])<=t else {'received':False}) for a in sorted(ids)},state={a:list(state[a]) for a in sorted(ids)},occupied=occupied(state),physical_ack=None)
    frames.append(snapshot(Q(0)))
    for t,tn in zip(ts,ts[1:]):
        d=float(tn-t); order=sorted(ids,key=lambda a:state[a][0],reverse=True); controls={}; old={a:list(v) for a,v in state.items()}; current_occ=set(occupied(old))
        for j,a in enumerate(order):
            s,v,l=old[a]; target=8.; acc=max(-brake_max,min(accel_max,(target-v)*.8)); gap=math.inf; lead_v=0.
            if j:
                ls,lv,ll=old[order[j-1]];gap=ls-ll/2-(s+l/2);lead_v=lv
            # A receiver can react to announced future closure, never to hidden actual effectivity.
            aware=event and rec[a] is not None and Q(rec[a])<=t<Q(c.planned_off)
            if aware and s+l/2<c.start and c.start-(s+l/2)<gap:gap=c.start-(s+l/2);lead_v=0.
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
    return dict(event=event,ego_brake=ego_brake,response=response,frames=frames,violations=violations,stop=stop,decision_dt=str(h),off_grid_receipt_semantics='AVAILABLE_AT_NEXT_CONTROL_TICK',actual_clock_used_only_in_monitor=True,physical_verified=False,formal_sc=False)


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
    spec=pair['spec']; c=Closure(**spec['closure']);c.validate(); errors=[]; ids={a['id'] for a in spec['vehicles']}; rec=spec['receipts']
    if pair['spec_sha256']!=canonical_digest(spec):errors.append('SPEC_HASH')
    if set(pair['runs'])!={'A','AA','B','NO_EVENT','CAUTIOUS_A','CAUTIOUS_B'}:return dict(ok=False,errors=['RUN_ROSTER'],scope='TRACE_CONSISTENCY_ONLY')
    for name,run in pair['runs'].items():
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
                if sorted(set(occ)-set(prev['occupied']))!=f['entered_since_previous'] or sorted(set(prev['occupied'])-set(occ))!=f['cleared_since_previous']:errors.append(name+':OCCUPANCY_TRANSITION')
            prev=f
    a,b,aa=(pair['runs'][k] for k in ('A','B','AA'))
    if a!=aa or pair['aa_equal'] is not True:errors.append('AA_REPRODUCTION')
    for f,g in zip(a['frames'],b['frames']):
        if f['t']!=g['t'] or f['public']!=g['public'] or f['rule_active']!=g['rule_active']:errors.append('EXOGENOUS_OR_PUBLIC_PAIR')
    if pair['all_training_masks'] is not False or pair['formal_sc'] is not False:errors.append('AUTHORIZATION')
    return dict(ok=not errors,errors=sorted(set(errors)),scope='INDEPENDENT_TRACE_CONSISTENCY_NOT_CONTROLLER_ORACLE_OR_SAFETY')
