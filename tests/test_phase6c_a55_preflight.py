import importlib.util,math,sys,csv
from pathlib import Path
from zoneinfo import ZoneInfo
from fractions import Fraction as Q
import pytest
from rampd_core.a55_motion import forward_arc
from rampd_core.a54_signal import SignalPlan,SignalController
from rampd_core.a53_rule_models import FlowSnapshot
from rampd_core.a53b_interlock import ClearanceObservation

ROOT=Path(__file__).resolve().parents[1]
def load(name):
    spec=importlib.util.spec_from_file_location(name,ROOT/'scripts'/f'{name}.py');m=importlib.util.module_from_spec(spec);sys.modules[name]=m;spec.loader.exec_module(m);return m


def test_forward_stop_exact_not_backward():
    assert forward_arc(0,0,0,.1,-3,0,.1)==pytest.approx((1/600,0,0,0,0))
    assert forward_arc(2,3,1,0,-3,.1,.1)==pytest.approx((2,3,1,0,0))
    assert forward_arc(0,0,0,0,2,0,.1)==pytest.approx((.01,0,0,.2,0))

@pytest.mark.parametrize('k',[-.2,0.,1e-14,.1])
def test_arc_split_consistency(k):
    p=forward_arc(0,0,.3,10,-2,k,.5)
    first=forward_arc(0,0,.3,10,-2,k,.25)
    second=forward_arc(*first[:3],math.hypot(*first[3:]),-2,k,.25)
    assert second==pytest.approx(p,abs=1e-12)


def test_bad_motion():
    with pytest.raises(ValueError):forward_arc(0,0,0,-1,0,0,.1)
    with pytest.raises(ValueError):forward_arc(0,0,0,1,0,0,0)


def test_511_daylight_saving_and_explicit_offset():
    m=load('audit_511ny');z=ZoneInfo('America/New_York')
    assert m.parse_time('2024-11-03T01:30:00',z)[1]=='ambiguous_or_nonexistent_local'
    assert m.parse_time('2024-03-10T02:30:00',z)[1]=='ambiguous_or_nonexistent_local'
    assert m.parse_time('2024-11-03T01:30:00-04:00',z)[1]=='ok'
    assert m.parse_time('06/13/2022 04:31:36 AM',z)[1]=='ok'


def test_511_streaming_scope(tmp_path):
    m=load('audit_511ny');path=tmp_path/'a.csv'
    fields=['Event Type','Organization Name','State','Create Time','Close Time','Facility Name','Latitude','Longitude']
    def row(typ='disabled vehicle',agency='NYSDOT',state='NY',start='2024-01-01T00:00:00',end='2024-01-01T00:10:00'):
        return [typ,agency,state,start,end,'I-95','40.0','-73.0']
    with path.open('w',newline='') as f:
        w=csv.writer(f);w.writerow(fields);w.writerows([row(),row(end=''),row(end='2023-01-01T00:00:00'),row(agency='NJ Transit Rail'),row(state='NJ'),row(typ='Construction'),row(start='1969-12-31T19:00:00'),row(end='2024-01-01T00:00:00')])
    r=m.audit(path);p=r['groups']['breakdown'];assert r['counts']['rows']==8 and r['counts']['ny_road_agency_proxy']==6
    assert p['lifetime_lt_900s']==1 and p['negative_lifetime']==1 and p['close_missing']==1 and p['pre2010_timestamp']==1 and p['zero_lifetime']==1
    assert not r['unique_incidents_known'] and not r['physical_clearance_labels_generated']
    assert m.audit(path,limit=2)['counts']['rows']==2


def test_route_sweep_rear_boundary_and_transient_crossing():
    m=load('probe_sumo_alternating');V=m.Vehicle;bounds={'A':(20,30),'B':(20,30)}
    old={'a':V('A',32,4,2),'b':V('B',19,4,2)};new={'a':V('A',34,4,2),'b':V('B',36,4,2)}
    occ,ent=m.swept_occupants(old,new,bounds,[],[])
    assert occ=={'A':{'a'},'B':{'b'}} and ent=={'A':set(),'B':{'b'}}
    occ,_=m.swept_occupants(new,{'a':V('A',35,4,2),'b':V('B',37,4,2)},bounds,[],[])
    assert occ['A']=={'a'} and occ['B']==set() # exact rear contact


def test_sweep_birth_exit_and_roster_errors():
    m=load('probe_sumo_alternating');V=m.Vehicle;b={'A':(20,30),'B':(20,30)}
    assert m.swept_occupants({}, {'a':V('A',4,4,0)},b,['a'],[])[0]=={'A':set(),'B':set()}
    assert m.swept_occupants({'a':V('A',40,4,2)}, {},b,[],['a'])[0]=={'A':set(),'B':set()}
    with pytest.raises(ValueError,match='roster'):m.swept_occupants({}, {'a':V('A',4,4,0)},b,[],[])
    with pytest.raises(ValueError,match='nonmonotone'):m.swept_occupants({'a':V('A',40,4,2)},{'a':V('A',39,4,2)},b,[],[])


def test_closed_loop_clearance_cannot_use_prior_yellow():
    p=SignalPlan(Q(1),Q(1),Q(2),Q(1),Q(1),Q(2),1,'fixture')
    c=SignalController.initial('x',1,'r',p)
    def tick(s,occupied):
        t=s.last_tick+1
        return s.advance(FlowSnapshot(t,0,2,int(occupied)),ClearanceObservation(t-1,t,True,not occupied,'fixture','x',1,'r'))
    c=tick(c,False);assert c.phase=='A_YELLOW'
    c=tick(c,False);assert c.phase=='A_RED_CLEAR'
    c=tick(c,False);assert c.phase=='A_RED_CLEAR'
    c=tick(c,True);assert c.empty_since is None
    c=tick(c,False);assert c.phase=='A_RED_CLEAR'
    c=tick(c,False);assert c.phase=='B_GREEN'


def test_roadwork_suffix_cannot_select_other_split():
    m=load('audit_roadwork')
    from types import SimpleNamespace as S
    idx={'x.jpg':[S(filename='images/val/x.jpg'),S(filename='images/train/x.jpg')]}
    with pytest.raises(ValueError,match='contrary split'):m.member_for_image(idx,'val/x.jpg','train')
    assert m.member_for_image(idx,'x.jpg','train').filename=='images/train/x.jpg'
    with pytest.raises(ValueError):m.member_for_image({'x.jpg':[S(filename='images/train/val/x.jpg')]},'x.jpg','train')
