import json
from pathlib import Path
from rampd_core.a66_evidence_inventory import inventory_single_control_inputs
S=Path(__file__).parent/'fixtures'/'a66_town06_steer_raw.json'

def test_missing_combined_and_brake_never_inferred_from_steer():
    source=json.loads(S.read_text())
    r=inventory_single_control_inputs({'brake':None,'steer':source,'combined':None})
    assert r['trials']['steer']['descriptive_capture'] is True
    assert r['trials']['combined']['status']=='MISSING'
    assert r['all_three_control_cases_present'] is False
    assert r['all_eight_supervision_sources_certified'] is False

def test_wrong_control_kind_cannot_fill_combined_slot():
    source=json.loads(S.read_text())
    r=inventory_single_control_inputs({'brake':None,'steer':source,'combined':source})
    assert r['trials']['combined']['status']=='REVIEW'
    assert 'WRONG_CONTROL_KIND_FOR_INVENTORY_SLOT' in r['trials']['combined']['reasons']

def test_absent_malformed_inputs_fail_closed():
    r=inventory_single_control_inputs({'brake':123,'steer':None,'combined':None})
    assert r['trials']['brake']['status']=='REVIEW'
    assert r['trials']['steer']['status']=='MISSING'

def test_scope_inventory_is_explicit():
    import pytest
    with pytest.raises(ValueError):inventory_single_control_inputs({'steer':None})
