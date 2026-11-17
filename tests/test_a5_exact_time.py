import importlib.util
from pathlib import Path
from fractions import Fraction as Q
import math
import pytest
spec=importlib.util.spec_from_file_location('a5_exact_time',Path(__file__).resolve().parents[1]/'python/rampd_core/exact_time.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

@pytest.mark.parametrize('q',[Q(1,10),Q(1,3),Q(1,8),Q(7,10),Q(1,2**1075),Q(0),Q(1000001,3)])
def test_exact_outward_adjacent_binary64(q):
    lo,hi=m.binary64_bracket(q)
    assert Q.from_float(lo)<=q<=Q.from_float(hi)
    assert lo==hi or math.nextafter(lo,math.inf)==hi
    if lo!=hi: assert Q.from_float(lo)<q<Q.from_float(hi)

@pytest.mark.parametrize('q',[.1,Q(-1),True,Q(10**400)])
def test_invalid_time(q):
    with pytest.raises((ValueError,OverflowError)):m.binary64_bracket(q)
