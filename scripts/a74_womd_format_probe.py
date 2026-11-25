#!/usr/bin/env python3
import argparse,json,hashlib,struct,itertools
from pathlib import Path


def classify(payload, scenario_factory, example_factory):
    result={'record_sha256':hashlib.sha256(payload).hexdigest(),'bytes':len(payload)}
    try:
        s=scenario_factory();s.ParseFromString(payload)
        if s.scenario_id and len(s.tracks)>0 and len(s.timestamps_seconds)>0 and 0<=s.sdc_track_index<len(s.tracks) and all(len(t.states)==len(s.timestamps_seconds) for t in s.tracks):
            result.update(kind='SCENARIO',scenario_id=s.scenario_id,tracks=len(s.tracks),timesteps=len(s.timestamps_seconds));return result
        result['scenario_error']='missing structural fields or inconsistent dimensions'
    except Exception as e:result['scenario_error']=type(e).__name__+': '+str(e)
    try:
        ex=example_factory();ex.ParseFromString(payload);keys=set(ex.features.feature)
        if {'state/past/x','state/current/x','state/id'}<=keys:
            result.update(kind='TFEXAMPLE_NOT_SCENARIO',feature_keys=sorted(keys)[:30]);return result
        result['example_error']='missing WOMD feature keys'
    except Exception as e:result['example_error']=type(e).__name__+': '+str(e)
    result['kind']='UNKNOWN_RECORD_FORMAT';return result


def main():
    p=argparse.ArgumentParser();p.add_argument('--file',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--max-records',type=int,default=5);a=p.parse_args()
    if a.output.exists() or not 1<=a.max_records<=50:raise SystemExit('new output and 1..50 records required')
    r={'status':'REVIEW','file':str(a.file),'records':[],'formal_labels_authorized':False}
    try:
        import tensorflow as tf
        from waymo_open_dataset.protos import scenario_pb2
        with a.file.open('rb') as f:magic=f.read(4)
        compression='GZIP' if magic[:2]==b'\x1f\x8b' else ''
        if magic[:2]==b'PK':raise ValueError('ZIP container, extract shard first')
        r['compression']=compression or 'NONE';r['tensorflow_version']=tf.__version__;r['scenario_module']=scenario_pb2.__file__
        for raw in itertools.islice(tf.data.TFRecordDataset([str(a.file)],compression_type=compression).as_numpy_iterator(),a.max_records):
            r['records'].append(classify(bytes(raw),scenario_pb2.Scenario,tf.train.Example))
        if r['records'] and all(x['kind']=='SCENARIO' for x in r['records']):r['status']='SCENARIO_STRUCTURAL_PROBE_PASS'
    except Exception as e:r['reason']=type(e).__name__+': '+str(e)
    a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(r,indent=2)+'\n');print(r['status']);return 0 if r['status'].endswith('PASS') else 4
if __name__=='__main__':raise SystemExit(main())
