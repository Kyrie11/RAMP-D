"""Exact finite multi-actor reference game, independent of native dynamics.
A model is explicit: states, fixed roster, rectangular resource geometry, every
outcome of every action, observation relation, and accepting state predicate.
Constant velocity translation of fixed axis-aligned boxes ONLY. Continuous
sweeps are exact in time; this is not a CARLA/WOMD model or a full SC proof.
"""
from fractions import Fraction as Q
from itertools import combinations


def q(x):
    if type(x) not in (str,int,Q): raise ValueError('exact rational required')
    return Q(x)


def box(b):
    if len(b)!=4: raise ValueError('box [xmin,ymin,xmax,ymax]')
    a=tuple(map(q,b))
    if a[0]>=a[2] or a[1]>=a[3]: raise ValueError('degenerate box')
    return a


def contact(a,b,c,d):
    """Closed time interval in normalized [0,1] of overlap, including touch.
    a,b are initial/final actor boxes; c,d another translating rectangle.
    """
    a,b,c,d=map(box,(a,b,c,d)); lo,hi=Q(0),Q(1)
    for x,y in ((a,b),(c,d)):
        if x[2]-x[0]!=y[2]-y[0] or x[3]-x[1]!=y[3]-y[1]: raise ValueError('shape changed')
    for k in (0,1):
        for u,v in ((a[k+2]-c[k],b[k+2]-d[k]),(c[k+2]-a[k],d[k+2]-b[k])):
            slope=v-u
            if slope==0:
                if u<0:return None
            elif slope>0:lo=max(lo,-u/slope)
            else:hi=min(hi,-u/slope)
    return (lo,hi) if lo<=hi else None


def safe_edge(s,t,resources,guards,conflicts,roster):
    if set(s['actors'])!=set(roster) or set(t['actors'])!=set(roster): raise ValueError('actor roster mismatch')
    if set(guards)!=set(resources): raise ValueError('missing guard')
    reasons=[] if s['legal'] and t['legal'] else ['ILLEGAL_STATE']; occ={}; paths={a:(box(s['actors'][a]),box(t['actors'][a])) for a in roster}
    for a,b in combinations(roster,2):
        if contact(*paths[a],*paths[b]) is not None:reasons.append('COLLISION:'+a+':'+b)
    for r,p in resources.items():
        p=box(p); g=guards[r]; times={}
        if any(type(g[k]) is not bool for k in ('entry','stay','exit','ack')) or type(g['capacity']) is not int or g['capacity']<0 or not isinstance(g['directions'],list):raise ValueError('bad guard')
        if type(g['version']) is not int or g['version']<0 or type(g['ack_version']) is not int:raise ValueError('bad version')
        for a,(b,c) in paths.items():
            span=contact(b,c,p,p)
            if span is None:continue
            times[a]=span;lo,hi=span
            dx=c[0]-b[0]; dy=c[1]-b[1]; direction='east' if dx>0 else 'west' if dx<0 else 'stationary'
            strict_start=all(b[k]<p[k+2] and p[k]<b[k+2] for k in (0,1))
            if (dy!=0 or not g['ack'] or g['ack_version']!=g['version'] or not g['stay'] or direction not in g['directions'] or ((lo>0 or not strict_start) and not g['entry']) or (hi<1 and not g['exit'])):reasons.append('GUARD:'+r+':'+a)
        for x in {x for span in times.values() for x in span}:
            if sum(lo<=x<=hi for lo,hi in times.values())>g['capacity']:reasons.append('CAPACITY:'+r)
        occ[r]=times
    for r,p in conflicts:
        if r==p or r not in resources or p not in resources:raise ValueError('bad conflict')
        for a,(lo,hi) in occ[r].items():
            for b,(l,h) in occ[p].items():
                if a!=b and max(lo,l)<=min(hi,h):reasons.append('RESOURCE_CONFLICT:'+r+':'+p)
    return sorted(set(reasons)),{r:{a:[str(l),str(h)] for a,(l,h) in v.items()} for r,v in occ.items()}


def solve(model, horizon, budget=10000):
    """Enumerate common actions and union all successors per observation BEFORE recursion.
    Finite outcome table is a declared model, not an inferred complete protocol.
    Reject malformed/missing state-action rows. No global negative labels.
    """
    if type(horizon) is not int or not 0<=horizon<=20 or type(budget) is not int or budget<1:raise ValueError('invalid horizon/budget')
    states=model['states'];actions=model['actions'];roster=model['roster'];resources=model['resources'];conflicts=model['conflicts']; initial=frozenset(model['initial']);goal=box(model['goal']);ego=model['ego']; edges=model['edges']
    if not states or not actions or not roster or not initial or not initial<=set(states) or ego not in roster or len(set(roster))!=len(roster) or len(set(actions))!=len(actions):raise ValueError('invalid model support')
    for name,s in states.items():
        if set(s['actors'])!=set(roster) or type(s['task_accept']) is not bool or type(s['legal']) is not bool:raise ValueError('state metadata')
        for b in s['actors'].values():box(b)
        if set(edges[name])!=set(actions):raise ValueError('incomplete action table')
        for a,rows in edges[name].items():
            if not rows:raise ValueError('empty outcome table')
            for row in rows:
                if row['to'] not in states or not row['observations'] or not all(type(o) is str and o for o in row['observations']):raise ValueError('incomplete observation/outcome relation')
    if set(edges)!=set(states):raise ValueError('extra state rows')
    memo={}; checks=[]; visited=0
    def accepting(s):
        b=box(s['actors'][ego]);return not any(contact(v,v,p,p) is not None for v in s['actors'].values() for p in resources.values()) and s['task_accept'] and s['legal'] and goal[0]<=b[0]<=b[2]<=goal[2] and goal[1]<=b[1]<=b[3]<=goal[3]
    def rec(B,k):
        nonlocal visited
        key=(B,k)
        if key in memo:return memo[key]
        visited+=1
        if visited>budget:raise RuntimeError('BUDGET')
        # Goal only accepted if every state safe at endpoint (including other actors).
        if all(accepting(states[s]) and not any(contact(box(states[s]['actors'][a]),box(states[s]['actors'][a]),box(states[s]['actors'][b]),box(states[s]['actors'][b])) is not None for a,b in combinations(roster,2)) for s in B):
            return {'rank':0,'support':sorted(B),'terminal_goal_declared':True}
        if k==0:return None
        for a in actions:
            posterior={};bad=False
            for s in sorted(B):
                for row in edges[s][a]:
                    t=row['to']; why,occ=safe_edge(states[s],states[t],resources,row['guards'],conflicts,roster)
                    checks.append(dict(state=s,action=a,to=t,reasons=why,occupancy=occ))
                    if why:bad=True
                    for o in row['observations']:posterior.setdefault(o,set()).add(t)
            if bad:continue
            children={o:rec(frozenset(v),k-1) for o,v in sorted(posterior.items())}
            if all(c is not None for c in children.values()):
                result={'rank':1+max(c['rank'] for c in children.values()),'support':sorted(B),'action':a,'children':children};memo[key]=result;return result
        memo[key]=None;return None
    try:policy=rec(initial,horizon);status='CONDITIONAL_FINITE_TRANSLATION_WIN' if policy else 'NO_WINNING_POLICY_IN_DECLARED_TABLE'
    except RuntimeError:policy=None;status='UNKNOWN_BUDGET'
    return dict(status=status,policy=policy,edge_checks=checks,visited=visited,complete_external_protocol=False,native_6d=False,formal_labels_authorized=False)
