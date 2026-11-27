"""Time-weighted descriptive stop duration. Does not prove deadlock or SC loss."""
from fractions import Fraction as Q
import math

def task_stop_metrics(intervals,*,speed_threshold_mps=.2):
    """Left-sample convention on contiguous declared executed decision intervals.
    Each row carries t0,t1, pending (bool or None), speed_mps, and resource_status
    (AVAILABLE/BLOCKED/UNKNOWN), independently observed or declared by caller.
    Unknown task status is counted separately, never imputed as completed.
    """
    if not math.isfinite(speed_threshold_mps) or speed_threshold_mps<0:raise ValueError('speed threshold')
    out={k:Q(0) for k in ('observed_s','pending_s','unknown_task_s','task_stop_s','blocked_stop_s','available_stop_s','unknown_resource_stop_s')};prev=None
    for r in intervals:
        t0,t1=Q(str(r['t0'])),Q(str(r['t1']));p=r['pending'];v=r['speed_mps'];status=r['resource_status']
        if t1<=t0 or (prev is not None and t0!=prev) or (p is not None and type(p) is not bool) or type(v) not in (int,float) or not math.isfinite(v) or v<0 or status not in ('BLOCKED','AVAILABLE','UNKNOWN'):raise ValueError('invalid wait interval')
        prev=t1;d=t1-t0;out['observed_s']+=d
        if p is None:out['unknown_task_s']+=d;continue
        if not p:continue
        out['pending_s']+=d
        if v<=speed_threshold_mps:
            out['task_stop_s']+=d;out[{'BLOCKED':'blocked_stop_s','AVAILABLE':'available_stop_s','UNKNOWN':'unknown_resource_stop_s'}[status]]+=d
    return dict(**{k:float(v) for k,v in out.items()},speed_threshold_mps=speed_threshold_mps,scope='SAMPLED_DESCRIPTIVE_STOP_TIME_NOT_DEADLOCK_OR_CAUSAL_ATTRIBUTION')
