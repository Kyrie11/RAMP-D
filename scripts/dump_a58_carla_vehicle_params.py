#!/usr/bin/env python3
"""Read-only CARLA 0.9.16 vehicle geometry and physics metadata.

Does NOT infer a calibrated rear-axle/CG model from bounding-box center. Does
NOT control a vehicle or advance simulation. Inspect units and provenance
before using wheel metadata as an input to a safety certificate.
"""
import argparse,json,traceback
from pathlib import Path


def vector(v):
    return {axis:float(getattr(v,axis)) for axis in ('x','y','z')}


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--host',default='127.0.0.1')
    ap.add_argument('--port',type=int,default=2000)
    ap.add_argument('--actor-id',type=int,default=None)
    ap.add_argument('--output',type=Path,required=True)
    a=ap.parse_args()
    result={'status':'ERROR','calibrated_vehicle_dynamics':False,'rear_axle_reference_certified':False,
            'braking_force_calibrated':False,'actuator_delay_calibrated':False,
            'steering_rate_calibrated':False}
    try:
        import carla
        client=carla.Client(a.host,a.port)
        client.set_timeout(8)
        world=client.get_world()
        vehicles=[actor for actor in world.get_actors().filter('vehicle.*')
                  if a.actor_id is None or actor.id==a.actor_id]
        result.update(status='READ_ONLY_METADATA_CAPTURED',carla_server_version=client.get_server_version(),
                      carla_map=world.get_map().name,vehicle_count=len(vehicles),vehicles=[])
        for actor in vehicles:
            box=actor.bounding_box
            body=actor.get_transform()
            p=actor.get_physics_control()
            wheels=[]
            for wheel in p.wheels:
                wheels.append({'position_raw':vector(wheel.position),'radius_raw':float(wheel.radius),
                               'max_steer_angle_raw':float(wheel.max_steer_angle),
                               'tire_friction':float(wheel.tire_friction)})
            result['vehicles'].append({'actor_id':int(actor.id),'type_id':actor.type_id,
                 'body_transform':{'location':vector(body.location),
                                   'rotation_degrees':{'yaw':float(body.rotation.yaw),
                                                       'pitch':float(body.rotation.pitch),
                                                       'roll':float(body.rotation.roll)}},
                 'bounding_box':{'local_location':vector(box.location),'extent':vector(box.extent),
                                 'local_rotation_degrees':{'yaw':float(box.rotation.yaw),
                                                           'pitch':float(box.rotation.pitch),
                                                           'roll':float(box.rotation.roll)}},
                 'physics':{'mass':float(p.mass),'center_of_mass_raw':vector(p.center_of_mass),
                            'drag_coefficient':float(p.drag_coefficient),
                            'wheels':wheels},
                 'WARNING':'Uncalibrated raw CARLA metadata; no validated wheelbase, rear axle, CG or actuator map inferred'})
        if not vehicles:result['status']='REVIEW_NO_VEHICLE_ACTOR'
    except Exception as e:
        result['error']=f'{type(e).__name__}: {e}'
        result['traceback']=traceback.format_exc()
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    print(result['status'])
    return 0 if result['status']=='READ_ONLY_METADATA_CAPTURED' else 4

if __name__=='__main__':raise SystemExit(main())
