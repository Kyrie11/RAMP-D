"""Observed simulator chain audit. No physical authority inferred from readback.
Requires all declared actors each tick, per-resource exact boxes, stable
version, issue -> readback -> occupied sample, exact rational tick clocks.
This is sampled evidence; between-tick collision/occupancy remains unknown.
"""
from .finite_joint_reference import q,box,contact

def audit_trace(trace):
    errors=[];out=[]; roster=trace['roster']; resources=trace['resources']; ticks=trace['ticks'];dt=q(trace['dt']); previous=None; prev_version=None
    if dt<=0 or not ticks or not roster or len(set(roster))!=len(roster) or not resources:raise ValueError('empty or invalid trace')
    if not trace.get('map_sha256') or not trace.get('registry_sha256'):raise ValueError('missing coordinate/registry binding')
    last_occupancy={};prev_tick=None;prev_config=None;prev_epoch=None;prev_command=None
    for r in ticks:
        t=q(r['time']);issue=q(r['issue']);read=q(r['readback']);event=q(r['effective']);v=r['version'];
        if previous is not None and t-previous!=dt:errors.append('TICK_GAP')
        if prev_tick is not None and (type(r['tick']) is not int or r['tick']!=prev_tick+1):errors.append('FRAME_GAP')
        if not event<=issue<=read<=t:errors.append('CLOCK_ORDER')
        if type(v) is not int or v<0 or (prev_version is not None and v<prev_version):errors.append('VERSION_ORDER')
        if r['readback_version']!=v or r['command']!=r['observed_execution']:errors.append('EXECUTION_MISMATCH')
        if set(r['actors'])!=set(roster):errors.append('ROSTER_MISMATCH')
        if set(r['permissions'])!=set(resources):errors.append('GUARD_COVERAGE');continue
        if 'command_epoch' in r:
            epoch=r['command_epoch']
            if type(epoch) is not int or epoch<0 or (prev_epoch is not None and epoch<prev_epoch) or r.get('readback_epoch')!=epoch:errors.append('COMMAND_EPOCH_MISMATCH')
            if prev_epoch==epoch and prev_command!=r['command']:errors.append('SAME_EPOCH_CHANGED_COMMAND')
            if prev_version==v and prev_config is not None and prev_config[1]!=r['permissions']:errors.append('SAME_VERSION_CHANGED_GUARD')
            prev_epoch=epoch;prev_command=r['command']
        elif prev_version==v and prev_config!=(r['command'],r['permissions']):errors.append('SAME_VERSION_CHANGED_GUARD')
        occupancy={}
        for name,p in resources.items():
            p=box(p);g=r['permissions'][name];occupied={a for a,b in r['actors'].items() if contact(b,b,p,p) is not None};occupancy[name]=sorted(occupied)
            if type(g['capacity']) is not int or g['capacity']<0 or len(occupied)>g['capacity']:errors.append('CAPACITY:'+name)
            if occupied and g['stay'] is not True:errors.append('STAY:'+name)
            if previous is not None:
                if occupied-set(last_occupancy[name]) and g['entry'] is not True:errors.append('ENTRY:'+name)
                if set(last_occupancy[name])-occupied and g['exit'] is not True:errors.append('EXIT:'+name)
            elif occupied:errors.append('INITIAL_OCCUPANCY_HISTORY_UNKNOWN:'+name)
        if occupancy!=r['reported_occupancy']:errors.append('GEOMETRY_OCCUPANCY_MISMATCH')
        out.append({'time':str(t),'version':v,'occupancy':occupancy});previous=t;prev_tick=r['tick'];prev_version=v;prev_config=(r['command'],r['permissions']);last_occupancy=occupancy
    return dict(status='DESCRIPTIVE_DECLARED_SAMPLED_CHAIN' if not errors else 'REVIEW',errors=sorted(set(errors)),ticks=out,physical_ack_verified=False,continuous_occupancy_verified=False,formal_labels_authorized=False)
