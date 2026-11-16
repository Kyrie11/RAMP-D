"""Strict source accounting: a dataset bit never becomes a proof label."""
from rampd_core.supervision_inventory import supervision_inventory
from rampd_core.scene_schema import SceneManifest, TrackState, SceneTrack, UnifiedScene


def test_logged_motion_is_available_but_every_unobserved_protocol_loss_masked():
    ts=(0.0,0.1,0.2)
    states=tuple(TrackState(t, t, 0., 0., 1., 0., True, observed=(i <= 1))
                 for i,t in enumerate(ts))
    scene=UnifiedScene(
        SceneManifest('womd_scenario','1.3.1','validation','s','fixture',ts,1,
                      'womd_global_xy','bounding_box_center',True,10),
        (SceneTrack('a','vehicle',states,to_predict=True),))
    inv=supervision_inventory(scene)['labels']
    assert inv['L_joint']['status']=='LOGGED_ACTION_ONLY'
    assert inv['L_joint']['benchmark_track_ids']==['a']
    assert inv['L_event']['status']=='UNAVAILABLE'
    assert inv['L_observation']['status']=='UNAVAILABLE'
    assert inv['L_viability']['unknown_is_not_negative']
    assert inv['L_occupancy']['status']=='NEEDS_GEOMETRY'
    assert inv['L_deadline']['status']=='PROTOCOL_AND_SCHEDULER_REQUIRED'
    assert inv['L_causal']['status']=='PAIRED_INTERVENTION_REQUIRED'


def test_test_split_has_no_logged_action_supervision():
    ts=(0.,0.1)
    states=(TrackState(0.,0.,0.,0.,1.,0.,True,observed=True),
            TrackState(.1,None,None,None,None,None,False,observed=False))
    scene=UnifiedScene(
        SceneManifest('av2_motion','2','test','test','fixture',ts,0,'av2_city_xy',
                      'bounding_box_center',False,10),
        (SceneTrack('focal','vehicle',states,to_predict=True,is_focal=True),))
    labels=supervision_inventory(scene)['labels']
    assert labels['L_joint']['status']=='UNAVAILABLE'
    assert labels['L_event']['status']=='UNAVAILABLE'
