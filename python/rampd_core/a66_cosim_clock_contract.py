"""A66: exact-rational declared CARLA/SUMO tick and Guard interlock trace gate.

This pure auditor is intentionally NOT a live bridge, not proof of network ACK,
not map registration, and not evidence of real lane occupancy. It rejects
incomplete or contradictory dual-simulator schedules before integration tests.
"""
from __future__ import annotations
from dataclasses import dataclass
from fractions import Fraction as Q

@dataclass(frozen=True)
class CoupledTick:
    step: int
    time: Q
    carla_frame: int
    carla_time: Q
    sumo_step: int
    sumo_time: Q
    tick_owner: str
    ego_owner: str
    signal_owner: str
    command_version: int
    ack_version: int | None
    requested_resource_entry: bool
    permission_open: bool
    resource_clear: bool

    def __post_init__(self):
        if any(type(x) is not int or x<0 for x in (self.step,self.carla_frame,self.sumo_step,self.command_version)):
            raise ValueError('nonnegative simulator frame/version integers required')
        if any(type(x) is not Q or x<0 for x in (self.time,self.carla_time,self.sumo_time)):
            raise ValueError('nonnegative exact rational timestamps required')
        if self.ack_version is not None and (type(self.ack_version) is not int or self.ack_version<0):
            raise ValueError('exact nonnegative ACK version or None required')
        for field in ('requested_resource_entry','permission_open','resource_clear'):
            if type(getattr(self,field)) is not bool:
                raise ValueError('literal boolean Guard states required')
        if any(not isinstance(getattr(self,k),str) or not getattr(self,k)
               for k in ('tick_owner','ego_owner','signal_owner')):
            raise ValueError('nonempty role owners required')


def audit_coupled_tick_trace(ticks: tuple[CoupledTick,...], *, dt:Q,
                             required_tick_owner:str, required_ego_owner:str='CARLA',
                             required_signal_owner:str='SUMO',
                             map_registration_sha256:str='') -> dict:
    if type(dt) is not Q or dt<=0:
        raise ValueError('exact positive step required')
    if any(not isinstance(t,CoupledTick) for t in ticks):
        raise TypeError('typed coupled tick records required')
    reasons=[]
    if not ticks:reasons.append('NO_TICK_PROVENANCE')
    if not isinstance(map_registration_sha256,str) or len(map_registration_sha256)!=64 or any(c not in '0123456789abcdef' for c in map_registration_sha256):
        reasons.append('MAP_ALIGNMENT_NOT_DECLARED')
    if not required_tick_owner or not required_ego_owner or not required_signal_owner:
        raise ValueError('unique asserted control owners must be named')
    last=None
    highest_ack=None
    for t in ticks:
        if (t.tick_owner,t.ego_owner,t.signal_owner)!=(required_tick_owner,required_ego_owner,required_signal_owner):
            reasons.append('SIMULATOR_OR_CONTROLLER_OWNERSHIP_MISMATCH')
        if t.time!=t.carla_time or t.time!=t.sumo_time:
            reasons.append('SYNCHRONOUS_TIME_ALIGNMENT_MISSING')
        if t.ack_version is not None and t.ack_version>t.command_version:
            reasons.append('FUTURE_ACK_VERSION')
        if t.ack_version is not None:
            if highest_ack is not None and t.ack_version<highest_ack:
                reasons.append('SIGNAL_ACK_VERSION_ROLLBACK')
            highest_ack=max(highest_ack if highest_ack is not None else t.ack_version,t.ack_version)
        if t.requested_resource_entry:
            if not t.permission_open:reasons.append('ENTRY_WITH_PERMISSION_CLOSED')
            if not t.resource_clear:reasons.append('ENTRY_WHILE_RESOURCE_NOT_CLEAR')
            if t.ack_version!=t.command_version:reasons.append('ENTRY_BEFORE_EFFECTIVE_SIGNAL_ACK')
        if last is not None:
            if (t.step!=last.step+1 or t.carla_frame!=last.carla_frame+1 or
                    t.sumo_step!=last.sumo_step+1):
                reasons.append('DUPLICATED_OR_SKIPPED_SIMULATOR_TICK')
            if (t.time-last.time)!=dt:
                reasons.append('WRONG_EXACT_SIMULATION_STEP')
            if t.command_version<last.command_version:
                reasons.append('SIGNAL_COMMAND_VERSION_ROLLBACK')
            if t.command_version>last.command_version+1:
                reasons.append('COMMAND_VERSION_SKIPPED_WITHOUT_EVENT_SLAB')
        last=t
    reasons=sorted(set(reasons))
    return {'schema':'rampd.a66.cosim_clock_contract.v1',
            'status':'CONDITIONAL_DECLARED_CO_SIM_TRACE_CONSISTENT_NOT_CERTIFIED' if not reasons else 'UNKNOWN',
            'reasons':reasons,'ticks_received':len(ticks),
            'simulators_actually_ticked_here':False,
            'map_registration_verified_from_geometry':False,
            'signal_ack_physically_observed':False,
            'full_resource_sweep_certified':False,
            'physics_verified':False,'safe_training_labels_allowed':False}
