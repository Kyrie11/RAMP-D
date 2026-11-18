from fractions import Fraction as Q
from dataclasses import replace
import pytest
from rampd_core.record_adapters import _av2_endpoint_metadata,parse_av2_rows,RecordParseError
from rampd_core.a53b_incident import IncidentEvent,IncidentTimeline,IncidentRuleRecord
from rampd_core.a53b_ttc import merging_taper_m
from test_phase6b_record_adapters import _av2_rows
from test_phase6c_a53b_interlock import advance, pending
from rampd_core.a53b_interlock import ClearanceObservation,advance_interlock


def test_legacy_binary64_ns_relative_time_and_precision():
    original=1_700_000_000_000_000_123
    a=float(original);b=float(original+200_000_000)
    rows=_av2_rows()
    for r in rows: r.update(start_timestamp=a,end_timestamp=b)
    m=parse_av2_rows(rows).scene.manifest
    assert m.timestamps==(0.,.1,.2)
    assert m.metadata['time_axis_source']=='scenario_binary64_ns_relative_interpolation'
    precision=m.metadata['source_endpoint_precision'];assert not precision['original_ns_exact']
    assert precision['start']['stored_hex']==a.hex()
    lo,hi=map(Q,precision['start']['round_to_nearest_cell_ns']);assert lo<=original<=hi
    assert m.metadata['source_timestamps_start_ns']==int(a)!=original

@pytest.mark.parametrize('x',[float('nan'),float('inf'),-1.,1.5,float(2**63)])
def test_invalid_double_endpoint(x):
    with pytest.raises(RecordParseError): _av2_endpoint_metadata(x,'start_timestamp')

def test_partial_endpoint_not_silent_nominal_fallback():
    rows=_av2_rows()
    for r in rows: del r['end_timestamp']
    with pytest.raises(RecordParseError,match='pair incomplete'): parse_av2_rows(rows)

def test_exact_native_integer_precision_not_degraded():
    x=1700000000000000123
    assert _av2_endpoint_metadata(x,'start')[1]['original_ns_exact']


def event(cause='EXOGENOUS_TRIGGER'):
    return IncidentEvent('incident','DISABLED_VEHICLE',cause,Q(1),('lane',),'fault model','seed key')

def timeline():
    return IncidentTimeline(event(),Q(20),hazard_on=Q(2),first_authority_awareness=Q(4),verification=Q(6),dispatch=Q(7),responder_arrival=Q(10),blocked_lane_physically_clear=Q(13),lanes_available=Q(14),last_responder_left=Q(15),normal_flow=Q(18),evidence_ref='fixture')

def test_tim_durations_and_causal_scope():
    t=timeline();assert t.duration('lanes_available')==10 and t.duration('last_responder_left')==11
    assert t.incident.external_signature() and event('TRAFFIC_DEPENDENT').external_signature() is None
    assert replace(t,normal_flow=None).duration('normal_flow') is None

def test_physical_and_formal_clocks_distinct():
    t=timeline();r=IncidentRuleRecord('incident','lane','DOT','test area',1,Q(5),Q(14),Q(4),Q(8),Q(3),False,True,'fixture')
    assert r.audit(t)
    with pytest.raises(ValueError): replace(r,receipt=Q(2))
    with pytest.raises(ValueError): replace(r,effective_on=Q(3)).audit(t)
    with pytest.raises(ValueError): replace(r,resource_id='wrong').audit(t)
    with pytest.raises(ValueError): replace(t,blocked_lane_physically_clear=None)
    with pytest.raises(ValueError): replace(t,blocked_lane_physically_clear=Q(16))

def test_mismatched_clearance_evidence_rejected():
    e,s=pending();o=ClearanceObservation(s.last_tick,s.last_tick+1,True,True,'fixture',s.event_id,s.version,'another lane')
    with pytest.raises(ValueError,match='scope mismatch'): advance_interlock(e,s,o,tick=Q(1),clearance=Q(2))

def test_taper_units_and_table_gap():
    assert merging_taper_m(Q('3.6'),Q(30))==54
    assert merging_taper_m(Q('3.6'),Q(45))==162
    with pytest.raises(ValueError): merging_taper_m(Q('3.6'),Q(42))
