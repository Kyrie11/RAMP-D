from fractions import Fraction as Q
from dataclasses import replace
import pytest
from rampd_core.a53_schedule import PermissionEpoch,PermissionSchedule,local_protocol
from rampd_core.protocol import ProtocolAutomaton,ProtocolState,ProtocolTransition,ClockTrace,TimeWindow,CausalStage


def schedule():
    a=PermissionEpoch('lane',Q(10),Q(101,10),True,True,'forward',2,'external-plan')
    b=PermissionEpoch('lane',Q(101,10),Q(11),False,True,'forward',1,'external-plan')
    return PermissionSchedule(Q(10),Q(51,5),('lane',),(a,b))


def test_closed_step_boundary_matches_half_open_epochs():
    s=schedule()
    assert s.restrictions(Q(10),Q(201,20))['lane']==(True,True,'forward',2)
    assert s.restrictions(Q(10),Q(101,10))['lane']==(False,True,'forward',1)
    assert s.restrictions(Q(101,10),Q(51,5))['lane']==(False,True,'forward',1)
    assert s.digest!=replace(s,epochs=(s.epochs[0],replace(s.epochs[1],beta=False))).digest


@pytest.mark.parametrize('kind',['gap','overlap','end','missing','duplicate','float'])
def test_schedule_invalid(kind):
    s=schedule(); a,b=s.epochs
    with pytest.raises(ValueError):
        if kind=='gap': replace(s,epochs=(a,replace(b,on=b.on+Q(1,100))))
        elif kind=='overlap': replace(s,epochs=(a,replace(b,on=b.on-Q(1,100))))
        elif kind=='end': replace(s,epochs=(a,replace(b,off=s.deadline)))
        elif kind=='missing': replace(s,resource_ids=('lane','uncovered'))
        elif kind=='duplicate': replace(s,epochs=(a,b,b))
        else: replace(a,on=10.)


def test_direction_change_cannot_invent_common_direction():
    s=schedule(); a,b=s.epochs
    s=replace(s,epochs=(a,replace(b,direction='reverse')))
    assert s.restrictions(Q(10),Q(101,10))['lane'][2]=='NO_COMMON_DIRECTION'
    with pytest.raises(ValueError): s.restrictions(Q(10),Q(11))


def proto():
    def edge(e,src,dst,start,end):
        return ProtocolTransition(e,src,dst,(('ext',CausalStage.EXTERNAL),),
          ClockTrace(TimeWindow(start,end),local=TimeWindow(end,end)), 'silence',silence=True,guard_tag='always')
    return ProtocolAutomaton(tuple(ProtocolState(x) for x in ('s','h1','h2','end')),'s',(
        edge('a','s','h1',Q(10),Q(101,10)),edge('b','s','h2',Q(10),Q(101,10)),
        edge('c','h1','end',Q(101,10),Q(51,5)),edge('d','h2','end',Q(101,10),Q(51,5))))


def test_absolute_protocol_preserves_all_same_observation_hidden_branches():
    p=proto(); l=local_protocol(p,('s',),Q(10),Q(101,10),'problem')
    assert {t.transition_id for t in l.outgoing('s')}=={'a','b'}
    assert all(t.clocks.local.hi==Q(1,10) for t in l.transitions)
    other=local_protocol(p,('h1','h2'),Q(101,10),Q(51,5),'problem')
    assert {t.transition_id for t in other.transitions}=={'c','d'} and other.digest()!=l.digest()


@pytest.mark.parametrize('kind',['reset','missing','guard','late','hidden','monitor','messages'])
def test_absolute_protocol_fails_closed_on_unmodelled_cases(kind):
    p=proto(); start,end=Q(10),Q(101,10); modes=('s',)
    if kind=='reset': start,end=Q(0),Q(1,10)
    elif kind=='missing': modes=('end',)
    elif kind=='guard': p=replace(p,transitions=(replace(p.transitions[0],guard_tag='unknown'),*p.transitions[1:]))
    elif kind=='late':
        t=p.transitions[0]; p=replace(p,transitions=(replace(t,clocks=replace(t.clocks,local=TimeWindow(Q(11),Q(11)))),*p.transitions[1:]))
    else:
        field={'hidden':'mode','monitor':'resource_monitor','messages':'received_messages'}[kind]
        state=replace(p.states[0],**{field:(('msg',1),) if kind=='messages' else (('r','closed'),)})
        p=replace(p,states=(state,*p.states[1:]))
    with pytest.raises((ValueError,KeyError)): local_protocol(p,modes,start,end,'problem')


def test_partition_checks_terminal_rule_and_all_hidden_branches():
    from rampd_core.a53_schedule import partition_family
    s=schedule(); a,b=s.epochs
    alternative=replace(s,epochs=(replace(a,alpha=False),replace(b,direction='reverse')))
    rows=s.partition(Q(10),Q(51,5))
    assert [(x,y) for x,y,_ in rows]==[(Q(10),Q(101,10)),(Q(101,10),Q(51,5)),(Q(51,5),Q(51,5))]
    assert rows[0][2]['lane']==(True,True,'forward',2)
    assert rows[-1][2]['lane']==(False,True,'forward',1)
    merged=partition_family((s,alternative),Q(10),Q(51,5))
    assert merged[0][2]['lane']==(False,True,'forward',2)
    assert merged[-1][2]['lane']==(False,True,'NO_COMMON_DIRECTION',1)
    with pytest.raises(ValueError): partition_family((),Q(10),Q(51,5))
