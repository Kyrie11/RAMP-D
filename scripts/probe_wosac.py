#!/usr/bin/env python3
"""Official WOSAC API probe / explicitly nonresponsive CV baseline.
No safety or causal label claims. Requires a version with ChallengeType API.
"""
import argparse, hashlib, json, math, sys
from pathlib import Path
from importlib.metadata import version


def main():
    p=argparse.ArgumentParser();p.add_argument('--scenario-file',type=Path,required=True);p.add_argument('--scenario-id');p.add_argument('--max-records',type=int,default=20);p.add_argument('--output',type=Path,required=True);p.add_argument('--cv-baseline',action='store_true');p.add_argument('--rollouts',type=Path);p.add_argument('--config',type=Path);a=p.parse_args()
    out={'status':'ERROR','scope':'WOSAC_OFFICIAL_INTERFACE_PROBE','python':sys.executable,'counterfactual_labels_generated':False,'safety_certified':False,'metrics_computed':False}
    try:
        if a.cv_baseline and a.rollouts:raise ValueError('choose CV baseline or submitted rollouts, not both')
        if a.max_records<1:raise ValueError('positive max-records required')
        import tensorflow as tf
        from waymo_open_dataset.protos import scenario_pb2,sim_agents_submission_pb2,sim_agents_metrics_pb2
        from waymo_open_dataset.utils.sim_agents import submission_specs as spec
        from waymo_open_dataset.wdl_limited.sim_agents_metrics import metrics
        from google.protobuf import json_format,text_format
        out['waymo_package']=version('waymo-open-dataset-tf-2-12-0')
        challenge=spec.ChallengeType.SIM_AGENTS; cfg=spec.get_submission_config(challenge)
        if (cfg.current_time_index,cfg.n_simulation_steps,cfg.n_rollouts)!=(10,80,32):raise ValueError('unexpected WOSAC submission specification')
        for raw in tf.data.TFRecordDataset(str(a.scenario_file)).take(a.max_records):
            b=bytes(raw.numpy());s=scenario_pb2.Scenario.FromString(b)
            if a.scenario_id is None or s.scenario_id==a.scenario_id: break
        else:raise ValueError('scenario not found in bounded scan')
        if s.current_time_index!=10 or len(s.timestamps_seconds)!=91:raise ValueError('expected standard WOMD 91-knot Scenario')
        ids=list(spec.get_sim_agent_ids(s,challenge));evaluation=list(spec.get_evaluation_sim_agent_ids(s,challenge))
        if not ids or len(ids)!=len(set(ids)) or not set(evaluation)<=set(ids):raise ValueError('invalid official agent identity set')
        out.update(scenario_id=s.scenario_id,record_sha256=hashlib.sha256(b).hexdigest(),sim_agent_ids=ids,evaluation_agent_ids=evaluation,history_current_step=10,rollouts_required=32,future_steps=80)
        if a.config:
            config_path=a.config;mc=sim_agents_metrics_pb2.SimAgentMetricsConfig();text_format.Parse(config_path.read_text(),mc)
        else:
            # Official master helper uses a relative resource path; prefer the
            # installed same-version resource explicitly if provided by wheel.
            config_path=Path(metrics.__file__).with_name('challenge_2025_sim_agents_config.textproto')
            if config_path.is_file():
                mc=sim_agents_metrics_pb2.SimAgentMetricsConfig();text_format.Parse(config_path.read_text(),mc)
            else: mc=metrics.load_metrics_config(challenge)
        out['config_sha256']=hashlib.sha256(mc.SerializeToString(deterministic=True)).hexdigest()
        if a.cv_baseline or a.rollouts:
            if a.cv_baseline:
                roll=sim_agents_submission_pb2.ScenarioRollouts(scenario_id=s.scenario_id)
                one=sim_agents_submission_pb2.JointScene()
                for track in s.tracks:
                    if track.id not in ids:continue
                    x=track.states[10];tr=one.simulated_trajectories.add(object_id=track.id)
                    if not all(math.isfinite(v) for v in (x.center_x,x.center_y,x.center_z,x.heading,x.velocity_x,x.velocity_y)):raise ValueError('nonfinite CV state')
                    for i in range(1,81):
                        t=i*cfg.step_duration_seconds;tr.center_x.append(x.center_x+t*x.velocity_x);tr.center_y.append(x.center_y+t*x.velocity_y);tr.center_z.append(x.center_z);tr.heading.append(x.heading)
                for _ in range(32):roll.joint_scenes.add().CopyFrom(one)
                out['rollout_source']='DETERMINISTIC_CONSTANT_VELOCITY_32_IDENTICAL_NONRESPONSIVE_BASELINE'
            else:
                roll=sim_agents_submission_pb2.ScenarioRollouts.FromString(a.rollouts.read_bytes());out['rollout_source']='USER_SUPPLIED_BINARY_PROTO'
            if roll.scenario_id!=s.scenario_id:raise ValueError('scenario id mismatch')
            for joint in roll.joint_scenes:
                got=[tr.object_id for tr in joint.simulated_trajectories]
                if len(got)!=len(ids) or set(got)!=set(ids):raise ValueError('incomplete/duplicate sim-agent ids')
                if any(not math.isfinite(v) for tr in joint.simulated_trajectories for seq in (tr.center_x,tr.center_y,tr.center_z,tr.heading) for v in seq):raise ValueError('nonfinite rollout')
            spec.validate_scenario_rollouts(roll,s,challenge)
            result=metrics.compute_scenario_metrics_for_bundle(mc,s,roll,challenge)
            out.update(metrics_computed=True,metrics=json_format.MessageToDict(result,preserving_proto_field_name=True))
        out['status']='PASS'
    except Exception as exc:out.update(reason=f'{type(exc).__name__}: {exc}')
    a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out,indent=2));return 0 if out['status']=='PASS' else 4
if __name__=='__main__':raise SystemExit(main())
