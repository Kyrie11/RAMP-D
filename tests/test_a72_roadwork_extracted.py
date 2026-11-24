"""Directory-only A72 ingress; compare the same source bytes with legacy ZIP readers."""
import io
import json
from pathlib import Path
import subprocess
import sys
import zipfile

import pytest
from PIL import Image

SCRIPTS = Path(__file__).resolve().parents[1] / 'scripts'


def run(script, *args):
    return subprocess.run([sys.executable, str(SCRIPTS / script), *map(str, args)],
                          capture_output=True, text=True)


def image_bytes(mode, fmt):
    out = io.BytesIO()
    Image.new(mode, (12, 10)).save(out, format=fmt)
    return out.getvalue()


@pytest.fixture
def dataset(tmp_path):
    root = tmp_path / 'ROADWork'
    root.mkdir()
    with (zipfile.ZipFile(root / 'annotations.zip', 'w') as ann,
          zipfile.ZipFile(root / 'images.zip', 'w') as images,
          zipfile.ZipFile(root / 'sem_seg_labels.zip', 'w') as masks):
        for split, number in [('train', 1), ('val', 2)]:
            name = f'pgh{number}_0001.jpg'
            record = {'images': [{'id': number, 'file_name': name, 'width': 12,
                                  'height': 10, 'gps': [40., -80. + number],
                                  'scene_level_tags': {'travel_alteration': ['Lane Shift']}}],
                      'categories': [{'id': 1, 'name': 'Cone'}],
                      'annotations': [{'id': number, 'image_id': number, 'category_id': 1,
                                       'bbox': [2, 2, 3, 4],
                                       'segmentation': [[2, 2, 5, 2, 5, 6, 2, 6]]}]}
            for suffix in ('', '_with_signs'):
                ann.writestr(f'annotations/instances_{split}_gps_split{suffix}.json',
                             json.dumps(record))
            images.writestr('images/' + name, image_bytes('RGB', 'JPEG'))
            masks.writestr(f'gtFine/{split}/{Path(name).stem}_labelIds.png', image_bytes('L', 'PNG'))
    return root


def extract(root):
    for path in root.glob('*.zip'):
        with zipfile.ZipFile(path) as archive:
            archive.extractall(root)
        path.unlink()


def test_directory_pipeline_matches_zip_audits_and_templates(dataset, tmp_path):
    zip_alignment = tmp_path / 'zip_alignment.json'
    zip_gps = tmp_path / 'zip_gps.json'
    zip_templates = tmp_path / 'zip_templates.jsonl'
    for script, args in (
        ('audit_roadwork.py', ['--root', dataset, '--output', zip_alignment, '--samples-per-split', 3]),
        ('audit_a57_roadwork.py', ['--annotations', dataset / 'annotations.zip', '--output', zip_gps]),
        ('export_a58_roadwork_templates.py', ['--annotations', dataset / 'annotations.zip', '--output', zip_templates, '--max-templates', 100]),
    ):
        result = run(script, *args)
        assert result.returncode == 0, result.stderr
    extract(dataset)
    out = tmp_path / 'directory_report'
    result = run('a72_roadwork_real_pipeline.py', '--dataset-root', dataset,
                 '--output-dir', out, '--max-templates', 100)
    assert result.returncode == 0, result.stderr + (out / 'pipeline_review.json').read_text()
    assert not list(dataset.rglob('*.zip'))
    review = json.loads((out / 'pipeline_review.json').read_text())
    assert review['status'] == 'DESCRIPTIVE_VISUAL_PIPELINE_COMPLETE'
    assert len(review['steps']) == 4 and all(s['returncode'] == 0 for s in review['steps'])
    old = json.loads(zip_alignment.read_text())
    new = json.loads((out / 'alignment.json').read_text())
    assert all(v['storage'] == 'directory' for v in new['archives'].values())
    for report in (old, new):
        report.pop('archives')
        for split in report['splits']:
            split.pop('annotation_member')
    assert new == old
    assert (out / 'gps_split.json').read_bytes() == zip_gps.read_bytes()
    assert (out / 'roadwork_templates.jsonl').read_bytes() == zip_templates.read_bytes()
    auxiliary = [json.loads(line) for line in (out / 'roadwork_auxiliary.jsonl').read_text().splitlines()]
    assert len(auxiliary) == 1 and all(v == 0 for v in auxiliary[0]['formal_label_masks'].values())
    assert not (out / 'roadwork_quarantine.jsonl').read_text()


def test_pipeline_does_not_fall_back_to_zip(dataset, tmp_path):
    out = tmp_path / 'report'
    result = run('a72_roadwork_real_pipeline.py', '--dataset-root', dataset, '--output-dir', out)
    assert result.returncode != 0 and 'MISSING_EXTRACTED_ROADWORK_DIRECTORIES' in result.stderr
    assert all(str(dataset / name) in result.stderr for name in ('annotations', 'images', 'gtFine'))
    assert not out.exists()


@pytest.mark.parametrize('duplicate', [False, True])
def test_a57_rejects_missing_or_duplicate_sign_annotations(dataset, tmp_path, duplicate):
    extract(dataset)
    target = dataset / 'annotations' / 'instances_train_gps_split_with_signs.json'
    if duplicate:
        other = target.parent / 'duplicate' / target.name
        other.parent.mkdir()
        other.write_bytes(target.read_bytes())
    else:
        target.unlink()
    result = run('audit_a57_roadwork.py', '--annotations', dataset / 'annotations',
                 '--output', tmp_path / 'gps.json')
    assert result.returncode != 0 and 'missing/ambiguous ' + target.name in result.stderr
