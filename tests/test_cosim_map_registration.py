import pytest
from rampd_core.cosim_map_registration import fit_landmarks,inventory

def points():
    a=[(0,0),(1,0),(0,1),(2,3),(4,1),(2,0)]
    return [dict(id=str(i),split='fit' if i<3 else 'holdout',carla_xy=[x,y],sumo_xy=[x+5,-y+2]) for i,(x,y) in enumerate(a)]
def test_reflection():
    r=fit_landmarks(points());assert r['determinant']==pytest.approx(-1);assert r['holdout_max_m']<1e-10;assert not r['cosim_verified']
def test_holdout_bad():
    p=points();p[-1]['sumo_xy'][0]+=2.5;assert fit_landmarks(p)['status']=='REVIEW_MAP_REGISTRATION'
def test_noncollinear():
    p=points();p[2]['carla_xy']=[2,0]
    with pytest.raises(ValueError):fit_landmarks(p)
def test_inventory(tmp_path):
    x=tmp_path/'x.xodr';n=tmp_path/'n.xml';x.write_text('<OpenDRIVE><road id="1"/></OpenDRIVE>');n.write_text('<net><edge id="1"><lane id="l"/></edge></net>');r=inventory(x,n);assert r['roads']==1 and r['sumo_lanes']==1 and not r['shared_resource_verified']
