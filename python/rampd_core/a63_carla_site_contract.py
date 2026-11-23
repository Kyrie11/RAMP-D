"""Conservative CARLA start-lane identity agreement, not physical lane safety.

A traced Waypoint from generate_waypoints or get_spawn_points and a later
Map.get_waypoint(project_to_road=True) query are *different* sources of map
information.  CARLA can return a different road, section or lane at overlapping
roads/junctions.  This contract rejects ambiguous sites and records both IDs.
"""
from __future__ import annotations
import math


def wp_identity(wp):
    if wp is None:
        return None
    try:
        return (int(wp.road_id), int(wp.section_id), int(wp.lane_id))
    except (AttributeError, TypeError, ValueError):
        return None


def audit_start_waypoint(map_obj, carla, candidate_wp, pose, *, max_xy_error_m=1.0,
                         max_z_error_m=2.0):
    """Test candidate vs projected query; fail closed on mismatch or junction.

    Geometry tolerances only check local map consistency, never road safety.
    They are intentionally not used to replace a physical footprint test.
    """
    wanted = wp_identity(candidate_wp)
    record = {'status': 'REVIEW', 'candidate_identity': wanted,
              'projected_identity': None, 'projected_is_junction': None,
              'source_pose_xyz_m': None, 'xy_disagreement_m': None,
              'z_disagreement_m': None, 'certified': False}
    if wanted is None or bool(getattr(candidate_wp, 'is_junction', True)):
        record['reason'] = 'CANDIDATE_NOT_DRIVING_NONJUNCTION_LANE'
        return record
    try:
        xyz=pose.location
        record['source_pose_xyz_m']=[float(xyz.x),float(xyz.y),float(xyz.z)]
        if not all(math.isfinite(x) for x in record['source_pose_xyz_m']):
            record['reason']='NONFINITE_POSE'
            return record
        projected=map_obj.get_waypoint(xyz, project_to_road=True,
                                       lane_type=carla.LaneType.Driving)
        record['projected_identity']=wp_identity(projected)
        if projected is None:
            record['reason']='NO_PROJECTED_DRIVING_WAYPOINT'
            return record
        record['projected_is_junction']=bool(projected.is_junction)
        if projected.is_junction:
            record['reason']='PROJECTED_START_IS_JUNCTION'
            return record
        if record['projected_identity']!=wanted:
            record['reason']='PROJECTED_LANE_IDENTITY_MISMATCH'
            return record
        center=projected.transform.location
        error_xy=math.hypot(float(xyz.x)-float(center.x),
                            float(xyz.y)-float(center.y))
        error_z=abs(float(xyz.z)-float(center.z))
        record['xy_disagreement_m']=error_xy
        record['z_disagreement_m']=error_z
        if not math.isfinite(error_xy) or not math.isfinite(error_z):
            record['reason']='NONFINITE_PROJECTION_ERROR'
        elif error_xy>max_xy_error_m or error_z>max_z_error_m:
            record['reason']='START_POSE_NOT_NEAR_PROJECTED_CENTERLINE'
        else:
            record['status']='DESCRIPTIVE_LANE_IDENTITY_REPRODUCED'
            record['reason']='CANDIDATE_AND_PROJECTED_WAYPOINT_AGREE'
        return record
    except (AttributeError, TypeError, ValueError, RuntimeError) as exc:
        record['reason']='MAP_PROJECTION_QUERY_FAILED'
        record['query_error']=type(exc).__name__+': '+str(exc)
        return record
