#!/usr/bin/env python3
"""Read-only CARLA settings + isolated headless SUMO time-step preflight.
Does NOT run a synchronized CARLA/SUMO simulation, mirror actors, deploy a
barrier, or change CARLA world settings. Never emits a physical PASS label.
"""
import argparse,json,sys,subprocess,traceback,hashlib
from pathlib import Path

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--carla-host',default='127.0.0.1');p.add_argument('--carla-port',type=int,default=2000)
    p.add_argument('--sumo-network',required=True,type=Path);p.add_argument('--sumo-routes',required=True,type=Path)
    p.add_argument('--sumo',default='sumo');p.add_argument('--step',type=float,default=.1)
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();r={'status':'PREFLIGHT_ERROR','physical_cosim_certified':False,'barrier_deployment_verified':False}
    try:
        import carla,traci
        client=carla.Client(a.carla_host,a.carla_port);client.set_timeout(8.)
        world=client.get_world();settings=world.get_settings()
        carla_version=client.get_server_version();map_name=world.get_map().name
        opendrive_digest=hashlib.sha256(world.get_map().to_opendrive().encode()).hexdigest()
        if not a.sumo_network.is_file() or not a.sumo_routes.is_file():raise ValueError('SUMO network and routes required')
        # Separate SUMO subprocess, not the production co-sim bridge.
        traci.start([a.sumo,'-n',str(a.sumo_network.resolve()),'-r',str(a.sumo_routes.resolve()),
                     '--step-length',str(a.step),'--no-step-log','true','--time-to-teleport','-1'])
        try:
            dt=traci.simulation.getDeltaT()
            sumo_version=traci.getVersion()
        finally:traci.close()
        ready=(carla_version.startswith('0.9.16') and settings.synchronous_mode and
               settings.fixed_delta_seconds is not None and
               abs(settings.fixed_delta_seconds-a.step)<1e-10 and abs(dt-a.step)<1e-10)
        r.update(status='PREFLIGHT_TIMESTEP_PASS_MAP_AND_ACTOR_SYNC_PENDING' if ready else 'PREFLIGHT_REVIEW',
                 carla_server_version=carla_version,carla_map=map_name,
                 carla_opendrive_sha256=opendrive_digest,carla_synchronous=settings.synchronous_mode,
                 carla_fixed_delta_s=settings.fixed_delta_seconds,sumo_dt_s=dt,sumo_version=sumo_version,
                 geometry_alignment_verified=False,vehicle_identity_mirror_verified=False,
                 traffic_signal_authority_verified=False)
    except Exception as e:r.update(error=f'{type(e).__name__}: {e}',traceback=traceback.format_exc())
    a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(r,indent=2,default=str)+'\n')
    print(r['status']);return 0 if r['status'].startswith('PREFLIGHT_TIMESTEP_PASS') else 4
if __name__=='__main__':raise SystemExit(main())
