import importlib.util
from pathlib import Path
from copy import deepcopy
spec=importlib.util.spec_from_file_location('audit_quality',Path(__file__).resolve().parents[1]/'scripts/audit_supervision_quality.py')
mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)

def fixture():
    row=dict(scenario_id='s1',raw_record_or_file_sha256='h1',valid_actor_time_knots=2,joint_target_knots_with_box_dimensions=2,source_file='a',actor_count=1,auxiliary_signal_change_brackets=0,status='LOGGED_EGO_PATH_SURROGATE')
    return {'records_requested_per_split':1,'groups':[{'dataset':ds,'split':split,'status':'PASS','records':[dict(row,scenario_id=ds+split,raw_record_or_file_sha256=ds+split)]} for ds,split in [('WOMD','training'),('WOMD','validation'),('AV2','train'),('AV2','validation')]]}

def test_valid_and_invalid_counts():
    f=fixture();assert mod.audit(f)['status']=='BOUNDED_INVENTORY_PASS'
    f['groups'][0]['records'][0]['joint_target_knots_with_box_dimensions']=3
    assert mod.audit(f)['status']=='NOT_PASSED'

def test_detect_overlap_and_missing_group():
    f=fixture();f['groups'][1]['records']=deepcopy(f['groups'][0]['records'])
    assert mod.audit(f)['status']=='NOT_PASSED'
    f['groups'][1]['records']=[];f['groups'][1]['status']='ERROR';assert mod.audit(f)['status']=='NOT_PASSED'

def test_old_waymax_clock_not_accepted():
    assert mod.audit(fixture(),{'initial_timestep':0,'next_timestep':1})['status']=='NOT_PASSED'
