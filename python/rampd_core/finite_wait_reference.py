"""Integrated finite reference for waiting, hidden opening time, resource
monitor, public successor union and persistent rank. Not Native 6D.
The complete model is generated, not arbitrary state/action edges supplied by
candidate. Each step is one time unit, ego moves 0 or 1; other crosses vertical
resource before opening. Public observation is delivered one full step after physical opening;
GO requires opening at the start of a decision step (conservative admission).
"""
from fractions import Fraction as Q
from functools import lru_cache
from .finite_joint_reference import contact
from .affine_resource_monitor import monitor
R=(2,0,4,2)
ACTIONS=('WAIT','GO')
# (hidden opening time, absolute time, ego x, admitted roster tuple, empty_age)
def b(x,y):return (x,y,x+1,y+1)
def other(t):return b(3,3-t) # enters at 2? at t=1 touches y=2; leaves after t=4

def step(s,u):
    opening,t,x,prior,age=s
    if u not in ACTIONS or t>=20:return None
    nx=x+(u=='GO');ego=(b(x,0),b(nx,0));o=(other(t),other(t+1))
    if contact(*ego,*o) is not None:return None
    old=dict(prior)
    # Before opening ego cannot contact resource. The other has prior clearance.
    ego_span=contact(*ego,R,R)
    if ego_span is not None and 'ego' not in old and t<opening:return None
    g=dict(entry=True,stay=True,exit=True,ack=True,capacity=1,directions=['A','B'])
    r=monitor({'ego':ego,'other':o},R,old,{'ego':'A','other':'B'},g,dt=1,empty_age=age)
    if not r['ok']:return None
    child=(opening,t+1,nx,tuple(sorted(r['end_admitted'].items())),r['empty_age'])
    obs='GREEN' if t+1>=opening+1 else 'SILENCE'
    return obs,child

def terminal(s):return s[2]>=5 and not s[3]
def successors(B,u):
    out={}
    for s in B:
        v=step(s,u)
        if v is None:return None
        o,c=v;out.setdefault(o,set()).add(c)
    return {o:frozenset(v) for o,v in out.items()}

def synthesize(openings=(5,7),horizon=14):
    root=frozenset((o,0,0,(),Q(0)) for o in openings)
    if not root or type(horizon) is not int or not 0<=horizon<=20:raise ValueError('context')
    @lru_cache(None)
    def solve(B,k):
        if all(map(terminal,B)):return {'rank':0,'terminal':True}
        if k==0:return None
        best=None
        for u in ACTIONS:
            out=successors(B,u)
            if not out:continue
            children={o:solve(c,k-1) for o,c in out.items()}
            if any(v is None for v in children.values()):continue
            candidate={'rank':1+max(v['rank'] for v in children.values()),'action':u,'children':children}
            if best is None or candidate['rank']<best['rank']:best=candidate
        return best
    return root,solve(root,horizon)

def replay(B,p,budget):
    # Recompute transition model at every branch; require strict inherited rank.
    if not B or not p or type(p.get('rank')) is not int or not 0<=p['rank']<=budget:raise ValueError('rank/support')
    if p['rank']==0:
        if p!={'rank':0,'terminal':True} or not all(map(terminal,B)):raise ValueError('false acceptance')
        return 0
    out=successors(B,p['action'])
    if not out or set(out)!=set(p['children']):raise ValueError('incomplete/unsafe branch')
    n=1+max(replay(c,p['children'][o],p['rank']-1) for o,c in out.items())
    if n!=p['rank']:raise ValueError('rank not tight')
    return n

def replan(B,old,replacement):
    # Called after actual control & observation: old is the inherited child.
    replay(B,old,old['rank']);replay(B,replacement,old['rank']);return replacement
