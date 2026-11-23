#!/usr/bin/env python3
"""Offline brake/steer visual diagnostic; does not certify continuous safety."""
import argparse, json
from pathlib import Path

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--input',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args()
    if a.input.resolve()==a.output.resolve() or a.output.exists():
        raise FileExistsError('REFUSE_OVERWRITE_EVIDENCE')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    d=json.loads(a.input.read_text())
    if not isinstance(d.get('trials'),list) or len(d['trials'])!=1:
        raise ValueError('EXPECTED_ONE_TRIAL')
    trial=d['trials'][0];samples=trial['samples'];tr=trial['trigger_frame']
    if tr<0 or len(samples)<2:raise ValueError('NO_TRIGGER_OR_FRAMES')
    time=[r['sim_time_s']-samples[0]['sim_time_s'] for r in samples]
    t0=next(r['sim_time_s']-samples[0]['sim_time_s'] for r in samples if r['frame']==tr)
    fig,ax=plt.subplots(3,1,figsize=(10,9),sharex=True,constrained_layout=True)
    ax[0].plot(time,[r['planar_speed_mps'] for r in samples],label='Planar speed (m/s)')
    ax[0].plot(time,[r['vertical_speed_mps'] for r in samples],label='Vertical speed (m/s)')
    ax[0].set_ylabel('Speed (m/s)');ax[0].legend()
    ax[1].plot(time,[r['signed_longitudinal_accel_mps2'] for r in samples],label='CARLA longitudinal acceleration')
    ax[1].plot(time,[r['command_brake'] for r in samples],label='Brake command (normalized)')
    ax[1].plot(time,[r['command_steer'] for r in samples],label='Steer command (normalized)')
    ax[1].set_ylabel('Accel (m/s²) / command');ax[1].legend()
    remaining=[r.get('lane_audit',{}).get('available_halfwidth_m',float('nan'))-
               r.get('lane_audit',{}).get('required_halfwidth_m',float('nan')) for r in samples]
    ax[2].plot(time,remaining,label='Sampled lane clearance proxy (m)')
    ax[2].axhline(0,linewidth=0.8)
    ax[2].set_ylabel('Lane proxy (m)');ax[2].set_xlabel('Seconds since first recorded sample');ax[2].legend()
    for axis in ax:axis.axvline(t0,linestyle='--',linewidth=1)
    fig.suptitle('CARLA single control trace (descriptive only, NOT continuous-time safety proof)')
    a.output.parent.mkdir(parents=True,exist_ok=True)
    fig.savefig(a.output,dpi=140)
    plt.close(fig)
    print(a.output)
if __name__=='__main__':main()
