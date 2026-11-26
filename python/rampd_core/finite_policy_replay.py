"""Independent replay of an A73 finite translation-game candidate. No search,
no continuous bicycle claim, no authority claim. Uses exact same contact kernel.
"""
from itertools import combinations
from .finite_joint_reference import box,contact,safe_edge

def replay(model,policy,horizon):
    states=model['states']; roster=model['roster'];goal=box(model['goal']);ego=model['ego'];resources=model['resources'];conflicts=model['conflicts'];visited=0
    def check(node,B,remaining):
        nonlocal visited
        visited+=1
        if type(node['rank']) is not int or not 0<=node['rank']<=remaining or set(node['support'])!=B or len(node['support'])!=len(B):raise ValueError('rank or public support mismatch')
        if node['rank']==0:
            if node.get('terminal_goal_declared') is not True or 'action' in node or 'children' in node:raise ValueError('invalid terminal')
            for name in B:
                s=states[name];b=box(s['actors'][ego]);a=s['actors']
                if set(a)!=set(roster) or s['task_accept'] is not True or s['legal'] is not True or not(goal[0]<=b[0]<=b[2]<=goal[2] and goal[1]<=b[1]<=b[3]<=goal[3]):raise ValueError('task not accepted')
                if any(contact(a[x],a[x],a[y],a[y]) is not None for x,y in combinations(roster,2)) or any(contact(v,v,p,p) is not None for v in a.values() for p in resources.values()):raise ValueError('terminal not safe')
            return 0
        u=node['action'];children=node['children'];posterior={}
        if u not in model['actions']:raise ValueError('action not declared')
        for s in B:
            rows=model['edges'][s][u]
            if not rows:raise ValueError('missing transition')
            for r in rows:
                why,_=safe_edge(states[s],states[r['to']],resources,r['guards'],conflicts,roster)
                if why:raise ValueError('unsafe edge: '+str(why))
                if not r['observations']:raise ValueError('empty observation')
                for o in r['observations']:posterior.setdefault(o,set()).add(r['to'])
        if set(children)!=set(posterior):raise ValueError('missing or extra public branch')
        worst=1+max(check(children[o],b,node['rank']-1) for o,b in posterior.items())
        if worst!=node['rank']:raise ValueError('incorrect rank bound')
        return worst
    try:
        if type(horizon) is not int or not 0<=horizon<=20 or not model['initial']:raise ValueError('bad horizon or support')
        rank=check(policy,set(model['initial']),horizon)
        return dict(status='CONDITIONAL_FINITE_POLICY_REPLAY',rank=rank,nodes=visited,formal_labels_authorized=False)
    except (ValueError,TypeError,KeyError,AttributeError,OverflowError) as e:return dict(status='UNKNOWN',reason=str(e),formal_labels_authorized=False)
