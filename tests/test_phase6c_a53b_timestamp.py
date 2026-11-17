from rampd_core.record_adapters import _timestamp_ticks_to_ns,RecordParseError,_integer_ns
import pytest

@pytest.mark.parametrize('unit,scale',[('s',10**9),('ms',10**6),('us',10**3),('ns',1)])
def test_units_exact(unit,scale):
    assert _timestamp_ticks_to_ns([123,-123,None],unit)==[123*scale,-123*scale,None]

def test_never_round_large_nanosecond_values():
    raw=1_700_000_000_000_000_123
    assert _timestamp_ticks_to_ns([raw,raw+1],'ns')==[raw,raw+1]
    assert _integer_ns(raw,'start')==raw
    with pytest.raises(RecordParseError): _integer_ns(float(raw),'start')
    with pytest.raises(RecordParseError): _timestamp_ticks_to_ns([2**63-1],'ms')
    with pytest.raises(RecordParseError): _timestamp_ticks_to_ns([True],'ns')
