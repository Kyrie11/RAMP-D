"""Label-side factual extraction, NOT a complete 8-loss training dataset.

A future recorded ego path is an action surrogate (not measured jerk/steering).
It is never inserted into history features. Future-only actors are excluded from
an identity-conditioned forecast until an explicit birth model is implemented.
"""
from __future__ import annotations
from dataclasses import dataclass
from .phase6c import SceneForecastSample
import hashlib
import json
import math


@dataclass(frozen=True)
class FactualJointLabels:
    source_digest: str
    scenario_id: str
    ego_id: str | None
    timestamps_s: tuple[float,...]
    ego_prefix_xy: tuple[tuple[float,float],...]
    actor_ids: tuple[str,...]
    target_xy: tuple[tuple[tuple[float,float] | None,...],...]
    valid_mask: tuple[tuple[bool,...],...]
    status: str
    ego_prefix_digest: str | None = None
    coordinate_frame: str = ''
    position_reference: str = ''
    ego_prefix_timestamps_s: tuple[float,...] = ()

    @property
    def usable(self):
        return self.status == 'LOGGED_EGO_PATH_SURROGATE'


def factual_joint_labels(sample: SceneForecastSample, prefix_steps: int) -> FactualJointLabels:
    """No invented ego or missing action. All actors share one logged future.

    `prefix_steps` counts future knots; ego must be valid at the current knot
    and all these knots. Other actors need usable history. Missing target knots
    remain None with mask False, not artificial (0,0) training targets.
    """
    if type(prefix_steps) is not int or prefix_steps <= 0:
        raise ValueError('positive integer ego prefix length required')
    def result(status, ego_id=None, times=(), prefix=(), ids=(), values=(), masks=(), digest=None, prefix_times=()):
        return FactualJointLabels(sample.source_digest,sample.scenario_id,ego_id,times,prefix,ids,
                   values,masks,status,digest,sample.coordinate_frame,sample.position_reference,prefix_times)
    if not sample.future_available or prefix_steps > len(sample.future_timestamps_s):
        return result('NO_LABELLED_PREFIX')
    sid=sample.sdc_track_id
    if sid is None: return result('NO_EXPLICIT_EGO')
    history={t.track_id:t for t in sample.history_tracks}
    targets={t.track_id:t for t in sample.future_targets}
    ego=history[sid]; future=targets.get(sid)
    if not ego.valid_observation_mask[-1] or future is None or not all(future.valid_future_mask[:prefix_steps]):
        return result('INCOMPLETE_LOGGED_EGO_PREFIX',sid)
    def xy(state):
        if state.x is None or state.y is None or not math.isfinite(state.x) or not math.isfinite(state.y):
            raise ValueError('nonfinite valid coordinate')
        return (state.x,state.y)
    prefix=(xy(ego.states[-1]),*(xy(s) for s in future.states[:prefix_steps]))
    times=(sample.current_timestamp_s,*sample.future_timestamps_s[:prefix_steps])
    ids=[]; values=[]; masks=[]
    for track_id,t in sorted(targets.items()):
        if track_id==sid or track_id not in history or not any(history[track_id].valid_observation_mask):
            continue
        if not any(t.valid_future_mask): continue
        ids.append(track_id); masks.append(t.valid_future_mask)
        values.append(tuple(xy(s) if m else None for s,m in zip(t.states,t.valid_future_mask)))
    if not ids: return result('NO_HISTORY_CONDITIONED_AGENT_TARGETS',sid)
    digest=hashlib.sha256(json.dumps([sample.dataset,sample.split,sample.scenario_id,sample.source_digest,
        sample.coordinate_frame,sample.position_reference,sid,times,prefix],allow_nan=False,
        separators=(',',':')).encode()).hexdigest()
    # `timestamps_s` is the target axis; prefix includes the current knot.
    return result('LOGGED_EGO_PATH_SURROGATE',sid,sample.future_timestamps_s,
                  tuple(prefix),tuple(ids),tuple(values),tuple(masks),digest,times)


@dataclass(frozen=True)
class SignalChangeBracket:
    lane_id: str
    before: str
    after: str
    lo_s: float
    hi_s: float
    scope: str = 'AT_LEAST_ONE_LOGGED_SIGNAL_CHANGE_NOT_PROTOCOL_EVENT'


def sampled_signal_changes(sample: SceneForecastSample) -> tuple[SignalChangeBracket,...]:
    """Adjacent known samples with different states imply at least one change
    between them under the recorded discrete signal semantics. Not unique onset,
    event cause, issue/receipt, or actual ego visibility. Never bridge gaps.
    """
    if not sample.future_available: return ()
    history=() if sample.map_context_history is None else sample.map_context_history.signals
    rows={}; ambiguous=set()
    for r in (*history,*sample.future_signal_targets):
        key=(r.lane_id,r.timestep)
        if key in rows and rows[key]!=r: ambiguous.add(key)
        rows[key]=r
    axis=(*sample.history_timestamps_s,*sample.future_timestamps_s)
    current=len(sample.history_timestamps_s)-1
    out=[]
    for (lane,i),r in sorted(rows.items()):
        if i<=current or i>=len(axis): continue
        p=rows.get((lane,i-1))
        if p is None or (lane,i) in ambiguous or (lane,i-1) in ambiguous: continue
        if p.timestamp_s!=axis[i-1] or r.timestamp_s!=axis[i]: continue
        known={'LANE_STATE_ARROW_STOP','LANE_STATE_ARROW_CAUTION','LANE_STATE_ARROW_GO',
               'LANE_STATE_STOP','LANE_STATE_CAUTION','LANE_STATE_GO',
               'LANE_STATE_FLASHING_STOP','LANE_STATE_FLASHING_CAUTION'}
        if p.state not in known or r.state not in known:
            continue
        if p.state!=r.state: out.append(SignalChangeBracket(lane,p.state,r.state,p.timestamp_s,r.timestamp_s))
    return tuple(out)
