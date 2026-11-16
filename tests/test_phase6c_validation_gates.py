"""Evidence gates and per-scene failure reporting: no false PASS from CTest 0 tests."""
from __future__ import annotations
from dataclasses import replace
from pathlib import Path
import runpy
import subprocess
import sys
from types import SimpleNamespace

from rampd_core.scene_schema import SceneManifest, TrackState, SceneTrack, UnifiedScene


def test_native_ctest_requires_nonempty_discovery(tmp_path: Path):
    project = tmp_path / 'empty_build'
    project.mkdir()
    (project / 'CTestTestfile.cmake').write_text('# zero tests\n')
    log = tmp_path / 'native.log'
    check = Path(__file__).resolve().parents[1] / 'scripts/check_native_ctest.py'
    process = subprocess.run([sys.executable, str(check), str(project),
                              '--log', str(log)], capture_output=True, text=True)
    assert process.returncode == 2
    assert 'missing mandatory native tests' in log.read_text()


def test_dataset_gate_preserves_previous_pass_rows_when_second_sample_errors():
    evaluate = runpy.run_path(str(Path(__file__).resolve().parents[1] / 'scripts/evaluate_phase6c.py'))
    ts=(0.0, 0.1, 0.2, 0.3)
    states=tuple(TrackState(x, x, 0., 0., 1., 0., True, observed=(i <= 1))
                 for i,x in enumerate(ts))
    manifest=SceneManifest('womd_scenario','1.3.1','validation','ok','example.tfrecord',
                           ts,1,'womd_global_xy','bounding_box_center',True,10.)
    good=UnifiedScene(manifest,(SceneTrack('agent','vehicle',states,to_predict=True),))
    bad=replace(good, manifest=replace(manifest, scenario_id='bad'),
                tracks=(replace(good.tracks[0],states=states[:-1]),))
    def parsed(scene):
        return SimpleNamespace(scene=scene, scenario_id=scene.manifest.scenario_id,
                               source_file='example.tfrecord', record_index=0,
                               content_sha256='0'*64, record_sha256='1'*64, source_file_sha256='0'*64,
                               scenario_content_sha256='2'*64,
                               source_schema='synthetic',parser_version='test',
                               map_file=None,map_content_sha256=None)
    output, ids=evaluate['one_split']('womd','validation',iter((parsed(good),parsed(bad))))
    assert output['status'] == 'ERROR'
    assert len(output['samples']) == 1 and output['samples'][0]['scoreable_future_rows'] == 1
    assert output['failure_cases'][0]['scenario_id'] == 'bad'
    assert ids == {'ok','bad'}
