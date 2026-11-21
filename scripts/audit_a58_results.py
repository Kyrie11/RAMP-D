#!/usr/bin/env python3
"""A58 independent A57 uploaded-result triage. Never confuse a PASS JSON
scope with actual real-world / full-support certification.
"""
import argparse,json,sys,types
from pathlib import Path
root=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root/'python'))
pkg=types.ModuleType('rampd_core');pkg.__path__=[str(root/'python'/'rampd_core')];sys.modules['rampd_core']=pkg
from rampd_core.a58_sumo_audit import audit_runs

def main():
    p=argparse.ArgumentParser();p.add_argument('--waymax',type=Path,nargs='+',required=True)
    p.add_argument('--sumo',type=Path,nargs='+',required=True)
    p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    r=[]
    for f in a.waymax:
        z=json.loads(f.read_text()); audit=z['official_internal_audit']['A'][0]
        gap=z['initial_geometric_gap_m'];r.append(dict(source=str(f),points=z['lookahead_points'],
            geometry_gap=gap,internal_gap=audit['distance_m'],gap_bias=audit['distance_m']-gap,
            raw_idm_accel=audit['raw_accel_mps2'],
            numerical_implementation_checked=z['aa_max_state_difference']==0 and z['smooth_ego_reference_max_abs_error']<1e-4,
            continuous_jerk_proved=z['continuous_jerk_certificate'],
            real_driver_behavior_validated=False))
    # Single-seed variants are intentionally not treated as a multi-seed test.
    s=[]
    for f in a.sumo:
        z=json.loads(f.read_text());s.append(dict(source=str(f),seed=z['seed'],status=z['status'],
          guard='reserve' if z.get('stop_reserve_guard') else 'old' if z.get('comfort_guard') else 'baseline',
          brake_samples=len(z['brake_steps']),departed=z['departed_count'],arrived=z['arrived_count'],
          completed=z['roster_completion_pass'],resource_violations=z['violations'],
          phase_transitions=len(z['transitions'])))
    out=dict(status='SCOPED_RUNTIME_AUDIT',waymax=r,sumo=s,full_real_response_validated=False,
             real_physical_closure_certified=False,physical_post_sc_integrated=False)
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
    print('SCOPED_RUNTIME_AUDIT',len(r),'Waymax profiles',len(s),'SUMO variants')
if __name__=='__main__':main()
