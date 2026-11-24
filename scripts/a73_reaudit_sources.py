#!/usr/bin/env python3
"""Bounded offline A72 source re-review; no simulation or formal labels."""
import argparse,hashlib,json,sys,types
from pathlib import Path
from collections import Counter
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'python'))
pkg=types.ModuleType('rampd_core');pkg.__path__=[str(ROOT/'python'/'rampd_core')];sys.modules['rampd_core']=pkg
from rampd_core.a73_auxiliary import export
from rampd_core.a73_physics import diagnose

def main():
    p=argparse.ArgumentParser();p.add_argument('--results-root',type=Path,required=True);p.add_argument('--output-dir',type=Path,required=True);a=p.parse_args();r=a.results_root;o=a.output_dir
    if o.exists():raise SystemExit('REFUSE_OVERWRITE')
    files={};load=lambda f:json.loads(f.read_text());rows=lambda f:[json.loads(l) for l in f.read_text().splitlines() if l.strip()]
    def sha(f):return hashlib.sha256(f.read_bytes()).hexdigest()
    for f in sorted(r.rglob('*')):
        if f.is_file():files[str(f.relative_to(r))]=sha(f)
    aux=export(rows(r/'a72_511ny_auxiliary.jsonl')+rows(r/'a72_roadwork_real_100/roadwork_auxiliary.jsonl'))
    carla=diagnose(load(r/'a72_carla/pure_b045_run01.json'),.45,'pure')
    o.mkdir(parents=True)
    for name,data in [('weak_rows',aux.pop('rows')),('quarantine',aux.pop('quarantine'))]:
        (o/(name+'.jsonl')).write_text(''.join(json.dumps(x,ensure_ascii=False,allow_nan=False)+'\n' for x in data))
    report=dict(status='OFFLINE_SOURCE_REVIEW_NOT_SIMULATOR_REPLAY',input_sha256=files,auxiliary=aux,carla=carla,sumo_uploaded_summary=load(r/'a72_sumo_12_replay.json'),waymax_uploaded_sensitivity=load(r/'a72_waymax_lookahead_review.json'),waymax_real_probe=load(r/'a72_waymax_real_scenes_5.json'),roadwork_uploaded_pipeline=load(r/'a72_roadwork_real_100/pipeline_review.json'),roadwork_uploaded_gps=load(r/'a72_roadwork_real_100/gps_split.json'),formal_labels_authorized=False,full_sc_certified=False)
    (o/'review.json').write_text(json.dumps(report,ensure_ascii=False,indent=2,allow_nan=False)+'\n');print(aux['counts'])
if __name__=='__main__':main()
