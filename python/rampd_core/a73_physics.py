"""Independent per-run CARLA diagnostics, not physical calibration."""
import math,hashlib,json,statistics

def digest(o):return hashlib.sha256(json.dumps(o,sort_keys=True,allow_nan=False,separators=(',',':')).encode()).hexdigest()
def num(x):
    if type(x) not in (int,float) or not math.isfinite(x):raise ValueError('nonfinite numeric field')
    return float(x)

def diagnose(doc,brake,mode,dt=.05,steer=.03,pulse=.15):
    if doc['status']!='RAW_CARLA_TRIALS_CAPTURED_NOT_CERTIFIED' or doc['calibrated_vehicle_dynamics'] is not False or doc['world_exclusive_confirmed'] is not True:raise ValueError('scope')
    if len(doc['trials'])!=1:raise ValueError('single run required')
    t=doc['trials'][0]; s=t['samples']; target=num(t['target_speed_mps']);
    if t['status']!='CAPTURED' or t['maneuver']!=('brake' if mode=='pure' else 'combined') or abs(num(doc['step_s'])-dt)>1e-8:raise ValueError('wrong cell')
    if abs(num(t['trigger_speed_mps'])-target)>.25:raise ValueError('initial speed out of tolerance')
    j=next(i for i,x in enumerate(s) if x['frame']==t['trigger_frame']);post=s[j+1:]
    if j<1 or len(post)*dt<1.9:raise ValueError('short trace')
    settings=doc['world_provenance']['settings'];
    if settings['synchronous_mode'] is not True or settings['substepping'] is not True or abs(num(settings['fixed_delta_seconds'])-dt)>1e-8 or dt>num(settings['max_substep_delta_time'])*num(settings['max_substeps'])+1e-9:raise ValueError('invalid step settings')
    for a,b in zip(s,s[1:]):
        if b['frame']!=a['frame']+1 or abs(num(b['sim_time_s'])-num(a['sim_time_s'])-dt)>1e-5:raise ValueError('clock gap')
    rows=[]
    for i,b in enumerate(post):
        a=s[j+i]; v0=num(a['planar_speed_mps']);v1=num(b['planar_speed_mps']); ax=num(b['signed_longitudinal_accel_mps2']);ay=num(b['signed_lateral_accel_mps2']);
        if min(v0,v1)<0 or b['command_issued_before_tick'] is not True:raise ValueError('invalid readback or speed')
        lane=b['lane_audit'];
        if lane['status']!='DESCRIPTIVE_RECTANGLE_WITHIN_LANE' or num(lane['available_halfwidth_m'])<num(lane['required_halfwidth_m']):raise ValueError('lane sample invalid')
        if any(b.get(k) is True for k in ('actual_hand_brake','actual_reverse','command_hand_brake','command_reverse')):raise ValueError('handbrake or reverse confound')
        if b.get('wheel_steer_query_error') is not None:raise ValueError('wheel steer readback unavailable')
        num(b['wheel_steer_deg_front_left_raw']);num(b['wheel_steer_deg_front_right_raw'])
        expected=steer if mode=='combined' and i*dt<pulse-1e-9 else 0.
        for field,val in [('brake',brake),('throttle',0.),('steer',expected)]:
            if any(abs(num(b[p+'_'+field])-val)>1e-5 for p in ('actual','command')):raise ValueError('mismatched '+field)
        # classify intervals, not just end frame. Speed derivative is not body ax on turns.
        regime='moving' if min(v0,v1)>=1 else 'stopped' if max(v0,v1)<=.01 else 'near_stop_or_crossing'
        rows.append(dict(frame=b['frame'],t_s=(i+1)*dt,v_before=v0,v_after=v1,ax=ax,ay=ay,dv_dt=(v1-v0)/dt,regime=regime))
    def stats(r):
        z=[x for x in rows if x['regime']==r];return dict(n=len(z),min_ax=min((x['ax'] for x in z),default=None),min_dv_dt=min((x['dv_dt'] for x in z),default=None))
    peak=min(rows,key=lambda x:x['ax']); stopped=next((x['t_s'] for x in rows if x['v_after']<=.01 and sum(y['t_s']>=x['t_s'] for y in rows)>=3 and all(y['v_after']<=.01 for y in rows if y['t_s']>=x['t_s'])),None)
    path=sum(math.hypot(num(a['x_m_carla'])-num(b['x_m_carla']),num(a['y_m_carla'])-num(b['y_m_carla'])) for a,b in zip(s[j:],post))
    # metadata not proof of independent experimental trials
    phy={k:v for k,v in doc['physics'].items() if k not in ('actor_id','body_transform','capture_frame','capture_state')}
    context={k:doc[k] for k in ('map','actor_type','carla_server_version','expected_start_lane','world_provenance')};context['physics']=phy;context['target_speed']=target
    return dict(status='DESCRIPTIVE_SINGLE_CAPTURE',digest=digest(doc),sample_digest=digest(s),context_digest=digest(context),initial_speed=num(t['trigger_speed_mps']),target_speed=target,peak=peak,regimes={r:stats(r) for r in ('moving','near_stop_or_crossing','stopped')},first_four=rows[:4],observed_sustained_stop_s=stopped,stop_right_censored=(stopped is None),sampled_path_m=path,gear_telemetry_complete=all(type(x.get('actual_gear')) is int for x in post),rows=rows,guaranteed_brake=False,tire_coupling_identified=False)

def campaign(arms,dt=.05,levels=(.15,.30,.45),repeats=3):
    errors=[];cells={};seen=set();contexts=set();all_initial=[]
    for b in levels:
        for mode in ('pure','combined'):
            key=f'{b:.2f}:{mode}'; good=[]
            for i,d in enumerate(arms.get((b,mode),[])):
                try:
                    r=diagnose(d,b,mode,dt)
                    if r['sample_digest'] in seen:raise ValueError('reused sampled trace')
                    seen.add(r['sample_digest']);contexts.add(r['context_digest']);all_initial.append(r['initial_speed']);good.append(r)
                except (ValueError,TypeError,KeyError,StopIteration,OverflowError) as e:errors.append(f'{key}:{i}:{e}')
            cells[key]=good
            if len(good)<repeats:errors.append(key+':INSUFFICIENT_VALID_RUNS')
    if len(contexts)>1:errors.append('CONTEXT_MISMATCH')
    if all_initial and max(all_initial)-min(all_initial)>.02:errors.append('TRIGGER_SPEED_MISMATCH')
    return dict(status='DESCRIPTIVE_REPLICATED_CAPTURE_MATRIX' if not errors else 'REVIEW',errors=errors,cells=cells,independence_proved=False,formal_labels_authorized=False)
