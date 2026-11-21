"""CARLA-ready, sampled physical closure observation contract.

An authoritative actor registry and a completed synchronized snapshot are
necessary evidence of presence. They are not continuous-time coverage or
independent sensor proof. The physical interlock must be fail-closed when this
contract cannot be discharged. No automatic restoration is authorized.
"""
from __future__ import annotations
from dataclasses import dataclass
from fractions import Fraction as Q
from math import isfinite, atan2, sin, cos, hypot

@dataclass(frozen=True)
class Pose2:
    x:float
    y:float
    yaw:float
    def __post_init__(self):
        if not all(isfinite(z) for z in (self.x,self.y,self.yaw)):
            raise ValueError('nonfinite world pose')

@dataclass(frozen=True)
class BarrierDesign:
    event_id:str
    version:int
    resource_id:str
    command_id:str
    carla_actor_id:int
    expected:Pose2
    position_tolerance_m:float
    yaw_tolerance_rad:float
    def __post_init__(self):
        if (not all((self.event_id,self.resource_id,self.command_id)) or
            type(self.version) is not int or self.version<0 or
            type(self.carla_actor_id) is not int or self.carla_actor_id<=0 or
            not isinstance(self.expected,Pose2) or
            not all(isfinite(v) and v>=0 for v in (self.position_tolerance_m,self.yaw_tolerance_rad)) or
            self.yaw_tolerance_rad>=3.141592653589793):
            raise ValueError('invalid scoped barrier design')

@dataclass(frozen=True)
class PhysicalFrame:
    time:Q
    carla_frame:int
    sumo_time:Q
    barrier_poses:tuple[tuple[int,Pose2],...]
    detected_vehicle_boxes:tuple[tuple[float,float,float,float],...] # conservative WORLD AABBs
    authoritative_actor_roster:bool
    observations_complete:bool
    outstanding_commands:bool
    def __post_init__(self):
        if (type(self.time) is not Q or type(self.sumo_time) is not Q or
            type(self.carla_frame) is not int or self.carla_frame<0 or
            self.time<0 or self.sumo_time!=self.time or
            not all(type(x) is bool for x in (self.authoritative_actor_roster,
                                                  self.observations_complete,self.outstanding_commands))):
            raise ValueError('bad synchronized frame')
        ids=[a for a,_ in self.barrier_poses]
        if len(set(ids))!=len(ids) or not all(type(a) is int and isinstance(p,Pose2) for a,p in self.barrier_poses):
            raise ValueError('duplicate/invalid barrier actor')
        if any(len(box)!=4 or not all(isfinite(v) for v in box) or
               box[0]>box[2] or box[1]>box[3] for box in self.detected_vehicle_boxes):
            raise ValueError('invalid vehicle AABB')

@dataclass(frozen=True)
class FrameAudit:
    status:str
    reason:str
    observed_present:bool
    sampled_vehicle_intrusion:bool
    tick:Q
    actor_id:int
    continuous_coverage_proved:bool=False
    ready_to_reopen:bool=False


def audit_barrier_frame(design:BarrierDesign,frame:PhysicalFrame,
                        *,protected_aabb:tuple[float,float,float,float])->FrameAudit:
    if len(protected_aabb)!=4 or not all(isfinite(v) for v in protected_aabb) or protected_aabb[0]>=protected_aabb[2] or protected_aabb[1]>=protected_aabb[3]:
        raise ValueError('invalid protected resource AABB')
    def hit(b,c):
        return b[0]<=c[2] and c[0]<=b[2] and b[1]<=c[3] and c[1]<=b[3]
    found=dict(frame.barrier_poses).get(design.carla_actor_id)
    intr=any(hit(box,protected_aabb) for box in frame.detected_vehicle_boxes)
    if not frame.authoritative_actor_roster or not frame.observations_complete:
        reason='ROSTER_OR_OBSERVATION_INCOMPLETE'
    elif frame.outstanding_commands:
        reason='UNSETTLED_COMMANDS'
    elif found is None:
        reason='BARRIER_ACTOR_MISSING'
    elif hypot(found.x-design.expected.x,found.y-design.expected.y)>design.position_tolerance_m:
        reason='BARRIER_DISPLACED'
    elif abs(atan2(sin(found.yaw-design.expected.yaw),cos(found.yaw-design.expected.yaw)))>design.yaw_tolerance_rad:
        reason='BARRIER_ROTATED'
    elif intr:
        reason='VEHICLE_INSIDE_PROTECTED_REGION'
    else:
        reason='CURRENT_SAMPLED_FRAME_OBSERVATION_OK'
    ok=reason=='CURRENT_SAMPLED_FRAME_OBSERVATION_OK'
    return FrameAudit('SAMPLED_FRAME_PASS' if ok else 'REVIEW_OR_FAULT',reason,
                      found is not None,intr,frame.time,design.carla_actor_id)


def sampled_barrier_ack(design:BarrierDesign,frame:PhysicalFrame,
                        audit:FrameAudit):
    """Adapter for an existing `BarrierAck` monitoring input (server native).
    Requires a matching sampled roster proof; cannot certify inter-tick
    coverage or authorize an automatic OPEN transition.
    """
    if audit.status!='SAMPLED_FRAME_PASS' or audit.actor_id!=design.carla_actor_id or audit.tick!=frame.time:
        raise ValueError('no fresh physical registry proof')
    from .a53b_interlock import BarrierAck
    return BarrierAck(design.event_id,design.version,design.resource_id,
                      design.command_id,frame.time,'PRESENT',True,
                      'CARLA_SAMPLED_ACTOR_ROSTER_FRAME_'+str(frame.carla_frame))
