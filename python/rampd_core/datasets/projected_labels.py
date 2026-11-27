"""Evidence adapter for audited projected diagnostic pairs. Not full-scene truth.
No promotion of the source's training authorization; no continuous/SC label.
"""
from fractions import Fraction as Q
from .incident_response import audit_pair,Closure
from .rule_overlay import clock_bin_target
from .split_manifest import canonical_digest

HEADS=('event','joint','occupancy','observation','viability','margin','deadline','causal')

def export_pair(pair):
    checked=audit_pair(pair)
    if not checked['ok']:raise ValueError('pair trace audit failed: '+str(checked['errors']))
    spec=pair['spec'];c=Closure(**spec['closure']);out=[];edges=[str(Q(j,2)) for j in range(13)]
    for name,run in pair['runs'].items():
        frames=run['frames'];observed_end=Q(frames[-1]['t']); active=run['event'];receipts=spec['receipts']
        # These are declared schedule labels (not observed physical clocks).
        onset=clock_bin_target(edges,kind='EXACT',value=c.effective_on) if active else clock_bin_target(edges,kind='RIGHT_CENSORED',value=edges[-1])
        expiry=clock_bin_target(edges,kind='EXACT',value=c.effective_off) if active else clock_bin_target(edges,kind='UNKNOWN')
        receipt={}
        for i,t in receipts.items():
            if not active:receipt[i]=clock_bin_target(edges,kind='UNKNOWN')
            elif t is not None and Q(t)<=observed_end:receipt[i]=clock_bin_target(edges,kind='EXACT',value=t)
            else:receipt[i]=clock_bin_target(edges,kind='RIGHT_CENSORED',value=str(observed_end))
        out.append(dict(schema='rampd.projected_evidence.v1',family_id=spec['family_id'],split=spec['split'],source_digest=spec['source_digest'],spec_sha256=pair['spec_sha256'],run=name,run_sha256=canonical_digest(run),domain='DECLARED_PROJECTED_MODEL_EVALUATION_ONLY',clock_edges_s=edges,observed_end_s=str(observed_end),complete=run['stop']=='HORIZON' and 'requested_steps' in run and len(frames)==run['requested_steps']+1,declared_event=dict(exists=active,onset=onset,expiry=expiry),sampled_occupancy=[dict(t=f['t'],ids=f['occupied']) for f in frames],message_clock_evidence=receipt,physical_execution=None,continuous_occupancy=None,heads={h:False for h in HEADS},training_allowed=False,formal_sc=False,excluded_current=spec['excluded_current']))
    return out
