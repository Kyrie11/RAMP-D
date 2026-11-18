"""Native-only declared moving-agent envelopes and posterior continuity."""
from fractions import Fraction as Q
from dataclasses import replace
from rampd_core.interval import Interval
from rampd_core.a53b_actor_envelope import ActorEnvelope,propagate_other
from rampd_core.footprint import VehicleGeometry
from rampd_core.a5_replay_bridge import A5PhysicalObligation,a5_world_digest,replay_a5_physical
from rampd_core.invariant import EvidenceContext
from rampd_core.resources import ResourceState,ResourceRegion
from rampd_core.a53_mission import audit_a53_mission
from rampd_core.safe_continuation import sc_support_digest
from test_phase6c_a5_bridge import fixture,_rebind
from test_phase6c_a53_mission import example


def model(name='car',acc=Interval(-1,1)):
    return ActorEnvelope(name,VehicleGeometry(4,2),acc,Interval.point(0),Interval.point(0),'declared fixture')

def initial(m,x=15.,vx=1.):return tuple(zip(m.keys,map(Interval.point,(x,0.,vx,0.,0.))))

def test_acceleration_enclosure_contains_analytic_extremes():
    m=model();d=dict(initial(m));b=m.enclosure(d,Q(1,10),Q(1,3))
    for t in (Q(1,10),Q(1,5),Q(1,3)):
        for a in (-1,1):
            for i,val in ((0,15+t+a*t*t/2),(2,1+a*t)):
                v=b[m.keys[i]];assert Q.from_float(v.lo)<=val<=Q.from_float(v.hi)

def test_full_mission_actor_state_inherited_and_missing_support_rejected():
    mission,root,nodes,finish=example();m=model();w=replace(mission.world,actor_models=(m,));w=replace(w,model_digest=a5_world_digest(w))
    source={root.atoms[0].atom_id:initial(m)};root=replace(root,atoms=tuple(replace(a,other=source[a.atom_id]) for a in root.atoms))
    mission=replace(mission,world=w,initial_support_digest=sc_support_digest(root))
    rebuilt=[]
    for n in sorted(nodes,key=lambda n:n.depth):
        cell=replace(n.cell,atoms=tuple(replace(a,other=source[a.atom_id]) for a in n.cell.atoms))
        if n.action_id is None:rebuilt.append(replace(n,cell=cell));continue
        c,_,_=mission.edge_context(cell,n.depth)
        obligations=tuple(A5PhysicalObligation.seal(o.cell_id,o.action_id,o.source_atom_id,o.tube,c) for o in n.obligations)
        refs={o.source_atom_id:o.evidence_ref for o in obligations};atoms={a.atom_id:a for a in cell.atoms}
        def post(a,sid):
            other=tuple(propagate_other((m,),atoms[sid],mission.step,mission.step).items());source[a.atom_id]=other
            return replace(a,other=other)
        outcomes=tuple(replace(o,successors=tuple(post(a,o.source_atom_id) for a in o.successors)) for o in n.outcomes)
        act=cell.actions[0];trs=tuple(replace(t,evidence_ref=refs[t.source_atom_id],branches=tuple(replace(b,atoms=tuple(replace(a,other=source[a.atom_id]) for a in b.atoms)) for b in t.branches)) for t in act.transitions)
        rebuilt.append(replace(n,cell=replace(cell,actions=(replace(act,transitions=trs),)),obligations=obligations,outcomes=outcomes))
    root=rebuilt[0].cell;r=audit_a53_mission(mission,root,rebuilt,finish);assert r.ok,r.reason
    # Reset another agent at a later node – must not be accepted.
    n=rebuilt[1];bad=replace(n,cell=replace(n.cell,atoms=tuple(replace(a,other=initial(m)) for a in n.cell.atoms)))
    assert not audit_a53_mission(mission,root,(rebuilt[0],bad,*rebuilt[2:]),finish).ok
    n=rebuilt[-1];bad=replace(n,cell=replace(n.cell,atoms=tuple(replace(a,other=()) for a in n.cell.atoms)))
    assert not audit_a53_mission(mission,root,(*rebuilt[:-1],bad),finish).ok


def edge(x=15.,vx=1.,capacity=None,second=False,bad_endpoint=False):
    c,p,obs,cell,action,out,ob,ctx,w,safe=fixture();m=model();models=(m,);other=initial(m,x,vx)
    if second:
        m2=model('car2');models+=(m2,);other+=initial(m2,x+1.,vx)
    src=replace(ctx.source_atom,other=other)
    vals=tuple(propagate_other(models,src,c.step_s,c.step_s).items())
    if bad_endpoint:vals=other
    dst=replace(out.successors[0],other=vals)
    tr=replace(ctx.transition,branches=(replace(ctx.transition.branches[0],atoms=(dst,)),))
    a=replace(action,transitions=(tr,));ce=replace(cell,atoms=(src,),actions=(a,));ctx=EvidenceContext(ce,src,a,tr)
    states=();regions=();axes=()
    if capacity is not None:
        states=(ResourceState('lane',True,True,'forward',capacity),);regions=(ResourceRegion('lane',Interval(-5,30),Interval(-5,5),capacity),);axes=(('lane',1.,0.),)
    w=replace(w,actor_models=models,regions=regions,resource_states=states,resource_forward_axes=axes,timed_resource_slices=((Q(0),c.step_s,states),(c.step_s,c.step_s,states)))
    return _rebind(c,ob,ctx,w),safe

def test_pairwise_collision_capacity_and_endpoint_are_independent():
    for opts,expected in (({},True),({'x':1.},False),({'capacity':1},False),({'capacity':2},True),({'bad_endpoint':True},False),({'second':True},False),({'capacity':2,'vx':-1.},False)):
        (c,ob,ctx,w),safe=edge(**opts);assert replay_a5_physical(ctx,c,ob,w,safe)==expected,opts
