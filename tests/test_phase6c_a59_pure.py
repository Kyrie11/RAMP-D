"""A59/0 forensic and summary soundness tests; no native backend needed."""
import io
import json
import pytest
from rampd_core.a58_sumo_audit import audit_runs
from rampd_core.a59_sumo_forensics import audit_trace


def tiny_streams():
    net='<net>' + ''.join(f'<edge id="{kind}{d}"><lane id="{kind}{d}_0" length="{length}"/></edge>'
         for d in 'AB' for kind,length in (('in',1),('mid',2),('out',2))) + '</net>'
    rows=[(.1,.6,0),(.2,1.4,1),(.3,3.6,2)]
    vehicles=[dict(time_s=t,id='a0',direction='A',front_m=x,speed_mps=v,length_m=.5)
             for t,x,v in rows]
    roster=[{'time_s':.1,'departed':['a0'],'arrived':[]},
            {'time_s':.2,'departed':[],'arrived':[]},
            {'time_s':.3,'departed':[],'arrived':[]},
            {'time_s':.4,'departed':[],'arrived':['a0']}]
    summary=dict(status='SUMO_LOGICAL_CORRIDOR_PASS',seed=17,traffic_profile='baseline',
                 scope='TRAFFIC_ACTUATED_LOGICAL_CORRIDOR_NOT_PHYSICAL_SINGLE_LANE',
                 stop_reserve_guard=True,drained_at_cutoff=True,transitions=[],brake_steps=[],
                 roster_completion_pass=True,violations=[],comfort_review_required=False,
                 departed_count=1,arrived_count=1,
                 unique_entries={'A':1,'B':0},rear_clearances={'A':1,'B':0})
    return net,vehicles,roster,summary


def audit_fixture(*,change=None,log='',summary=True):
    net,vehicles,roster,r=tiny_streams()
    if change:change(vehicles,roster,r)
    data=lambda x:io.BytesIO((''.join(json.dumps(row)+'\n' for row in x)).encode())
    return audit_trace(net,data(vehicles),data(roster),log,profile='baseline',seed=17,
                       summary=r if summary else None)


def test_trace_independently_replays_roster_and_geometry():
    a=audit_fixture()
    assert a['status']=='LOGICAL_TRACE_REPLAY_MATCH_WITH_DECLARED_SUMMARY'
    assert a['frames']==4 and a['departed']==a['arrived']==1
    assert a['entered']==a['cleared']=={'A':1,'B':0}
    assert not a['valid_full_runtime_certificate'] and not a['training_labels_authorized']


def test_trace_missing_summary_never_recovered_as_full_pass():
    r=audit_fixture(summary=False)
    assert r['status']=='REVIEW' and 'MISSING_VALID_CONTROLS_SUMMARY' in r['reasons']


def test_trace_roster_tampering_fails_closed():
    def change(vehicles,roster,r):roster[0]['departed']=[]
    assert 'ROSTER_DELTA_MISMATCH' in audit_fixture(change=change)['reasons']


def test_trace_nonmonotone_reference_point_fails_closed():
    def change(vehicles,roster,r):vehicles[2]['front_m']=1.1
    assert 'NONMONOTONE_OR_MUTATED_ACTOR' in audit_fixture(change=change)['reasons']


def test_trace_log_warning_even_with_good_summary_must_review():
    assert 'SIMULATOR_WARNING_OR_ERROR_REVIEW' in audit_fixture(log='Warning: vehicle emergency brake')['reasons']


def test_malformed_summary_cannot_pass_by_default(tmp_path):
    r=dict(status='REVIEW_REQUIRED',scope='TRAFFIC_ACTUATED_LOGICAL_CORRIDOR_NOT_PHYSICAL_SINGLE_LANE',
           traffic_profile='dense',seed=17,expected_vehicles=1,departed_count=1,arrived_count=1,
           roster_completion_pass=True,drained_at_cutoff=True,transitions=[],violations=[],
           brake_steps=[],comfort_review_required=False,stop_reserve_guard=True)
    p=tmp_path/'r.json';p.write_text(json.dumps(r))
    assert audit_runs([p],expected_profile='dense',require_stop_reserve=True)['status']=='REVIEW'
    r['status']='SUMO_LOGICAL_CORRIDOR_PASS';del r['brake_steps']
    p.write_text(json.dumps(r))
    assert audit_runs([p],expected_profile='dense',require_stop_reserve=True)['status']=='REVIEW'
    r['brake_steps']=[];r['stop_reserve_guard']=False
    p.write_text(json.dumps(r))
    assert 'REQUIRED_STOP_RESERVE_CONTROL_NOT_VERIFIED' in audit_runs([p],expected_profile='dense',require_stop_reserve=True)['runs'][0]['reasons']


def test_mixed_profiles_fail_even_with_positive_reports(tmp_path):
    paths=[]
    for seed,profile in [(17,'dense'),(23,'slow_reaction')]:
        r=dict(status='SUMO_LOGICAL_CORRIDOR_PASS',scope='TRAFFIC_ACTUATED_LOGICAL_CORRIDOR_NOT_PHYSICAL_SINGLE_LANE',
            traffic_profile=profile,seed=seed,expected_vehicles=1,departed_count=1,arrived_count=1,
            roster_completion_pass=True,drained_at_cutoff=True,transitions=[],violations=[],
            brake_steps=[],comfort_review_required=False,stop_reserve_guard=True)
        p=tmp_path/f'{seed}.json';p.write_text(json.dumps(r));paths.append(p)
    assert audit_runs(paths,require_stop_reserve=True)['status']=='REVIEW'


def test_sumo_probe_never_clobbers_existing_successful_report(tmp_path):
    import subprocess,sys
    from pathlib import Path
    script=Path(__file__).resolve().parents[1]/'scripts'/'probe_sumo_alternating.py'
    report=tmp_path/'existing.json';original='{"status":"SUMO_LOGICAL_CORRIDOR_PASS","unique":"preserve"}\n'
    report.write_text(original)
    result=subprocess.run([sys.executable,str(script),'--work',str(tmp_path/'dirty'),
                           '--output',str(report)],capture_output=True,text=True)
    assert result.returncode != 0 and 'EXISTING_SUMO_REPORT_PRESERVED' in result.stderr
    assert report.read_text()==original


def test_carla_readonly_metadata_includes_actual_wheel_brake_torque_fields():
    import importlib.util
    from pathlib import Path
    from types import SimpleNamespace as NS
    script=Path(__file__).resolve().parents[1]/'scripts'/'dump_a58_carla_vehicle_params.py'
    spec=importlib.util.spec_from_file_location('carla_probe_math_test',script)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    wheel=NS(position=NS(x=144,y=80,z=0),radius=35,max_steer_angle=32,
             tire_friction=1.0,max_brake_torque=1900,max_handbrake_torque=600)
    row=module.wheel_metadata(wheel)
    assert row['max_brake_torque_nm_raw']==1900
    assert row['max_handbrake_torque_nm_raw']==600
    assert row['position_raw']['x']==144
    assert module.optional_curve(NS(steering_curve=[NS(x=0,y=1),NS(x=80,y=.4)]))[1]['speed_kmh_raw']==80
    # Unprovided fields must remain explicitly unknown, never 1500 Nm defaults.
    assert module.wheel_metadata(NS(position=wheel.position,radius=35,max_steer_angle=32,tire_friction=1))['max_brake_torque_nm_raw'] is None


def test_forged_or_partial_archive_cannot_be_all_report_pass(tmp_path):
    from zipfile import ZipFile
    from rampd_core.a59_sumo_forensics import audit_a58_archive
    net,vehicles,roster,summary=tiny_streams()
    zpath=tmp_path/'partial_a58.zip'
    with ZipFile(zpath,'w') as z:
        prefix='a58/sumo_baseline_17/'
        z.writestr(prefix+'network.xml',net)
        for filename,rows in [('vehicle_trace.jsonl',vehicles),('roster_trace.jsonl',roster)]:
            z.writestr(prefix+filename,''.join(json.dumps(x)+'\n' for x in rows))
        z.writestr(prefix+'sumo.log','')
        z.writestr('a58/sumo_baseline_17.json',json.dumps(summary))
    report=audit_a58_archive(zpath)
    assert report['status']=='REVIEW'
    assert report['complete_summary_and_trace_replays']==1
    assert 'MISSING_OR_UNEXPECTED_PROFILE_SEED' in report['inventory_errors']


def test_sumo_summary_missing_transitions_or_guard_is_review():
    def change(vehicles,roster,r):
        r.pop('transitions')
    assert 'REPORT_DECLARED_REVIEW_OR_MISSING_CONTROL_FIELDS' in audit_fixture(change=change)['reasons']
