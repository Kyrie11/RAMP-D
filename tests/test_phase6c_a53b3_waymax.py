import importlib.util
from pathlib import Path
from types import SimpleNamespace
import numpy as np
import pytest
spec=importlib.util.spec_from_file_location('wm_probe',Path(__file__).resolve().parents[1]/'scripts/probe_waymax.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

def state():
    x=np.arange(6,dtype=float).reshape(2,3)
    fields={k:x.copy() for k in ('x','y','yaw','vel_x','vel_y','length','width')}
    return SimpleNamespace(log_trajectory=SimpleNamespace(valid=np.ones((2,3),bool),**fields),sim_trajectory=SimpleNamespace(valid=np.array([[True,True,False],[True,True,False]]),**{k:v.copy() for k,v in fields.items()}))

def test_waymax_replay_numeric_mask_and_future_leakage():
    s=state();r=m.replay_numeric_check(s,1);assert r['history_valid_knots']==4 and r['simulated_future_valid_knots']==0
    s.sim_trajectory.x[0,1]+=1
    with pytest.raises(ValueError,match='field mismatch'):m.replay_numeric_check(s,1)
    s=state();s.sim_trajectory.valid[0,2]=True
    with pytest.raises(ValueError,match='future'):m.replay_numeric_check(s,1)
