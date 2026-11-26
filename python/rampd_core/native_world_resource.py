"""A72 bind actual Native certificate replay to an independently reconstructed
hidden-world clock partition and a declared polygon resource family.

Passing this gate DOES NOT certify SC, physical authority, complete actor
support, dynamic polygons, or accepting mission tails. It is a sound scope
check for a narrow modeled exclusion claim only.
"""
from __future__ import annotations
from fractions import Fraction as Q
from .a61_hybrid_partition import partition_clock_worlds,ClockWorld
from .segmented_native_post import clock_source_digest
from .native_polygon_geometry import audit_native_polygon_resources


def audit_clock_bound_polygon_exclusion(report, certs, worlds, polygons, *,
                                        start, end, length_m, width_m,
                                        offset_x_m=0, offset_y_m=0,
                                        history_events=(), physical_declarations=None):
    reasons=[]
    if not isinstance(start,Q) or not isinstance(end,Q) or not start<end:
        raise ValueError('exact observation horizon required')
    worlds=tuple(worlds);history_events=tuple(history_events)
    if not worlds or any(not isinstance(w,ClockWorld) for w in worlds):
        raise ValueError('explicit finite hidden worlds required')
    partition=partition_clock_worlds(worlds,start=start,end=end,history_events=history_events)
    reasons.extend(partition.reasons)
    expected={(w,lo,hi) for lo,hi,groups in partition.posterior_worlds_by_slab
              for _,ids in groups for w in ids}
    declared={(r.get('world'),Q(r.get('start')),Q(r.get('end')))
              for r in report.get('rows',[])}
    if expected!=declared or set(certs)!=expected:
        reasons.append('INDEPENDENT_CLOCK_PARTITION_OR_WORLD_SUPPORT_MISMATCH')
    if report.get('clock_worlds_digest')!=clock_source_digest(worlds,start,end,history_events):
        reasons.append('CLOCK_EVENT_DECLARATION_BYTES_CHANGED')
    if report.get('clock_interval')!=[str(start),str(end)]:
        reasons.append('HORIZON_DECLARATION_CHANGED')
    if report.get('status')!='CONDITIONAL_DECLARED_EGO_NATIVE_PICARD_SEGMENTED_REPLAY':
        reasons.append('NATIVE_REPORT_NOT_REPLAYED')
    # An unrelated valid tube must not authorize this time/control/initial context.
    from .native_certificate_context import audit_context
    if physical_declarations is None:
        reasons.append('INDEPENDENT_PHYSICAL_CONTEXT_REQUIRED')
    elif not reasons:
        reasons.extend(audit_context(certs,physical_declarations))
    # Do not let an incomplete partition authorize any polygon conclusion.
    geometry=None
    if not reasons:
        geometry=audit_native_polygon_resources(report,certs,polygons,length_m=length_m,
                    width_m=width_m,offset_x_m=offset_x_m,offset_y_m=offset_y_m)
        reasons.extend(geometry['reasons'])
    return dict(schema='rampd.a72.native_clock_polygon.v1',
        status='CONDITIONAL_DECLARED_POLYGON_EXCLUSION' if not reasons else 'UNKNOWN',
        reasons=sorted(set(reasons)),independent_world_slabs=len(expected),
        geometry=geometry,native_certificate_replay_attempted=(geometry is not None),
        native_certificate_replay_passed=(geometry is not None and not any(
            'INVALID_NATIVE' in r or 'MALFORMED_NATIVE' in r or 'EMPTY_NATIVE' in r for r in geometry['reasons'])),
        hidden_world_clock_identity_checked=not any('CLOCK_' in x or 'SUPPORT_' in x for x in reasons),
        physically_authoritative_map=False,all_traffic_participant_tubes_complete=False,
        guard_enter_stay_exit_proved=False,public_observation_complete=False,
        terminal_accepting_tail_verified=False,sc_certified=False,
        safe_training_labels_allowed=False)
