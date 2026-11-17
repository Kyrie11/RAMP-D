"""Independent test oracle runs WITHOUT any MPFR / RAMPD shared object."""
import importlib.util
from fractions import Fraction as Q
from pathlib import Path
import random

p=Path(__file__).parents[1]/'python/rampd_core/finite_game_oracle.py'
spec=importlib.util.spec_from_file_location('rampd_finite_game_oracle',p)
mod=importlib.util.module_from_spec(spec)
import sys
sys.modules[spec.name]=mod
spec.loader.exec_module(mod)
FiniteGame=mod.FiniteGame


def test_distinguishability_is_required_for_contingent_branching():
    # Both histories share 'same', hence the parent must have ONE public child
    # that already covers the combined posterior. No hidden-state selection.
    g=FiniteGame(('P','G','bad'),frozenset({'P','G'}),frozenset({'G'}),
                 {'P': ((('same','G'),('other','bad')), )},Q(1,10),{'G': Q(7,10)})
    assert mod.forward_ranks(g,3)[0]=={'G':0}
    assert mod.recursive_winner(g,'P',3) is False


def test_strict_finite_completion_excludes_safe_wait():
    g=FiniteGame(('S','G'),frozenset({'S','G'}),frozenset({'G'}),
                 {'S': ((('seen','S'),), (('seen','G'),))},Q(1,10),{'G': Q(3,4)})
    ranks,times=mod.forward_ranks(g,5)
    assert ranks=={'G':0,'S':1}
    assert times['S']==Q(17,20)


def test_exact_rational_nonuniform_completion_bounds():
    g=FiniteGame(('A','B','C'),frozenset({'A','B','C'}),frozenset({'C'}),
                 {'A': ((('a','B'),),), 'B': ((('a','C'),),)},Q(1,10),{'C':Q(1,3)})
    ranks,times=mod.forward_ranks(g,4)
    assert ranks=={'C':0,'B':1,'A':2}
    assert times['A']==Q(8,15)


def test_randomized_and_or_game_oracle_independent_agreement():
    rng=random.Random(20261117)
    for trial in range(300):
        names=tuple('S'+str(i) for i in range(rng.randint(2,6)))
        safe=frozenset(s for s in names if rng.randrange(5)!=0)
        terminals=frozenset(s for s in safe if rng.randrange(4)==0)
        actions={}
        for s in names:
            candidates=[]
            for _ in range(rng.randrange(4)):
                candidates.append(tuple(('obs'+str(i),rng.choice(names))
                                        for i in range(rng.randint(1,3))))
            actions[s]=tuple(candidates)
        game=FiniteGame(names,safe,terminals,actions,Q(1,10),
                        {s:Q(1,4) for s in terminals})
        h=4
        rank,_=mod.forward_ranks(game,h)
        for s in names:
            assert (s in rank)==mod.recursive_winner(game,s,h), (trial,s)


def test_bad_graph_rejected():
    import pytest
    with pytest.raises(ValueError):
        FiniteGame(('A',),frozenset({'A'}),frozenset(),{'A':((('obs','Z'),),)},Q(1,10),{})
    with pytest.raises(ValueError):
        FiniteGame(('A',),frozenset({'A'}),frozenset(),{'A':((('obs','A'),('obs','A')), )},Q(1,10),{})
