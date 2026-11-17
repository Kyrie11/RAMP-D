#!/usr/bin/env python3
"""Read-only Waymax official tf.Example ingestion and logged visualization smoke.

No sim-agent rollout, counterfactual labels or safety proof produced.
Use an isolated Waymax environment if TensorFlow/JAX dependencies conflict.
"""
import argparse, json, sys, platform
from pathlib import Path
from importlib.metadata import version, PackageNotFoundError


def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--tf-example-file',type=Path,required=True)
    ap.add_argument('--output',type=Path,required=True); ap.add_argument('--plot',type=Path)
    a=ap.parse_args(); out={'status':'ERROR','scope':'WAYMAX_LOGGED_DATA_INGESTION_ONLY','python':sys.executable,
        'python_version':platform.python_version(),'input':str(a.tf_example_file),'counterfactual_labels_generated':False,'safety_certified':False}
    for p in ('waymo-waymax','jax','jaxlib','tensorflow','waymo-open-dataset-tf-2-12-0','numpy'):
        try: out[p]=version(p)
        except PackageNotFoundError: out[p]=None
    try:
        if not a.tf_example_file.is_file(): raise FileNotFoundError('local WOMD tf.Example shard required (not Scenario proto)')
        import dataclasses
        import numpy as np
        from waymax import config, dataloader, datatypes
        base=getattr(config,'WOD_1_3_1_VALIDATION',None)
        if base is None: raise RuntimeError('installed Waymax lacks official WOMD 1.3.1 configuration; use a compatible revision in a separate environment')
        cfg=dataclasses.replace(base,path=str(a.tf_example_file.resolve()),
            max_num_objects=128,repeat=1,num_shards=1,batch_dims=(),deterministic=True,shuffle_seed=None)
        state=next(dataloader.simulator_state_generator(config=cfg))
        valid=np.asarray(state.log_trajectory.valid); sdc=np.asarray(state.object_metadata.is_sdc,dtype=bool)
        ids=np.asarray(state.object_metadata.ids)
        if valid.ndim!=2 or sdc.ndim!=1 or sdc.sum()!=1 or valid.shape[0]!=sdc.shape[0] or valid.shape[-1]!=91:
            raise ValueError('unexpected unbatched standard 91-knot WOMD state or SDC identity')
        if not bool(valid[sdc,10].all()): raise ValueError('invalid SDC at standard current knot')
        if int(np.asarray(state.remaining_timesteps))<1: raise ValueError('no future step to replay')
        nxt=datatypes.update_state_by_log(state,num_steps=1)
        if int(np.asarray(nxt.timestep))!=int(np.asarray(state.timestep))+1: raise ValueError('logged timestep did not advance')
        out.update(status='PASS',sdc_id=int(ids[sdc][0]),shape=list(valid.shape),valid_knots=int(valid.sum()),
                   initial_timestep=int(np.asarray(state.timestep)),next_timestep=int(np.asarray(nxt.timestep)))
        if a.plot:
            from waymax import visualization
            import matplotlib.image as mpimg
            a.plot.parent.mkdir(parents=True,exist_ok=True)
            mpimg.imsave(a.plot,visualization.plot_simulator_state(state,use_log_traj=True));out['plot']=str(a.plot)
    except Exception as exc:
        out.update(status='SKIP' if isinstance(exc,(ImportError,FileNotFoundError)) else 'ERROR',reason=f'{type(exc).__name__}: {exc}')
    a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(out,indent=2)+'\n')
    print(json.dumps(out,indent=2));return 0 if out['status']=='PASS' else 3 if out['status']=='SKIP' else 4

if __name__=='__main__': raise SystemExit(main())
