"""Conditional multi-actor Native Post -> public successor support gate.
Declared outcomes are external model inputs, not evidence of protocol completeness.
This gate does not authorize SC, even if all enclosures and targets match.
"""
from fractions import Fraction as Q
from .native_certificate_context import exact_endpoint, bounds, contains


def merge_endpoint_support(certs, outcomes, targets, roster, *, end):
    """outcomes: world -> nonempty list of {observation, atom, latent}.
    targets: observation -> atom -> {latent, actors:{actor: six interval box}}.
    Exact union of IDs, latent state equality, enclosure of each joint outcome.
    Distinct worlds must have distinct atom IDs (no accidental loss of correlation).
    All inputs are independent declared model/abstraction, not inferred from certs.
    """
    if type(end) is not Q or not roster or len(set(roster)) != len(roster) or set(certs)!=set(roster):
        raise ValueError('independent roster mismatch')
    worlds={k[0] for k in certs[roster[0]] if k[2]==end}
    if not worlds or worlds!=set(outcomes):raise ValueError('outcome world coverage')
    unions={}; atom_world={}
    for w in sorted(worlds):
        endpoint={}
        for a in roster:
            rows=[(k,c) for k,c in certs[a].items() if k[0]==w and k[2]==end]
            if len(rows)!=1:raise ValueError('missing/duplicate endpoint')
            k,c=rows[0];endpoint[a]=exact_endpoint(c,k[2]-k[1])
        if not outcomes[w]:raise ValueError('empty observation relation')
        for row in outcomes[w]:
            o,i,latent=(row[k] for k in ('observation','atom','latent'))
            if not all(isinstance(v,str) and v for v in (o,i,latent)):raise ValueError('invalid outcome identity')
            if i in atom_world and atom_world[i]!=(w,latent):raise ValueError('cross-world atom alias')
            atom_world[i]=(w,latent)
            t=unions.setdefault(o,{})
            if i in t:raise ValueError('duplicate observation outcome')
            t[i]={'latent':latent,'actors':endpoint}
    if set(targets)!=set(unions):raise ValueError('public observation coverage')
    for o,items in unions.items():
        if set(items)!=set(targets[o]):raise ValueError('posterior atom union mismatch')
        for i,row in items.items():
            dst=targets[o][i]
            if row['latent']!=dst['latent'] or set(dst['actors'])!=set(roster):raise ValueError('latent state or roster mismatch')
            for a,b in row['actors'].items():
                if not contains(bounds(dst['actors'][a]),b):raise ValueError('endpoint undercoverage')
    return {o:sorted(items) for o,items in sorted(unions.items())}


def audit_native_successors(certs,declarations,geometry,resources,guards,conflicts,worlds,*,start,end,ego,roster,outcomes,targets,history_events=()):
    from .native_multi_actor_screen import audit_joint_native
    try:
        if set(roster)!=set(certs) or len(set(roster))!=len(roster):raise ValueError('independent roster mismatch')
        # A shared box alone does not establish a single executable ego action.
        for c in certs[ego].values():
            if any(lo!=hi for lo,hi in c['control']):raise ValueError('non-point ego control unsupported')
        r=audit_joint_native(certs,declarations,geometry,resources,guards,conflicts,worlds,start=start,end=end,ego=ego,history_events=history_events)
        if not r['status'].startswith('CONDITIONAL'):raise ValueError('upstream screen: '+str(r['reasons']))
        # Same public clock history cannot be split by an invented observation token.
        from .a61_hybrid_partition import partition_clock_worlds
        clock=partition_clock_worlds(tuple(worlds),start=start,end=end,history_events=tuple(history_events))
        groups={w for _,ids in clock.posterior_worlds for w in ids}
        if groups!=set(outcomes):raise ValueError('clock world mismatch')
        # Here the only supported observation is the exact declared public history.
        for sig,ids in clock.posterior_worlds:
            label=history_label(sig)
            for w in ids:
                if not outcomes[w] or {v['observation'] for v in outcomes[w]}!={label}:raise ValueError('observation not bound to clock history')
        unions=merge_endpoint_support(certs,outcomes,targets,roster,end=end)
        return dict(status='CONDITIONAL_DECLARED_NATIVE_POST_SUPPORT',successors=unions,screen=r,formal_labels_authorized=False,full_sc=False)
    except (KeyError,TypeError,ValueError,RuntimeError,OverflowError,ZeroDivisionError) as e:
        return dict(status='UNKNOWN',reason=str(e),formal_labels_authorized=False,full_sc=False)


def history_label(sig):
    import json
    return json.dumps([[str(t),o] for t,o in sig],ensure_ascii=False,separators=(',',':'))
