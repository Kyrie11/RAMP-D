"""Exact fixed-step and single-owner co-simulation *contract*, not a bridge.

Actual CARLA/SUMO tick scheduling, state mirroring and map registration must be
verified by live server experiments before any physical deployment labels.
"""
from dataclasses import dataclass
from fractions import Fraction as Q

@dataclass(frozen=True)
class CoSimAuthority:
    step:Q
    ego_controller:str
    traffic_controller:str
    tls_controller:str
    source_opendrive_sha256:str
    def __post_init__(self):
        if type(self.step) is not Q or self.step<=0:raise ValueError('exact step required')
        if (self.ego_controller,self.traffic_controller,self.tls_controller)!=('CARLA','SUMO','SUMO'):
            raise ValueError('single actor/signal ownership expected for this experiment')
        if len(self.source_opendrive_sha256)!=64 or any(c not in '0123456789abcdef' for c in self.source_opendrive_sha256):
            raise ValueError('common source OpenDRIVE provenance required')

@dataclass(frozen=True)
class CoSimPair:
    index:int
    carla_frame:int
    carla_time:Q
    sumo_time:Q
    delivered_sensor_time:Q|None
    def __post_init__(self):
        if (type(self.index) is not int or self.index<0 or type(self.carla_frame) is not int or self.carla_frame<0 or
            type(self.carla_time) is not Q or type(self.sumo_time) is not Q or
            (self.delivered_sensor_time is not None and type(self.delivered_sensor_time) is not Q)):
            raise ValueError('exact frame contract required')


def audit_pair(contract:CoSimAuthority,previous:CoSimPair,current:CoSimPair):
    if current.index!=previous.index+1 or current.carla_frame!=previous.carla_frame+1:
        return 'UNKNOWN_FRAME_DROP'
    if (current.carla_time-previous.carla_time!=contract.step or
        current.sumo_time-previous.sumo_time!=contract.step):
        return 'UNKNOWN_TIME_DRIFT'
    if current.carla_time-current.sumo_time!=previous.carla_time-previous.sumo_time:
        return 'UNKNOWN_CLOCK_OFFSET_DRIFT'
    # delayed sensor packets may be used by the planner only with a production-
    # time stamp, never interpreted as observation at the delivery tick.
    if current.delivered_sensor_time is not None and current.delivered_sensor_time>current.carla_time:
        return 'UNKNOWN_SENSOR_TIME_FROM_FUTURE'
    return 'FRAME_STEP_CONSISTENCY_PASS_NOT_PHYSICAL_COSIM_CERTIFICATE'
