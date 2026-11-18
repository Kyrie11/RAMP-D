import csv,json,zipfile
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from audit_wzdx_inputs import audit

def write(p,rows):
    with p.open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)

def test_flattened_event_rows_are_not_certified_events(tmp_path):
    r=tmp_path/'registry.csv';e=tmp_path/'events.csv';z=tmp_path/'schema.zip'
    write(r,[dict(state='texas',feedName='test',version='4.2',active='true')])
    row=dict(vehicle_impact='all-lanes-closed',start_date='2026-01-01T00:00:00Z',end_date='2026-01-02T00:00:00Z',core_details='{"event_type":"work-zone"}',line='LINESTRING (-97 30,-97 31)',location_method='junction-method',is_start_date_verified='false',is_end_date_verified='false',is_start_position_verified='false',is_end_position_verified='false')
    write(e,[row,row]);d={'definitions':{'VehicleImpact':{'enum':['all-lanes-closed']},'EventType':{'enum':['work-zone']}}}
    with zipfile.ZipFile(z,'w') as f:f.writestr('fixture/schemas/4.2/RoadEventFeature.json',json.dumps(d))
    o=audit(r,e,z);assert o['status']=='BOUNDED_CSV_INVENTORY_PASS' and o['event_rows']==2 and not o['unique_event_count_known'] and not o['authoritative_rule_time_labels_generated']
    write(e,[dict(row,vehicle_impact='invented',end_date='2020-01-01T00:00:00Z')]);o=audit(r,e,z);assert o['status']=='NOT_PASSED' and o['issues']=={'unknown_vehicle_impact':1,'reversed_date_interval':1}
