#!/usr/bin/env python3
"""Two-direction sampled audit bound to the actual uploaded straight net."""
import argparse,json,hashlib,xml.etree.ElementTree as ET
from pathlib import Path
from collections import Counter
from sumo_metric_review import review,vehicle_polygon

def audit(work):
    from shapely.geometry import LineString
    from shapely.ops import unary_union
    net=work/'network.xml';tree=ET.parse(net);lanes={l.attrib['id']:l for l in tree.iter('lane')};pol={};centers={}
    for lane in ('midA_0','midB_0'):
        l=lanes[lane];line=LineString([tuple(map(float,p.split(','))) for p in l.attrib['shape'].split()]);pol[lane]=line.buffer(float(l.attrib.get('width','3.2'))/2,cap_style=2);centers[lane]=line
    combined=unary_union(list(pol.values()))
    if combined.geom_type!='Polygon' or combined.interiors:raise ValueError('unsupported corridor topology')
    definition={'network_sha256':hashlib.sha256(net.read_bytes()).hexdigest(),'polygon':list(combined.exterior.coords)}
    base=review(work,definition);negative=review(work,dict(definition,polygon=list(pol['midA_0'].exterior.coords)))
    counts=Counter();logical_only=Counter();actor_dirs={};errors=[];sample_entries=set();sample_exits=set();sample_ever=set();departed=set();arrived=set();max_occ=0;versions=set();negative_dirs=set()
    for line,r,n in zip((work/'metric_actor_trace.jsonl').open(),base['rows'],negative['rows']):
        t=json.loads(line);versions.add(t['rule_version']);departed.update(t['departed']);arrived.update(t['arrived']);current=set(r['occupancy']);max_occ=max(max_occ,len(current));sample_ever|=current
        for a in t['actors']:
            i=a['id'];d=a['direction']
            if i in actor_dirs and actor_dirs[i]!=d:errors.append('DIRECTION_METADATA_CHANGED')
            actor_dirs[i]=d
            if i in current:counts[d]+=1
        logical=set().union(*map(set,t['logical_swept_occupants'].values()))
        for i in logical-current:logical_only[actor_dirs.get(i,'UNKNOWN')]+=1
        sample_entries.update(r['entries']);sample_exits.update(r['exits']);negative_dirs.update(n['occupancy'].values())
    if not all(counts[d]>0 for d in ('A','B')):errors.append('DIRECTION_NONVACUITY_FAILURE')
    return dict(status='DESCRIPTIVE_SAMPLED_TWO_STRIP_AUDIT' if not base['errors'] and not errors else 'REVIEW',errors=base['errors']+errors,ticks=len(base['rows']),net_sha256=definition['network_sha256'],polygon=definition['polygon'],lane_centerline_distance_m=centers['midA_0'].distance(centers['midB_0']),lane_interior_overlap_area_m2=pol['midA_0'].intersection(pol['midB_0']).area,direction_sample_counts=dict(counts),logical_only_actor_tick_counts=dict(logical_only),sample_ever_actors=len(sample_ever),sample_entry_actors=len(sample_entries),sample_exit_actors=len(sample_exits),departed=len(departed),arrived=len(arrived),max_sampled_occupancy=max_occ,rule_versions=sorted(versions),one_sided_old_audit_status=negative['status'],one_sided_old_audit_error_count=len(negative['errors']),one_sided_observed_directions=sorted(negative_dirs),one_sided_new_coverage_rejected=negative_dirs!={'A','B'},physical_ack_proved=False,continuous_sweep_proved=False,formal_labels_authorized=False),base['rows']

def main():
    p=argparse.ArgumentParser();p.add_argument('--work',type=Path,required=True);p.add_argument('--output-dir',type=Path,required=True);a=p.parse_args();a.output_dir.mkdir(parents=True,exist_ok=False);r,rows=audit(a.work);(a.output_dir/'review.json').write_text(json.dumps(r,indent=2)+'\n');(a.output_dir/'sampled_occupancy.jsonl').write_text(''.join(json.dumps(x)+'\n' for x in rows));print(r);return 0 if r['status'].startswith('DESCRIPTIVE') else 4
if __name__=='__main__':raise SystemExit(main())
