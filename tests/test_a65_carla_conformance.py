"""A65 controlled falsification; no live simulator or uploaded-file path needed."""
import json,subprocess,sys
from pathlib import Path
from test_a64_smoke_and_handoff import one_smoke
from rampd_core.a65_carla_conformance import audit_brake_conformance

ROOT=Path(__file__).resolve().parents[1]

def synthetic_with_physics():
    d=one_smoke('brake')
    d['physics']['mass_kg_raw']=1845.
    d['physics']['wheels']=[{'radius_cm_raw':37.,'max_brake_torque_nm_raw':700.,'tire_friction_raw':3.5} for _ in range(4)]
    s=d['trials'][0]['samples']
    for i,x in enumerate(s):
        if i<=5:
            v=5.;acc=0.
        else:
            v=max(0., 5.-.15*(i-5));acc=-3. if v>0 else 0.
        x['planar_speed_mps']=x['speed_mps']=v
        x['signed_longitudinal_accel_mps2']=acc
        x['lane_audit'].update(available_halfwidth_m=1.75,required_halfwidth_m=1.18)
    return d

def test_nominal_trace_remains_uncertified():
    result=audit_brake_conformance(synthetic_with_physics())
    assert result['status'].endswith('NOT_CALIBRATED'),result
    assert not result['physical_certified'] and not result['safe_training_labels_allowed']
    assert not result['torque_only_comparison_is_certified_bound']

def test_synthetic_gross_braking_spike_rejected_even_when_capture_accepted():
    d=synthetic_with_physics();ss=d['trials'][0]['samples']
    for j in range(6,len(ss)):
        v=max(0.,5.-1.35*(j-5))
        ss[j]['planar_speed_mps']=ss[j]['speed_mps']=v
        ss[j]['signed_longitudinal_accel_mps2']=-27. if v>0 else 0.
    out=audit_brake_conformance(d)
    assert 'GROSS_TORQUE_ONLY_MODEL_DISCREPANCY' in out['reasons'],out
    assert out['max_speed_difference_deceleration_mps2']>20.
    assert not out['safe_training_labels_allowed']

def test_sensor_only_spike_does_not_fake_two_channel_discrepancy():
    d=synthetic_with_physics();d['trials'][0]['samples'][7]['signed_longitudinal_accel_mps2']=-27.
    out=audit_brake_conformance(d)
    assert 'GROSS_TORQUE_ONLY_MODEL_DISCREPANCY' not in out['reasons']
    assert 'SINGLE_FRAME_ACCEL_VELOCITY_MISMATCH' in out['reasons']
    assert not out['physical_certified']

def test_missing_wheel_metadata_and_units_fail_closed():
    d=synthetic_with_physics();d['physics']['wheels'][0]['radius_cm_raw']=0.37
    assert 'INVALID_TORQUE_OR_RADIUS_UNITS' in audit_brake_conformance(d)['reasons']
    d=synthetic_with_physics();d['physics']['mass_kg_raw']=0
    assert 'MISSING_MASS_OR_WHEEL_PHYSICS' in audit_brake_conformance(d)['reasons']

def test_nonbrake_and_unaccepted_capture_no_calibration():
    d=synthetic_with_physics();d['trials'][0]['maneuver']='steer'
    assert 'BRAKE_TRIAL_REQUIRED' in audit_brake_conformance(d)['reasons']
    d=synthetic_with_physics();d['trials'][0]['samples'][7]['lane_audit']['status']='REVIEW'
    assert 'SOURCE_SMOKE_CAPTURE_NOT_ACCEPTED' in audit_brake_conformance(d)['reasons']

def test_driver_requires_both_isolation_flags_even_in_smoke_mode():
    source=(ROOT/'scripts/a60_carla_actor_trials.py').read_text()
    assert "a.mode in ('capture','readiness','smoke','trials') and not a.confirm_isolated_world" in source
    assert "a.mode in ('readiness','smoke','trials') and not a.confirm_exclusive_tick" in source

def test_standalone_cli_review_does_not_clobber_existing_results(tmp_path):
    source=tmp_path/'in.json';output=tmp_path/'out.json'
    source.write_text(json.dumps(synthetic_with_physics()))
    cmd=[sys.executable,str(ROOT/'scripts/a65_review_carla_conformance.py'),
         '--input',str(source),'--output',str(output)]
    x=subprocess.run(cmd,capture_output=True,text=True)
    assert x.returncode==0,x.stderr
    y=json.loads(output.read_text());assert not y['actuator_calibrated']
    x=subprocess.run(cmd,capture_output=True,text=True)
    assert x.returncode!=0


def test_lane_status_without_numeric_clearance_does_not_pass_physical_gate():
    d=synthetic_with_physics()
    for s in d['trials'][0]['samples']:
        s['lane_audit'].pop('required_halfwidth_m')
    r=audit_brake_conformance(d)
    assert 'MISSING_NUMERIC_LANE_CLEARANCE_EVIDENCE' in r['reasons']
    assert not r['full_continuous_lane_safety_certified']
