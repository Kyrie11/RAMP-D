"""Safety-obligation audit BETWEEN A57 physical Post and SC.

A57 native_post itself supplies possible rule successors, NOT SafeTube. This
module independently checks every MPFR/Picard-replayed ego slab, actuator
limits, friction, all declared agent collision envelopes, and relevant resource
avoidance. It never shrinks the support using a learned prediction.

A pass is only a CONDITIONAL local collision/vehicle/resource *avoidance*
result for the complete declared actor roster; it is not an SC winning-state,
physical environment completeness, dynamic protocol, or task-tail certificate.
Unknown is preserved when the resource may be entered, as entry/exit topology
and incumbent permissions are not yet proven.
"""
from dataclasses import dataclass
from fractions import Fraction as Q
from .native_tick_guard import NativeParent, native_post
from .actor_response_envelope import propagate_other
from .model import BicycleParameters,ControlBounds,friction_value_enclosure
from .footprint import VehicleGeometry,SweptFootprint,separate_swept_footprints,SeparationStatus
from .resources import ResourceRegion,rectangular_separated
from .reachability import TubeStatus
from .interval import Interval
from .native_protocol_replay import _subslab_box

@dataclass(frozen=True)
class PhysicalLimits:
    speed_max:float
    accel_min:float
    accel_max:float
    steer_max_abs:float
    jerk_max_abs:float
    steer_rate_max_abs:float
    def __post_init__(self):
        import math
        v=(self.speed_max,self.accel_min,self.accel_max,self.steer_max_abs,
           self.jerk_max_abs,self.steer_rate_max_abs)
        if not all(math.isfinite(x) for x in v) or not (self.speed_max>0 and self.accel_min<0<self.accel_max and 0<self.steer_max_abs<1.5707963267948966 and self.jerk_max_abs>0 and self.steer_rate_max_abs>0):
            raise ValueError('explicit physical limits required')

@dataclass(frozen=True)
class ParentSafetyAudit:
    parent_id:str
    status:str
    reasons:tuple[str,...]
    slabs_checked:int
    pairs_proved_disjoint:int

@dataclass(frozen=True)
class GuardSafetyAudit:
    status:str
    parent_audits:tuple[ParentSafetyAudit,...]
    posterior_labels:tuple[str,...]
    # Intentional: this proof has not established task-winning or full model completeness
    safe_continuation_certified:bool=False
    task_complete:bool=False
    full_real_world_support_certified:bool=False


def _validate_control(control,limits,disturbance):
    # Bound the actual state derivatives, not merely the nominal command.
    # Bicycle state order is (x,y,psi,v,a,delta).
    actual_jerk=control.jerk+disturbance[4]
    actual_steer_rate=control.steering_rate+disturbance[5]
    return (max(abs(actual_jerk.lo),abs(actual_jerk.hi))<=limits.jerk_max_abs and
            max(abs(actual_steer_rate.lo),abs(actual_steer_rate.hi))<=limits.steer_rate_max_abs)


def audit_native_tubes(parents,tubes,control,*,params,ego_geometry,resource,limits,disturbance):
    """Independently test ALL included slab certificates, never test a sample.

    NOTE: The nominal physical limits are exact binary64-configured constants.
    Strict interval comparisons can only prove safety relative to these
    declared bounds. Vehicle-model completeness and sensor coverage remain
    explicit outside this function.
    """
    parents=tuple(parents)
    if (not parents or not all(isinstance(p,NativeParent) for p in parents) or
        len({p.atom.atom_id for p in parents})!=len(parents) or
        set(tubes)!={p.atom.atom_id for p in parents} or
        not isinstance(control,ControlBounds) or not isinstance(params,BicycleParameters) or
        not isinstance(ego_geometry,VehicleGeometry) or not isinstance(resource,ResourceRegion) or not isinstance(limits,PhysicalLimits) or
        len(disturbance)!=6 or not all(isinstance(w,Interval) for w in disturbance)):
        raise ValueError('complete and scoped physical Post evidence required')
    audits=[]
    for p in parents:
        tube=tubes[p.atom.atom_id]
        reasons=[];pairs=0;slabs=0
        if tube.status is not TubeStatus.VALIDATED:
            reasons.append('UNKNOWN_NATIVE_PROPAGATION')
        if (tube.initial!=p.atom.ego or tube.control!=control or tube.params!=params or
            tuple(tube.disturbance)!=tuple(disturbance)):
            reasons.append('PROOF_CONTEXT_MISMATCH')
        if not _validate_control(control,limits,disturbance):reasons.append('CONTROL_OR_DISTURBANCE_OUTSIDE_ACTUATOR_LIMITS')
        prev=Q(0)
        for seg in tube.segments:
            if seg.start_time!=prev or seg.end_time<=prev:
                reasons.append('TUBE_TIME_GAP_OR_OVERLAP')
            prev=seg.end_time
        if prev<p.controller.plan.tick:
            reasons.append('TUBE_DOES_NOT_COVER_TICK')
        for seg in tube.segments:
            lo,hi=seg.start_time,seg.end_time
            if hi>p.controller.plan.tick:hi=p.controller.plan.tick
            if lo>=hi:continue
            slabs+=1
            box=_subslab_box(seg,lo,hi)
            if not(0<=box.v.lo and box.v.hi<=limits.speed_max):reasons.append('UNKNOWN_SPEED_DOMAIN')
            if not(limits.accel_min<=box.a.lo and box.a.hi<=limits.accel_max):reasons.append('UNKNOWN_ACCEL_DOMAIN')
            if not(-limits.steer_max_abs<=box.delta.lo and box.delta.hi<=limits.steer_max_abs):reasons.append('UNKNOWN_STEERING_DOMAIN')
            if friction_value_enclosure(box,params).hi>1:reasons.append('UNKNOWN_FRICTION_FEASIBILITY')
            efp=SweptFootprint(box,ego_geometry,lo,hi,'ego')
            if not rectangular_separated(efp,resource):
                reasons.append('UNKNOWN_RESOURCE_ENTRY_EXIT_OR_PERMISSION')
            other=propagate_other(p.actor_models,p.atom,lo,hi)
            for actor in p.actor_models:
                afp=actor.footprint(other,lo,hi)
                collision=separate_swept_footprints(efp,afp)
                if collision.status is SeparationStatus.SEPARATED:pairs+=1
                else:reasons.append('UNKNOWN_EGO_ACTOR_COLLISION:'+actor.actor_id)
        if not slabs:reasons.append('MISSING_CONTINUOUS_SLAB')
        issues=tuple(sorted(set(reasons)))
        audits.append(ParentSafetyAudit(p.atom.atom_id,'CONDITIONAL_EGO_AVOIDANCE_PASS' if not issues else 'UNKNOWN',issues,slabs,pairs))
    return tuple(audits)


def guarded_physical_post(parents,control,*,params,ego_geometry,disturbance,resource,
                          queue_a,queue_b,limits,options=None,max_cases=100000):
    """Return Post with an explicit independent safety gate. NEVER equate Post
    generation with SafeTube or SC; on UNKNOWN, do not mark the control viable.
    """
    parents=tuple(parents)
    try:
        status,posterior,tubes=native_post(parents,control,params=params,ego_geometry=ego_geometry,
                              disturbance=disturbance,resource=resource,queue_a=queue_a,queue_b=queue_b,
                              options=options,max_cases=max_cases)
    except ValueError as exc:
        # Numerical replay or finite support-budget exhaustion is genuinely
        # unresolved, never a negative proof and never a partial successor set.
        # Invalid user/model contracts still raise instead of being hidden.
        why=str(exc)
        if not any(t in why for t in ('physical propagation/replay failed; UNKNOWN',
                                      'native guard budget exceeded; UNKNOWN',
                                      'guard support budget exceeded')):
            raise
        failure=tuple(ParentSafetyAudit(p.atom.atom_id,'UNKNOWN',
                           ('UNKNOWN_NATIVE_POST_OR_SUPPORT_BUDGET',),0,0) for p in parents)
        return 'UNKNOWN',{}, {},GuardSafetyAudit('UNKNOWN',failure,())
    audits=audit_native_tubes(parents,tubes,control,params=params,ego_geometry=ego_geometry,
                              resource=resource,limits=limits,disturbance=disturbance)
    safe=all(x.status=='CONDITIONAL_EGO_AVOIDANCE_PASS' for x in audits)
    out=GuardSafetyAudit('CONDITIONAL_EGO_AVOIDANCE_PASS' if safe else 'UNKNOWN',audits,tuple(sorted(posterior)))
    return status,posterior,tubes,out
