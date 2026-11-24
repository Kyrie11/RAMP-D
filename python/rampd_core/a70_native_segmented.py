"""A70 actual MPFR/Picard *piecewise* propagation across a declared clock support.

This invokes the existing native validated integrator once per clock slab and
independently replays each certificate. The right-continuous clock partition
is reconstructed from the supplied worlds; public controls must be identical
(in value, not only string ID) within each observable-history group. The next
slab's initial box must enclose the entire preceding endpoint.

Only the 6D declared ego ODE with bounded derivative disturbances is proved.
Resource topology, other actors, real-world parameter support, complete hidden
worlds, observation semantics, and accepting SC tails are NOT verified here.
"""
from __future__ import annotations
from dataclasses import dataclass
from fractions import Fraction as Q
from hashlib import sha256
import json
from .a61_hybrid_partition import ClockWorld,partition_clock_worlds
from .exact_time import binary64_bracket
from .model import BicycleParameters,ControlBounds,StateBounds
from .interval import Interval
from .reachability import PicardOptions,integrate,TubeStatus
from .certificate import to_dict,replay_certificate
from .a5_replay_bridge import exact_step_endpoint

@dataclass(frozen=True)
class NativeSlabInput:
    world_id: str
    start: Q
    end: Q
    public_control_id: str
    state_start: StateBounds
    control: ControlBounds
    disturbance: tuple[Interval,...]
    def __post_init__(self):
        if not isinstance(self.world_id,str) or not self.world_id or not isinstance(self.public_control_id,str) or not self.public_control_id:
            raise ValueError('nonempty world and public control identity')
        if type(self.start) is not Q or type(self.end) is not Q or not 0<=self.start<self.end:
            raise ValueError('exact slab interval required')
        if not isinstance(self.state_start,StateBounds) or not isinstance(self.control,ControlBounds) or len(self.disturbance)!=6 or any(not isinstance(x,Interval) for x in self.disturbance):
            raise TypeError('typed ego physical contract required')


def clock_source_digest(worlds:tuple[ClockWorld,...],start:Q,end:Q,history_events=())->str:
    """Byte-stable model declaration binding, not a source-authority proof."""
    def event(e):
        return [e.event_id,e.kind,str(e.time),e.source_ref,e.correlated_id,e.domain]
    payload=dict(start=str(start),end=str(end),worlds=[
        dict(world_id=w.world_id,complete=w.declared_complete,
             public_history_id=w.public_history_id,
             public_tokens=sorted([list(x) for x in w.public_tokens]),
             events=sorted(event(e) for e in w.events))
        for w in sorted(worlds,key=lambda w:w.world_id)],
        history=sorted(event(e) for e in history_events))
    return sha256(json.dumps(payload,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()


def _control_value(c):
    return tuple((i.lo.hex(),i.hi.hex()) for i in c.as_tuple())


def replay_segmented_native(worlds:tuple[ClockWorld,...], inputs:tuple[NativeSlabInput,...], *,
                            start:Q,end:Q,params:BicycleParameters,
                            options:PicardOptions|None=None,history_events=(),
                            max_world_slabs:int=128):
    """Return (status report, independently replayed raw tube certificate dictionary).

    A valid result is explicitly *local/conditional*. It is never SafeTube or SC.
    """
    if not isinstance(params,BicycleParameters) or (options is not None and not isinstance(options,PicardOptions)):
        raise TypeError('physical model and solver options required')
    if type(max_world_slabs) is not int or not 1<=max_world_slabs<=100000:
        raise ValueError('finite complete-support budget required')
    worlds=tuple(worlds);inputs=tuple(inputs)
    clock_digest=clock_source_digest(worlds,start,end,history_events)
    if any(not isinstance(x,NativeSlabInput) for x in inputs):raise TypeError('typed NativeSlabInput required')
    clock=partition_clock_worlds(worlds,start=start,end=end,history_events=tuple(history_events))
    reasons=list(clock.reasons)
    expected={(w,lo,hi) for lo,hi,groups in clock.posterior_worlds_by_slab for _,ids in groups for w in ids}
    given={};names=set()
    if len(expected)>max_world_slabs:reasons.append('NATIVE_WORLD_SLAB_BUDGET_EXCEEDED')
    if not expected:reasons.append('EMPTY_HIDDEN_SUPPORT')
    for r in inputs:
        key=(r.world_id,r.start,r.end)
        if key in given:reasons.append('DUPLICATE_WORLD_SLAB')
        given[key]=r
        if r.world_id not in {w.world_id for w in worlds}:reasons.append('UNDECLARED_NATIVE_WORLD')
        names.add(r.public_control_id)
    if set(given)!=expected:reasons.append('MISSING_OR_EXTRA_NATIVE_WORLD_SLAB')
    # Fail closed before native work if the world/clock support is not valid.
    if reasons:
        return dict(schema='rampd.a70.segmented_native.v1',status='UNKNOWN',reasons=sorted(set(reasons)),
                    expected_world_slabs=len(expected),replayed_world_slabs=0,rows=[],
                    native_picard_subslabs_replayed=False,full_safe_tube=False,full_sc=False,
                    safe_training_labels_allowed=False),{}
    for lo,hi,groups in clock.posterior_worlds_by_slab:
        for history,ids in groups:
            src=[given[(w,lo,hi)] for w in ids]
            if len({r.public_control_id for r in src})>1 or len({_control_value(r.control) for r in src})>1:
                reasons.append('PUBLIC_NONANTICIPATIVITY_CONTROL_ID_OR_VALUE_MISMATCH')
    if reasons:
        return dict(schema='rampd.a70.segmented_native.v1',status='UNKNOWN',reasons=sorted(set(reasons)),
                    expected_world_slabs=len(expected),replayed_world_slabs=0,rows=[],
                    native_picard_subslabs_replayed=False,full_safe_tube=False,full_sc=False,
                    safe_training_labels_allowed=False),{}
    certs={};rows=[];prev={}
    for lo,hi,_ in clock.posterior_worlds_by_slab:
        for w in sorted({key[0] for key in expected if key[1]==lo and key[2]==hi}):
            key=w,lo,hi;r=given[key]
            if w in prev and not r.state_start.contains(prev[w]):
                reasons.append('NATIVE_HANDOFF_UNDERAPPROXIMATION:'+w+':'+str(lo))
                # Do not run a spuriously narrowed initial condition.
                continue
            dt=hi-lo
            try:
                h=binary64_bracket(dt)[1]
                tube=integrate(r.state_start,r.control,params,h,options,derivative_disturbance=r.disturbance)
                if tube.status is not TubeStatus.VALIDATED:
                    raise ValueError('NATIVE_UNKNOWN:'+tube.reason)
                obj=to_dict(tube)
                if not replay_certificate(obj).ok:
                    raise ValueError('NATIVE_CERTIFICATE_REPLAY_REJECTED')
                endpoint=exact_step_endpoint(tube,dt)
                raw=json.dumps(obj,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
                certs[key]=obj
                rows.append(dict(world=w,start=str(lo),end=str(hi),control=r.public_control_id,
                    control_values=_control_value(r.control),
                    certificate_sha256=sha256(raw).hexdigest(),
                    exact_requested_horizon=str(dt),native_enclosing_horizon=h,
                    validated_picard_steps=len(tube.segments),backend=tube.backend,
                    endpoint=[[v.lo,v.hi] for v in endpoint.as_tuple()],
                    local_native_replay=True))
                prev[w]=endpoint
            except (ValueError,RuntimeError,OverflowError,ArithmeticError) as exc:
                reasons.append('NATIVE_PROPAGATION_OR_REPLAY_UNKNOWN:'+w+':'+str(lo)+':'+str(exc))
    reasons=sorted(set(reasons))
    return dict(schema='rampd.a70.segmented_native.v1',
                status='CONDITIONAL_DECLARED_EGO_NATIVE_PICARD_SEGMENTED_REPLAY' if not reasons else 'UNKNOWN',
                reasons=reasons,expected_world_slabs=len(expected),replayed_world_slabs=len(rows),
                rows=rows,clock_slab_count=len(clock.slabs),
                clock_worlds_digest=clock_digest,clock_interval=[str(start),str(end)],
                public_history_groups=[[str(lo),str(hi),[[str(hist),list(ids)] for hist,ids in groups]]
                    for lo,hi,groups in clock.posterior_worlds_by_slab],
                native_picard_subslabs_replayed=(not reasons),
                # Every unimplemented obligation explicitly stays false.
                continuous_resource_geometry_verified=False,other_actor_support_verified=False,
                rule_authority_verified=False,complete_real_hidden_support_verified=False,
                observation_relation_verified=False,terminal_acceptance_tail_verified=False,
                real_vehicle_error_envelope_verified=False,full_safe_tube=False,full_sc=False,
                safe_training_labels_allowed=False),certs
