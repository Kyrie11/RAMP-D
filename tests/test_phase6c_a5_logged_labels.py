from dataclasses import replace
from rampd_core.scene_schema import SceneManifest,SceneTrack,TrackState,UnifiedScene
from rampd_core.phase6c import build_scene_forecast_sample
from rampd_core.map_context import MapContext,SignalRecord
from rampd_core.a5_logged_labels import factual_joint_labels,sampled_signal_changes


def sample():
    ts=(0.,.1,.2,.3)
    def track(name,valid,sd=False):
        return SceneTrack(name,'vehicle',tuple(TrackState(t,t if v else None,0. if v else None,
                    0.,1.,0.,v,observed=i<=1) for i,(t,v) in enumerate(zip(ts,valid))),is_sdc=sd)
    context=MapContext('womd_scenario','s','global',(),(
        SignalRecord(1,.1,'lane','LANE_STATE_STOP'),SignalRecord(2,.2,'lane','LANE_STATE_GO'),
        SignalRecord(3,.3,'lane','LANE_STATE_UNKNOWN')))
    scene=UnifiedScene(SceneManifest('womd_scenario','1.3.1','train','s','synthetic',ts,1,'global',
                      'bounding_box_center',True,10),
             (track('ego',(True,True,True,True),True),track('a',(True,True,True,False)),
              track('new',(False,False,True,True))),map_context=context)
    return build_scene_forecast_sample(scene)


def test_factual_prefix_and_joint_mask():
    s=sample(); label=factual_joint_labels(s,1)
    assert label.usable and label.ego_id=='ego' and label.actor_ids==('a',)
    assert label.ego_prefix_xy==((.1,0.),(.2,0.))
    assert label.ego_prefix_timestamps_s==(.1,.2)
    assert label.target_xy==(((.2,0.),None),) and label.valid_mask==((True,False),)
    assert label.ego_prefix_digest != factual_joint_labels(s,2).ego_prefix_digest


def test_no_focal_substitution_and_incomplete_ego_masked():
    s=sample(); h=tuple(replace(t,is_sdc=False,is_focal=True) if t.is_sdc else t for t in s.history_tracks)
    assert factual_joint_labels(replace(s,history_tracks=h),1).status=='NO_EXPLICIT_EGO'
    future=tuple(replace(t,valid_future_mask=(False,True)) if t.is_sdc else t for t in s.future_targets)
    assert factual_joint_labels(replace(s,future_targets=future),2).status=='INCOMPLETE_LOGGED_EGO_PREFIX'
    assert not factual_joint_labels(s,3).usable


def test_signal_change_is_auxiliary_only_and_never_gap_filled():
    s=sample(); rows=sampled_signal_changes(s)
    assert len(rows)==1 and (rows[0].lo_s,rows[0].hi_s)==(.1,.2)
    assert rows[0].scope=='AT_LEAST_ONE_LOGGED_SIGNAL_CHANGE_NOT_PROTOCOL_EVENT'
    assert not sampled_signal_changes(replace(s,future_signal_targets=s.future_signal_targets[1:]))
    conflict=replace(s.future_signal_targets[0],state='LANE_STATE_CAUTION')
    assert not sampled_signal_changes(replace(s,future_signal_targets=(*s.future_signal_targets,conflict)))


def test_sampled_occupancy_masks_missing_geometry_boundary_and_reference():
    from rampd_core.map_context import MapPrimitive,MapVertex
    from rampd_core.a5_sampled_occupancy import sampled_occupancy_labels
    s=sample()
    poly=MapPrimitive('p','crosswalk','polygon',tuple(MapVertex(x,y) for x,y in ((1,-1),(3,-1),(3,1),(1,1))))
    s=replace(s,map_context_history=replace(s.map_context_history,primitives=(poly,)))
    h=tuple(replace(t,states=tuple(replace(v,x=0.,length=.4,width=.4) for v in t.states)) if t.track_id=='ego' else t for t in s.history_tracks)
    fut=tuple(replace(t,states=(replace(t.states[0],x=2.,length=.4,width=.4),
                      replace(t.states[1],x=4.,length=.4,width=.4))) if t.track_id=='ego' else t for t in s.future_targets)
    s=replace(s,history_tracks=h,future_targets=fut)
    labels=sampled_occupancy_labels(s,(('ego','p'),('a','p')),boundary_buffer_m=.01)
    assert [(l.occupied,l.transition) for l in labels[:2]]==[(True,'sampled_entry'),(False,'sampled_exit')]
    assert all(l.occupied is None for l in labels[2:])
    assert all(l.occupied is None for l in sampled_occupancy_labels(replace(s,position_reference='rear_axle_center'),(('ego','p'),),boundary_buffer_m=.01))
    fut=tuple(replace(t,states=(replace(t.states[0],x=.8),t.states[1])) if t.track_id=='ego' else t for t in s.future_targets)
    rows=sampled_occupancy_labels(replace(s,future_targets=fut),(('ego','p'),),boundary_buffer_m=.01)
    assert rows[0].occupied is None and rows[1].transition is None
