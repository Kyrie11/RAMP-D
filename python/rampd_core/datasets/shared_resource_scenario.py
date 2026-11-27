"""Executable finite 2-D shared corridor benchmark, not SUMO/CARLA or Native SC.
Rectangles fixed axis-aligned, affine translation on each 0.5 s tick. Two opposing
approach/exit lanes physically merge into the SAME rectangle. No future visibility.
"""
from fractions import Fraction as Q
from itertools import combinations
from ..finite_joint_reference import contact
from ..shared_resource_controller import SharedResourceController,SignalCommand
from .split_manifest import canonical_digest

RESOURCE=(-6,-4,18,4)
ROSTER={'e':'A','a':'A','b':'B','c':'B'}

def rectangle(direction,s):
    # s increases in driving direction. All waypoint breakpoints on integer grid.
    x=s if direction=='A' else 12-s
    y=Q(0)
    if x<-6 or x>18:y=Q(3 if direction=='A' else -3)
    elif x<0:y=Q(3 if direction=='A' else -3)*(-x)/6
    elif x>12:y=Q(3 if direction=='A' else -3)*(x-12)/6
    return (x-2,y-1,x+2,y+1)

def _boxes(states):return {i:rectangle(ROSTER[i],Q(s)) for i,s in states.items()}
def _occ(boxes):return {i:contact(b,b,RESOURCE,RESOURCE) is not None for i,b in boxes.items()}
def _spans(a,b):return {i:contact(a[i],b[i],RESOURCE,RESOURCE) for i in a}
def _serialize(spans):return {i:None if p is None else [str(x) for x in p] for i,p in spans.items()}

def simulate(*,seed=0,ego_wait_ticks=0,ack_delay_ticks=1,clearance_ticks=2,steps=160,green_ticks=16):
    if any(type(x) is not int or x<0 for x in (seed,ego_wait_ticks,ack_delay_ticks)) or type(steps) is not int or steps<1:raise ValueError('scenario configuration')
    # The seed is a declared initial spacing variant, not an empirical distribution.
    states={'e':-10-seed%3,'a':-16-seed%3,'b':-10-(seed//3)%3,'c':-16-(seed//3)%3}
    c=SharedResourceController(ROSTER,clearance_ticks=clearance_ticks,green_ticks=green_ticks)
    pending=[(0,c.command)];ack=None;empty=None;frames=[];last_command=c.command
    for k in range(steps):
        if pending and pending[0][0]<=k:
            _,ack=pending.pop(0)
        a=_boxes(states);occ=_occ(a);g=c.step(k,occ,prior_swept_empty=empty,ack=ack)
        if c.command!=last_command:
            pending.append((k+max(1,ack_delay_ticks),c.command));last_command=c.command
        nxt=dict(states); actions={}
        for i,s in states.items():
            direction=ROSTER[i];candidate=s+1; dest=rectangle(direction,Q(candidate));entry=not occ[i] and contact(a[i],dest,RESOURCE,RESOURCE) is not None
            # Protected exit: a car already in resource can clear even under RED.
            # Outside it, the displayed, confirmed local signal is the sole permission.
            move=not entry or g['permit']==direction
            if i=='e' and k<ego_wait_ticks:move=False
            # Queue gap: update using prior states, no future state of lead vehicle.
            if any(ROSTER[j]==direction and 0<states[j]-s<=5 for j in states if i!=j):move=False
            # Once cleared, continue to a separate terminal lane, then hold.
            if s>=45:move=False
            nxt[i]=candidate if move else s;actions[i]=int(move)
        b=_boxes(nxt);spans=_spans(a,b);empty=all(v is None for v in spans.values())
        frames.append(dict(tick=k,t_s=str(Q(k,2)),state=dict(states),next_state=nxt,actions=actions,occupancy=occ,contact_spans=_serialize(spans),controller=g,public={i:dict(signal=g['permit']) for i in states}))
        states=nxt
    result=dict(schema='rampd.shared_corridor.v1',domain='DECLARED_2D_AFFINE_MODEL',family_id=f'shared-{seed}',seed=seed,ego_wait_ticks=ego_wait_ticks,ack_delay_ticks=ack_delay_ticks,clearance_ticks=clearance_ticks,green_ticks=green_ticks,steps=steps,resource=list(RESOURCE),roster=dict(ROSTER),frames=frames,final_state=states,formal_sc=False,real_world=False)
    result['digest']=canonical_digest(result);return result

def audit(run):
    """Independent ledger checks (not controller reexecution). Exact affine geometry.
    Validate versioned readback, full empty slabs before switching, entry permission,
    complete clearance, physical overlap and task goal; no real-world inference.
    """
    errors=[];last=None;red_empty=0;prev_ack_red=False;last_dir=None;entries={i:0 for i in ROSTER};exits={i:0 for i in ROSTER};prev_empty=None
    if run.get('digest')!=canonical_digest({k:v for k,v in run.items() if k!='digest'}):errors.append('DIGEST')
    if run['resource']!=list(RESOURCE) or run['roster']!=ROSTER or run['formal_sc'] is not False or run['real_world'] is not False or len(run['frames'])!=run['steps']:errors.append('CONTRACT')
    expected_initial={'e':-10-run['seed']%3,'a':-16-run['seed']%3,'b':-10-(run['seed']//3)%3,'c':-16-(run['seed']//3)%3}
    if not run['frames'] or run['frames'][0]['state']!=expected_initial:errors.append('INITIAL_STATE')
    pending=[(0,{'version':0,'direction':'RED'})];applied=None;issued={'version':0,'direction':'RED'}
    for k,f in enumerate(run['frames']):
        if pending and pending[0][0]<=k:_,applied=pending.pop(0)
        if set(f['state'])!=set(ROSTER) or set(f['next_state'])!=set(ROSTER) or f['tick']!=k or Q(f['t_s'])!=Q(k,2) or last is not None and f['state']!=last['next_state']:errors.append('CLOCK_ROSTER_HANDOFF');break
        a,b=_boxes(f['state']),_boxes(f['next_state']);o=_occ(a);n=_occ(b);spans=_spans(a,b);g=f['controller'];cmd=g['command'];ack=g['ack'];permit=g['permit']
        if ack!=applied:errors.append('MOCK_ACK_SCHEDULE')
        if cmd!=issued:pending.append((k+max(1,run['ack_delay_ticks']),cmd));issued=cmd
        if o!=f['occupancy'] or _serialize(spans)!=f['contact_spans']:errors.append('GEOMETRY_LEDGER')
        if set(f['actions'])!=set(ROSTER) or any(f['next_state'][i]-f['state'][i] not in (0,1) or f['actions'][i]!=f['next_state'][i]-f['state'][i] for i in ROSTER):errors.append('MOTION')
        if permit is not None and (permit not in ('A','B') or cmd!=ack or cmd['direction']!=permit):errors.append('ACK_PERMISSION')
        if any(f['public'][i]!={'signal':permit} for i in ROSTER):errors.append('PUBLIC_SIGNAL')
        confirmed_red=cmd==ack and cmd['direction']=='RED'
        # In a command-transition frame the controller may already have issued
        # the next command, although the matching RED readback still applies.
        if last is not None and prev_ack_red and prev_empty is True and ack==last['controller']['command'] and ack['direction']=='RED' and not any(o.values()):red_empty+=1
        elif not confirmed_red:red_empty=0 if cmd['direction']=='RED' else red_empty
        else:red_empty=0
        if cmd['direction'] in ('A','B') and (last is None or last['controller']['command']!=cmd):
            if red_empty<run['clearance_ticks'] or any(o.values()):errors.append('OPEN_WITHOUT_CLEARANCE')
            red_empty=0
        if last is not None:
            old=last['controller']['command'];dv=cmd['version']-old['version']
            if dv not in (0,1) or (dv==0 and old!=cmd) or (dv==1 and old['direction']==cmd['direction']):errors.append('VERSION')
        for i in ROSTER:
            if not o[i] and spans[i] is not None:
                entries[i]+=1
                if permit!=ROSTER[i]:errors.append('ILLEGAL_ENTRY')
            if o[i] and not n[i]:exits[i]+=1
        for i,j in combinations(ROSTER,2):
            if contact(a[i],b[i],a[j],b[j]) is not None:errors.append('COLLISION')
            if ROSTER[i]!=ROSTER[j] and spans[i] is not None and spans[j] is not None and max(spans[i][0],spans[j][0])<=min(spans[i][1],spans[j][1]):errors.append('CONFLICT')
        last=f;prev_empty=all(v is None for v in spans.values());prev_ack_red=confirmed_red
    if last is None or run['final_state']!=last['next_state']:errors.append('FINAL_STATE')
    if any(_occ(_boxes(run['final_state'])).values()):errors.append('RESOURCE_NOT_CLEARED')
    return dict(ok=not errors,errors=sorted(set(errors)),entries=entries,exits=exits,completed=all(s>=39 for s in run['final_state'].values()) and run['final_state']['e']>=45,ego_completed=run['final_state']['e']>=45,scope='EXACT_AFFINE_GEOMETRY_AND_LEDGER_NOT_NATIVE_SC')
