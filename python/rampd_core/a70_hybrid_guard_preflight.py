"""A70 necessary conditions for Native-verified 6D ego tubes near a 1D resource.

Native certificate bytes are replayed again and are bound to the same
world/time/control manifest. The x-projection of every six-dimensional
Picard tube is compared with an OUTER resource projection; an intersection
is only MAY occupancy. Endpoint rosters and sampled Guard alone never prove
continuous enter/stay/exit. Fail closed when any MAY intersection occurs.

This is NOT a general polygon/resource verifier or an SC certificate.
"""
from __future__ import annotations
from dataclasses import dataclass
from fractions import Fraction as Q
import hashlib,json
from .certificate import replay_certificate
from .a61_hybrid_partition import ClockWorld
from .a70_native_segmented import clock_source_digest

@dataclass(frozen=True)
class AtSlabStartPermission:
    world_id: str
    start: Q
    end: Q
    entry_open: bool
    stay_open: bool
    exit_open: bool
    command_version: int
    ack_version: int|None
    initial_occupants: tuple[tuple[str,str], ...]
    capacity: int = 1
    allowed_directions: tuple[str,...] = ('A',)
    def __post_init__(self):
        if not self.world_id or type(self.start) is not Q or type(self.end) is not Q or not self.start<self.end:
            raise ValueError('world and positive exact slab required')
        if any(type(x) is not bool for x in (self.entry_open,self.stay_open,self.exit_open)):
            raise TypeError('typed guard permissions required')
        if type(self.command_version) is not int or self.command_version<0 or (self.ack_version is not None and (type(self.ack_version) is not int or self.ack_version<0)):
            raise ValueError('command/ACK versions required')
        if type(self.initial_occupants) is not tuple or any(type(x) is not tuple or len(x)!=2 or not x[0] or x[1] not in ('A','B') for x in self.initial_occupants):
            raise ValueError('explicit complete start-of-slab actor direction roster required')
        if len({a for a,_ in self.initial_occupants})!=len(self.initial_occupants):
            raise ValueError('unique start-of-slab roster required')
        if type(self.capacity) is not int or self.capacity<1 or not self.allowed_directions or any(d not in ('A','B') for d in self.allowed_directions):
            raise ValueError('valid capacity and declared directions required')


def audit_native_guard_projection(native_report:dict,native_certificates:dict,worlds:tuple[ClockWorld,...],
                                  permissions:tuple[AtSlabStartPermission,...], *,
                                  resource_x_lo:Q,resource_x_hi:Q,ego_half_length:Q,
                                  actor_roster_physically_complete:bool=False,
                                  controller_authority_physically_attested:bool=False,
                                  history_events=())->dict:
    if any(type(x) is not Q for x in (resource_x_lo,resource_x_hi,ego_half_length)) or resource_x_lo>=resource_x_hi or ego_half_length<=0:
        raise ValueError('exact resource projection and ego geometry required')
    reasons=[];may=[];perm={}
    if native_report.get('status')!='CONDITIONAL_DECLARED_EGO_NATIVE_PICARD_SEGMENTED_REPLAY':
        reasons.append('NATIVE_SEGMENTED_PROOF_NOT_AVAILABLE')
    if not actor_roster_physically_complete:reasons.append('FULL_ACTOR_ROSTER_NOT_PROVEN')
    if not controller_authority_physically_attested:reasons.append('REAL_CONTROLLER_AUTHORITY_NOT_PROVEN')
    if any(not isinstance(p,AtSlabStartPermission) for p in permissions):
        raise TypeError('permission snapshots required')
    for p in permissions:
        key=p.world_id,p.start,p.end
        if key in perm:reasons.append('DUPLICATE_START_PERMISSION')
        perm[key]=p
    expected={(r['world'],Q(r['start']),Q(r['end'])) for r in native_report.get('rows',())}
    if expected:
        span_start=min(key[1] for key in expected);span_end=max(key[2] for key in expected)
        if (native_report.get('clock_worlds_digest') != clock_source_digest(tuple(worlds),span_start,span_end,history_events)
                or native_report.get('clock_interval') != [str(span_start),str(span_end)]):
            reasons.append('NATIVE_CLOCK_SUPPORT_DECLARATION_DIGEST_MISMATCH')
    if set(perm)!=expected or set(native_certificates)!=expected:
        reasons.append('RESOURCE_WORLD_SLAB_SUPPORT_MISMATCH')
    world_map={w.world_id:w for w in worlds}
    if set(world_map)!={k[0] for k in expected}:
        reasons.append('RESOURCE_WORLD_DECLARATION_MISMATCH')
    for r in native_report.get('rows',()):
        key=r['world'],Q(r['start']),Q(r['end'])
        p=perm.get(key); cert=native_certificates.get(key)
        if p is None or cert is None:continue
        raw=json.dumps(cert,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
        if hashlib.sha256(raw).hexdigest()!=r.get('certificate_sha256') or not replay_certificate(cert).ok:
            reasons.append('CERTIFICATE_BYTES_OR_NATIVE_PROOF_INVALID:'+str(key));continue
        if len(p.initial_occupants)>p.capacity:
            reasons.append('INITIAL_RESOURCE_CAPACITY_EXCEEDED:'+str(key))
        if any(d not in p.allowed_directions for _,d in p.initial_occupants):
            reasons.append('INITIAL_RESOURCE_DIRECTION_UNAUTHORIZED:'+str(key))
        if len({d for _,d in p.initial_occupants})>1:
            reasons.append('OPPOSING_DIRECTIONS_INITIAL_RESOURCE_CONFLICT:'+str(key))
        if p.ack_version is not None and p.ack_version>p.command_version:
            reasons.append('ACK_VERSION_FROM_FUTURE:'+str(key))
        overlap=False
        for seg in cert.get('segments',()):
            # C/MPFR returned binary64 interval endpoints; map them to exact
            # rational numbers rather than rounding resource bounds to floats.
            lo,hi=seg['tube'][0]
            xlo,xhi=Q.from_float(lo),Q.from_float(hi)
            if xlo-ego_half_length<=resource_x_hi and xhi+ego_half_length>=resource_x_lo:
                overlap=True;break
        if overlap:
            may.append([key[0],str(key[1]),str(key[2])])
            if not p.entry_open:reasons.append('MAY_ENTER_WHILE_ENTRY_GUARD_CLOSED:'+str(key))
            if p.ack_version!=p.command_version:reasons.append('MAY_ENTER_WITHOUT_MATCHING_ACK_VERSION:'+str(key))
            if p.ack_version is not None:
                events=world_map[key[0]].events
                if not any(e.kind=='ACK' and e.time<=p.start and e.correlated_id==str(p.ack_version) for e in events):
                    reasons.append('NO_CLOCK_ACK_BEFORE_RESOURCE_SLAB:'+str(key))
            # Even if all permissions are open, MAY-occupancy from a tube is
            # NOT proof of an actual legal enter/stay/exit state sequence.
            reasons.append('POSSIBLE_INTERIOR_RESOURCE_OCCUPANCY_REQUIRES_TOPOLOGY_AND_OBSERVATION_PROOF:'+str(key))
    reasons=sorted(set(reasons))
    return dict(schema='rampd.a70.native_guard_projection.v1',
        status='CONDITIONAL_NATIVE_RESOURCE_X_EXCLUSION' if not reasons else 'UNKNOWN',
        reasons=reasons,world_slabs_with_possible_resource_occupancy=may,
        complete_polygon_resource_verified=False,
        continuous_enter_stay_exit_verified=False,all_agents_continuous_safety_verified=False,
        full_sc_certified=False,safe_training_labels_allowed=False)


def audit_rank_progress(rank_transitions:tuple[tuple[str,int,int,bool,bool],...])->dict:
    """A necessary rank/tail screen: (observation, source rank, child rank, terminal, tail-verified).

    The Boolean tail flag is a declaration here, not an independently replayed
    accepting policy. This screen cannot assert SC even for a PASS.
    """
    reasons=[];seen=set()
    if not rank_transitions:reasons.append('NO_OBSERVATION_BRANCHES')
    for entry in rank_transitions:
        if type(entry) is not tuple or len(entry)!=5:
            reasons.append('INVALID_RANK_BRANCH');continue
        obs,src,dst,terminal,tail=entry
        if not isinstance(obs,str) or not obs or obs in seen:reasons.append('DUPLICATE_OR_INVALID_OBSERVATION')
        seen.add(obs)
        if any(type(x) is not int or x<0 for x in (src,dst)):
            reasons.append('INVALID_NONNEGATIVE_RANK');continue
        if dst>=src:reasons.append('RANK_NOT_STRICTLY_DECREASING:'+str(obs))
        if type(terminal) is not bool or type(tail) is not bool:
            reasons.append('INVALID_TERMINAL_TAIL_FLAGS')
        elif terminal and not tail:reasons.append('TERMINAL_ACCEPTANCE_TAIL_UNPROVEN:'+str(obs))
        elif dst==0 and not terminal:reasons.append('ZERO_RANK_WITHOUT_ACCEPTING_TERMINAL:'+str(obs))
    reasons=sorted(set(reasons))
    return dict(schema='rampd.a70.rank_tail_necessary_screen.v1',
        status='CONDITIONAL_DECLARED_RANK_SANITY_PASS' if not reasons else 'UNKNOWN',
        reasons=reasons,independent_tail_policy_replayed=False,
        entire_successor_support_exhausted=False,sc_certified=False,
        safe_training_labels_allowed=False)
