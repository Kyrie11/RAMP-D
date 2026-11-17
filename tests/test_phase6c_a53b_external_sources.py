import importlib.util
from pathlib import Path
import pytest
s=importlib.util.spec_from_file_location('source_audit',Path(__file__).resolve().parents[1]/'scripts/audit_external_rule_sources.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m)

def test_verified_dates_are_not_physical_or_receipt_labels():
    d={'type':'FeatureCollection','features':[{'id':'a','properties':{'core_details':{'event_type':'work-zone'},'start_date':'2025-01-01T00:00:00Z','end_date':'2025-01-01T01:00:00Z','is_start_date_verified':True,'is_end_date_verified':True}}]}
    r=m.wzdx_summary(d);assert r['verified_declared_durations_s']==[3600] and not r['physical_onset_label'] and not r['ego_receipt_label']
    d['features'][0]['properties']['is_end_date_verified']=False;assert m.wzdx_summary(d)['verified_declared_durations_s']==[]

def test_duplicate_ids_and_bad_links_rejected():
    d={'type':'FeatureCollection','features':[{'id':'a'},{'id':'a'}]};assert m.wzdx_summary(d)['errors']
    c={'images':[{'id':1}],'categories':[{'id':2,'name':'cone'}],'annotations':[{'id':3,'image_id':1,'category_id':2}]};assert m.coco_summary(c)['annotations']==1
    c['annotations'][0]['image_id']=9
    with pytest.raises(ValueError):m.coco_summary(c)
