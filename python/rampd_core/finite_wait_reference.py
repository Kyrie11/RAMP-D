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


def analytic_step(s,u):
    """Independent scalar intersection ledger for this specific finite game.
    No calls to contact(), monitor() or step(). The exact admissible edge
    convention matches step(), including conservative start-of-slab permission.
    Not a general rectangle monitor or a Native certificate.
    """
    opening,t,x,prior,age=s
    if u not in ACTIONS or t>=20:return None
    dx=int(u=='GO');nx=x+dx
    def interval(a,b,lo,hi):
        # a+b*lambda in [lo,hi], 0<=lambda<=1, b in {0,1}
        if not b:return (Q(0),Q(1)) if lo<=a<=hi else None
        l=max(Q(0),Q(lo-a));h=min(Q(1),Q(hi-a));return (l,h) if l<=h else None
    def overlap(a,b):return a is not None and b is not None and max(a[0],b[0])<=min(a[1],b[1])
    if overlap(interval(x,dx,2,4),interval(t,1,2,4)):return None
    spans={k:v for k,v in {'ego':interval(x,dx,1,4),'other':interval(t,1,1,4)}.items() if v is not None}
    dirs={'ego':'A','other':'B'};old=dict(prior)
    if set(old)!={k for k,v in spans.items() if v[0]==0} or any(old[k]!=dirs[k] for k in old):return None
    if 'ego' in spans and 'ego' not in old and t<opening:return None
    if any(any(d!=dirs[k] for d in old.values()) for k in spans if k not in old):return None
    if overlap(spans.get('ego'),spans.get('other')):return None
    ends={k:dirs[k] for k,v in spans.items() if v[1]==1}
    next_age=Q(0) if ends else 1-max(v[1] for v in spans.values()) if spans else age+1
    return ('GREEN' if t+1>=opening+1 else 'SILENCE'),(opening,t+1,nx,tuple(sorted(ends.items())),next_age)


def finite_teacher(openings=(5,7),horizon=14):
    """Exhaustive AND/OR finite reference labels, checked by analytic_step.
    Viability is exact ONLY for the declared WAIT/GO model and finite budget.
    The forced-WAIT bound is not the paper's branch decision deferral deadline.
    No margin, ICG or full formal-head training authorization.
    """
    if not openings or len(set(openings))!=len(openings) or any(type(o) is not int or not 1<=o<=19 for o in openings) or type(horizon) is not int or not 0<=horizon<=20:raise ValueError('finite teacher context')
    root=frozenset((o,0,0,(),Q(0)) for o in openings);checked=set()
    def children(B,u):
        out={};safe=True
        for s in B:
            a=analytic_step(s,u);b=step(s,u);checked.add((s,u))
            if a!=b:raise ValueError('independent finite transition disagreement')
            if a is None:safe=False;continue
            o,c=a;out.setdefault(o,set()).add(c)
        return tuple(frozenset(v) for v in out.values()) if safe else ()
    @lru_cache(None)
    def rank(B,h,wait):
        if all(terminal(s) for s in B):return 0 if wait==0 else None
        if h==0:return None
        result=[]
        for u in ('WAIT',) if wait else ACTIONS:
            groups=children(B,u)
            if not groups:continue
            values=[rank(c,h-1,max(0,wait-1)) for c in groups]
            if all(v is not None for v in values):result.append(1+max(values))
        return min(result) if result else None
    rows=[]
    for h in range(horizon+1):
        r=rank(root,h,0);B,p=synthesize(openings,h)
        if r!=(None if p is None else replay(B,p,h)):raise ValueError('rank oracle disagreement')
        waits=[w for w in range(h+1) if rank(root,h,w) is not None] if r is not None else []
        rows.append(dict(horizon=h,viable=r is not None,rank=r,forced_wait_ticks_max=max(waits) if waits else None,finite_negative_complete=r is None))
    return dict(scope='EXACT_FINITE_WAIT_GO_REFERENCE_ONLY',openings=list(openings),rows=rows,analytic_edges_checked=len(checked),formal_sc=False,training_allowed=False,deadline_is_not_ICG=True)


def finite_criticality(openings=(5,7),horizon=14):
    """Exact leave-one-world action/continuation impact on reachable beliefs.
    Only for this enumerated WAIT/GO game; not a probability estimator, geometric
    ranker, native SC teacher, or formal ICG deadline. No learning authorization.
    """
    if len(openings)<2 or len(set(openings))!=len(openings) or any(type(o) is not int or not 1<=o<=19 for o in openings) or type(horizon) is not int or not 1<=horizon<=20:raise ValueError('finite criticality context')
    checked=set();root=frozenset((o,0,0,(),Q(0)) for o in openings)
    def children(B,u):
        out={};safe=True
        for s in B:
            a=analytic_step(s,u);b=step(s,u);checked.add((s,u))
            if a!=b:raise ValueError('independent finite transition disagreement')
            if a is None:safe=False;continue
            o,c=a;out.setdefault(o,set()).add(c)
        return {o:frozenset(v) for o,v in out.items()} if safe else {}
    @lru_cache(None)
    def rank(B,h):
        if all(terminal(s) for s in B):return 0
        if h<=0:return None
        r=actions(B,h);return min(r.values()) if r else None
    @lru_cache(None)
    def actions(B,h):
        if h<=0 or all(terminal(s) for s in B):return {}
        r={}
        for u in ACTIONS:
            c=children(B,u)
            if c:
                v=[rank(q,h-1) for q in c.values()]
                if all(x is not None for x in v):r[u]=1+max(v)
        return r
    pending=[(root,horizon,())];visited=set();rows=[]
    while pending:
        B,h,prefix=pending.pop(0)
        if (B,h) in visited:continue
        visited.add((B,h));full=actions(B,h);fr=rank(B,h)
        if len(B)>1 and h>0 and not all(terminal(s) for s in B):
            impacts=[]
            for opening in sorted({s[0] for s in B}):
                reduced=frozenset(s for s in B if s[0]!=opening)
                if not reduced:continue
                alt=actions(reduced,h);rr=rank(reduced,h)
                impacts.append(dict(removed_opening=opening,added_viable_actions=sorted(set(alt)-set(full)),removed_viable_actions=sorted(set(full)-set(alt)),viability_changes=(rr is None)!=(fr is None),rank_before=fr,rank_after=rr,critical=alt!=full or rr!=fr))
            rows.append(dict(t=horizon-h,x=next(iter(B))[2],remaining=h,prefix=list(prefix),hidden_openings=sorted({s[0] for s in B}),viable_actions=full,rank=fr,impacts=impacts))
        if h>0 and not all(terminal(s) for s in B):
            for u in ACTIONS:
                for o,c in children(B,u).items():pending.append((c,h-1,prefix+((u,o),)))
    return dict(scope='EXACT_FINITE_WAIT_GO_LEAVE_ONE_WORLD_ONLY',openings=list(openings),horizon=horizon,rows=rows,beliefs_checked=len(visited),analytic_edges_checked=len(checked),critical_beliefs=sum(any(i['critical'] for i in r['impacts']) for r in rows),formal_sc=False,training_allowed=False,deadline_is_not_ICG=True)
