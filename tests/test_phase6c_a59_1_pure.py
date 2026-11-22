"""A59/1a targeted falsification tests: no native train or CARLA required."""
from dataclasses import replace
from fractions import Fraction as Q
from types import SimpleNamespace
import json,subprocess,sys
from pathlib import Path

import pytest
from rampd_core.a60_clock_resource import (ClockEvent,audit_clock_events,ResourceActor,ResourceSlice,
    ResourcePermission,audit_resource_transition,conditional_a59_1_bridge,ObligationAudit)
from rampd_core.a60_carla_evidence import inspect_trials,REQUIRED
from rampd_core.interval import Interval
from rampd_core.model import StateBounds
from rampd_core.footprint import VehicleGeometry,SweptFootprint
from rampd_core.resources import ResourceRegion


def ce(kind,time,domain='EXACT_MODEL',correlated_id=''):
    return ClockEvent('evt',kind,Q(time),'test',correlated_id,domain)


def fp(x,lo=Q(0),hi=Q(1)):
    state=StateBounds(Interval.point(x),Interval.point(0.),Interval.point(0.),
                      Interval.point(0.),Interval.point(0.),Interval.point(0.))
    return SweptFootprint(state,VehicleGeometry(2.,1.),lo,hi,'ego')


def rcheck(*,initial='OUT',x=0.,alpha=True,beta=True,exit_open=True,cap=1,
           complete=True,slabs=None):
    region=ResourceRegion('r',Interval(10,15),Interval(-2,2),capacity=cap)
    perm=ResourcePermission('r',alpha,beta,exit_open,('A',),cap)
    slices=(ResourceSlice(Q(0),Q(1),(('ego',fp(x)),)),) if slabs is None else slabs
    return audit_resource_transition(region,perm,(ResourceActor('ego','A',1,initial),),
                slices,complete_roster=complete,exact_tick_boundaries=True)


def test_clock_separate_model_event_times_and_splitting():
    e=(ce('ISSUE',Q(1,4)),ce('RECEIPT',Q(3,4)))
    assert audit_clock_events(e,start=Q(0),end=Q(1),complete=True).status=='UNKNOWN'
    assert audit_clock_events(e,start=Q(0),end=Q(1),split_times=(Q(1,4),Q(3,4)),complete=True).status=='CONDITIONAL_EXACT_MODEL_CLOCK_PASS'


def test_clock_causal_order_failure_even_after_split():
    a=audit_clock_events((ce('RECEIPT',Q(1,4)),ce('ISSUE',Q(3,4))),start=Q(0),end=Q(1),
                         split_times=(Q(1,4),Q(3,4)),complete=True)
    assert a.status=='UNKNOWN' and any('INVALID_CAUSAL' in k for k in a.reasons)


def test_external_report_clock_is_not_physical_onset():
    a=audit_clock_events((ce('EXT_ONSET',Q(0),'EXTERNAL_REPORT'),),start=Q(0),end=Q(1),complete=True)
    assert a.status=='UNKNOWN' and 'NONMODEL_CLOCK_CANNOT_PROVE_EXACT_EFFECTIVITY' in a.reasons


def test_command_ack_identity_binding():
    a=audit_clock_events((ce('COMMAND',Q(0),correlated_id='c1'),ce('ACK',Q(1),correlated_id='c2')),
                         start=Q(0),end=Q(1),complete=True)
    assert 'INVALID_CAUSAL_ORDER_OR_ID:evt:ACK' in a.reasons


def test_clock_incomplete_or_duplicate_fails_closed():
    assert audit_clock_events((),start=Q(0),end=Q(1)).status=='UNKNOWN'
    assert 'DUPLICATE_CLOCK_EVENT' in audit_clock_events((ce('ISSUE',Q(0)),ce('ISSUE',Q(0))),
                          start=Q(0),end=Q(1),complete=True).reasons


def test_safe_all_resource_footprints_proved_free_even_when_closed():
    assert rcheck(x=100,alpha=False,beta=False,exit_open=False).status=='CONDITIONAL_RESOURCE_SLAB_GATE_PASS'


def test_entry_closed_if_prior_out_and_current_possible():
    a=rcheck(x=12,alpha=False)
    assert a.status=='UNKNOWN' and 'ENTRY_CLOSED_REENTRY_NOT_EXCLUDED:ego' in a.reasons


def test_closed_stay_and_exit_independently_fail():
    assert 'STAY_OR_CLEAR_CLOSED_POSSIBLE:ego' in rcheck(x=12,beta=False).reasons
    assert 'EXIT_CLOSED_CLEARANCE_NOT_EXCLUDED:ego' in rcheck(x=9.,exit_open=False).reasons


def test_incumbent_proven_continuous_inside_can_stay_without_reentry():
    assert rcheck(x=12,initial='IN',alpha=False,exit_open=False).status=='CONDITIONAL_RESOURCE_SLAB_GATE_PASS'


def test_closed_entry_does_not_allow_exit_then_reentry():
    slabs=(ResourceSlice(Q(0),Q(1,3),(('ego',fp(12,Q(0),Q(1,3))),)),
           ResourceSlice(Q(1,3),Q(2,3),(('ego',fp(100,Q(1,3),Q(2,3))),)),
           ResourceSlice(Q(2,3),Q(1),(('ego',fp(12,Q(2,3),Q(1))),)))
    a=rcheck(initial='IN',alpha=False,slabs=slabs)
    assert a.status=='UNKNOWN' and 'ENTRY_CLOSED_REENTRY_NOT_EXCLUDED:ego' in a.reasons


def test_slab_gap_and_missing_roster_produce_unknown():
    gaps=(ResourceSlice(Q(0),Q(1,3),(('ego',fp(100,Q(0),Q(1,3))),)),
          ResourceSlice(Q(2,3),Q(1),(('ego',fp(100,Q(2,3),Q(1))),)))
    assert 'RESOURCE_SLAB_GAP_OR_OVERLAP' in rcheck(slabs=gaps).reasons
    assert 'UNPROVEN_ACTOR_ROSTER_COMPLETENESS' in rcheck(complete=False).reasons


def test_resource_capacity_must_count_possible_other_actor():
    region=ResourceRegion('r',Interval(10,15),Interval(-2,2),1)
    perm=ResourcePermission('r',True,True,True,('A',),1)
    slab=ResourceSlice(Q(0),Q(1),(('a',fp(12)),('b',fp(12))))
    a=audit_resource_transition(region,perm,(ResourceActor('a','A',1,'IN'),ResourceActor('b','A',1,'IN')),
                                (slab,),complete_roster=True,exact_tick_boundaries=True)
    assert a.status=='UNKNOWN' and 'CAPACITY_EXCEEDED_POSSIBLE' in a.reasons


def test_rank_bridge_never_upgrades_local_evidence_to_certified():
    rank=SimpleNamespace(status='CONDITIONAL_PHYSICAL_RANK_PREDECESSOR_CANDIDATE',certified=False)
    r=ObligationAudit('CONDITIONAL_RESOURCE_SLAB_GATE_PASS',())
    c=ObligationAudit('CONDITIONAL_EXACT_MODEL_CLOCK_PASS',())
    a=conditional_a59_1_bridge(rank,r,c)
    assert a.status=='CONDITIONAL_A59_1_SUBGATE_CANDIDATE' and not a.certified
    assert conditional_a59_1_bridge(rank,r,ObligationAudit('UNKNOWN',('MISSING_EVENT',))).status=='UNKNOWN'


def fabricated_log(repeats=1):
    trials=[]
    for speed in (5,10,15):
        for kind in ('brake','steer','combined'):
            for _ in range(repeats):
                samples=[]
                for k in range(15):
                    s=dict.fromkeys(REQUIRED,0.)
                    s['frame']=100+k;s['sim_time_s']=k*.05
                    s['speed_mps']=speed;s['signed_longitudinal_accel_mps2']=-2
                    if k>0:
                        if kind=='brake':s['command_brake']=0.7
                        if kind=='steer':s['command_steer']=0.08
                        if kind=='combined':s['command_brake']=0.45;s['command_steer']=0.08
                    samples.append(s)
                trials.append({'status':'CAPTURED','target_speed_mps':speed,
                               'maneuver':kind,'actor_id':(speed*100+len(trials)),'trigger_frame':100,
                               'trigger_speed_mps':speed,'samples':samples})
    return {'schema':'rampd.carla.a59_1.raw_trials.v1','map':'/Game/Carla/Maps/Town04',
            'carla_server_version':'0.9.16','actor_type':'vehicle.tesla.model3',
            'actor_id':1,'world_exclusive_confirmed':True,
            'physics':{'wheels':[{}]*4,'bounding_box':{'extent':{}}},'trials':trials}


def test_actor_sample_review_requires_complete_commands_and_repeats():
    a=fabricated_log();r=inspect_trials(a,required_repeats=1)
    assert r['status']=='SAMPLED_ACTOR_RESPONSE_LOGS_CAPTURED_UNCALIBRATED'
    assert not r['physical_certified'] and not r['model_error_enclosure_certified']
    assert inspect_trials(a,required_repeats=3)['status']=='REVIEW'


def test_carlog_rejects_missing_signal_and_noncontiguous_frames():
    a=fabricated_log();a['trials'][0]['samples'][2].pop('yaw_rate_radps_carla')
    assert any('MISSING_SIGNAL' in x for x in inspect_trials(a,required_repeats=1)['reasons'])
    a=fabricated_log();a['trials'][0]['samples'][3]['frame']+=3
    assert any('NONCONTIGUOUS_FRAME' in x for x in inspect_trials(a,required_repeats=1)['reasons'])


def test_carla_capture_requires_explicit_isolation_without_importing_carla(tmp_path):
    script=Path(__file__).resolve().parents[1]/'scripts/a60_carla_actor_trials.py'
    out=tmp_path/'never.json'
    x=subprocess.run([sys.executable,str(script),'--mode','capture','--output',str(out)],capture_output=True,text=True)
    assert x.returncode!=0 and 'ISOLATED_WORLD_ACK' in x.stderr and not out.exists()


def test_forged_named_maneuver_without_command_is_review():
    doc=fabricated_log()
    for s in doc['trials'][0]['samples']:
        s['command_brake']=0.
    assert any('MISSING_ACTUAL_COMMANDED_EXCITATION' in x
               for x in inspect_trials(doc,required_repeats=1)['reasons'])


def test_delayed_receipt_with_prior_issue_history_can_pass_model_clock():
    issue=ClockEvent('same_msg','ISSUE',Q(0),'model','message-7')
    receipt=ClockEvent('same_msg','RECEIPT',Q(2),'model','message-7')
    a=audit_clock_events((receipt,),start=Q(1),end=Q(2),
                         history_events=(issue,),complete=True)
    assert a.status=='CONDITIONAL_EXACT_MODEL_CLOCK_PASS'
    assert audit_clock_events((receipt,),start=Q(1),end=Q(2),complete=True).status=='UNKNOWN'


def test_carla_metadata_extraction_preserves_raw_wheel_and_offset_fields():
    import importlib.util
    from types import SimpleNamespace as NS
    script=Path(__file__).resolve().parents[1]/'scripts/a60_carla_actor_trials.py'
    spec=importlib.util.spec_from_file_location('a60_carla_script_unit',script)
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
    v=NS(x=10,y=20,z=1);rot=NS(pitch=0,yaw=0,roll=0)
    wheel=NS(position=v,radius=34,tire_friction=1.1,max_steer_angle=32,
             max_brake_torque=1400,max_handbrake_torque=1600)
    phy=NS(wheels=[wheel]*4,center_of_mass=v,mass=1600,drag_coefficient=.3,
           steering_curve=[NS(x=0,y=1)])
    box=NS(location=v,extent=v,rotation=rot)
    actor=NS(id=42,type_id='vehicle.tesla.model3',bounding_box=box,
             get_physics_control=lambda:phy,get_transform=lambda:NS(location=v,rotation=rot))
    world=NS(get_map=lambda:NS(name='/Game/Carla/Maps/Town04'))
    client=NS(get_server_version=lambda:'0.9.16')
    meta=m.actor_metadata(actor,world,client)
    assert meta['wheels'][0]['radius_cm_raw']==34
    assert meta['wheels'][0]['max_brake_torque_nm_raw']==1400
    assert meta['bounding_box']['location_local']['x']==10
    assert not meta['calibrated_vehicle_dynamics']
