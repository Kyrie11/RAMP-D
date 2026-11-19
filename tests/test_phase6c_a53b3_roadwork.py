import io,json,zipfile,importlib.util
from pathlib import Path
import pytest
from PIL import Image
spec=importlib.util.spec_from_file_location('roadwork',Path(__file__).resolve().parents[1]/'scripts/audit_roadwork.py');mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)

def make(root,*,bad_size=False,overlap=False):
    def image(fmt,size,mode):
        b=io.BytesIO();Image.new(mode,size).save(b,format=fmt);return b.getvalue()
    with zipfile.ZipFile(root/'annotations.zip','w') as a,zipfile.ZipFile(root/'images.zip','w') as i,zipfile.ZipFile(root/'sem_seg_labels.zip','w') as s:
        for split in ('train','val'):
            name=('train' if overlap else split)+'.jpg';d={'images':[{'id':1,'width':12,'height':10,'file_name':name}], 'categories':[{'id':1,'name':'cone'}],'annotations':[{'id':1,'image_id':1,'category_id':1,'bbox':[2,2,3,4],'segmentation':[[2,2,5,2,5,6,2,6]]}]}
            a.writestr(f'annotations/instances_{split}_gps_split.json',json.dumps(d))
            if overlap and split=='val':continue
            i.writestr('images/'+name,image('JPEG',(12,10),'RGB'))
            s.writestr(f'gtFine/{split}/{Path(name).stem}_labelIds.png',image('PNG',(11,10) if bad_size else (12,10),'L'))

def test_roadwork_consistent_archives_and_plot(tmp_path):
    make(tmp_path);p=tmp_path/'out.png';out=mod.audit(tmp_path,1,p)
    assert out['status']=='BOUNDED_ROADWORK_ALIGNMENT_PASS' and p.is_file()
    assert out['splits'][0]['category_instances']=={'cone':1}
    assert not out['formal_rule_labels_generated']

@pytest.mark.parametrize('kwargs,match',[({'bad_size':True},'size mismatch'),({'overlap':True},'overlap')])
def test_reject_bad_archive_pairs(tmp_path,kwargs,match):
    make(tmp_path,**kwargs)
    with pytest.raises(ValueError,match=match):mod.audit(tmp_path,1)

def test_extracted_layout_and_identical_stats(tmp_path):
    make(tmp_path); expected=mod.audit(tmp_path,1)
    for p in list(tmp_path.glob('*.zip')):
        with zipfile.ZipFile(p) as z: z.extractall(tmp_path)
        p.unlink()
    result=mod.audit(tmp_path,1,tmp_path/'preview.png')
    assert result['status']=='BOUNDED_ROADWORK_ALIGNMENT_PASS'
    assert all(x['storage']=='directory' for x in result['archives'].values())
    assert [{k:v for k,v in g.items() if k!='annotation_member'} for g in result['splits']]==[{k:v for k,v in g.items() if k!='annotation_member'} for g in expected['splits']]


def test_missing_mask_outside_sample_rejected(tmp_path):
    make(tmp_path)
    with zipfile.ZipFile(tmp_path/'sem_seg_labels.zip') as z: z.extractall(tmp_path)
    (tmp_path/'gtFine/val/val_labelIds.png').unlink()
    with pytest.raises(ValueError,match='unique archive member'): mod.audit(tmp_path,1)


def test_gps_split_masks_with_identical_stems_are_resolved_in_correct_split(tmp_path):
    """A train .jpg and val .png may have the same stem; do not cross-pair masks."""
    def jpg_or_png(fmt):
        out = io.BytesIO()
        Image.new('RGB', (12, 10), 'white').save(out, format=fmt)
        return out.getvalue()
    with (zipfile.ZipFile(tmp_path/'annotations.zip', 'w') as a,
          zipfile.ZipFile(tmp_path/'images.zip', 'w') as im,
          zipfile.ZipFile(tmp_path/'sem_seg_labels.zip', 'w') as sem):
        for split, ext, value in [('train', '.jpg', 11), ('val', '.png', 12)]:
            d = {'images': [{'id': 1, 'file_name': 'same'+ext, 'width': 12, 'height': 10}],
                 'categories': [{'id': 1, 'name': 'Cone'}],
                 'annotations': [{'id': 1, 'image_id': 1, 'category_id': 1,
                                  'bbox': [2, 2, 3, 4], 'segmentation': [[2, 2, 5, 6]]}]}
            a.writestr(f'annotations/instances_{split}_gps_split.json', json.dumps(d))
            im.writestr('images/same'+ext, jpg_or_png('JPEG' if ext == '.jpg' else 'PNG'))
            b = io.BytesIO()
            Image.new('L', (12, 10), value).save(b, 'PNG')
            sem.writestr(f'gtFine/{split}/same_labelIds.png', b.getvalue())
    result = mod.audit(tmp_path, 1)
    assert result['status'] == 'BOUNDED_ROADWORK_ALIGNMENT_PASS'
    assert result['splits'][0]['decoded_samples'][0]['mask_pixel_counts'] == {11: 120}
    assert result['splits'][1]['decoded_samples'][0]['mask_pixel_counts'] == {12: 120}


def test_reject_mask_present_only_in_wrong_split(tmp_path):
    make(tmp_path)
    # Delete the required train mask, leaving the val mask and an unrelated
    # train file with a different name. There must be no cross-split fallback.
    with zipfile.ZipFile(tmp_path/'sem_seg_labels.zip') as src:
        data = [(item.filename, src.read(item)) for item in src.infolist()
                if item.filename != 'gtFine/train/train_labelIds.png']
    with zipfile.ZipFile(tmp_path/'sem_seg_labels.zip', 'w') as dst:
        for path, raw in data:
            dst.writestr(path, raw)
        dst.writestr('gtFine/val/train_labelIds.png', data[0][1])
    with pytest.raises(ValueError, match='missing train labelIds'):
        mod.audit(tmp_path, 1)


def test_images_in_duplicate_split_directories_resolve_by_split(tmp_path):
    make(tmp_path)
    with zipfile.ZipFile(tmp_path/'images.zip') as src:
        old = [(item.filename, src.read(item)) for item in src.infolist()]
    with zipfile.ZipFile(tmp_path/'images.zip', 'w') as dst:
        for name, raw in old:
            dst.writestr('images/'+ ('train' if name.endswith('train.jpg') else 'val')
                         + '/' + Path(name).name, raw)
        # Collision with official image filename, outside its actual split.
        dst.writestr('images/val/train.jpg', old[0][1])
    assert mod.audit(tmp_path, 1)['status'] == 'BOUNDED_ROADWORK_ALIGNMENT_PASS'


def test_error_report_preserves_reason_traceback_and_exit_code(tmp_path, monkeypatch, capsys):
    make(tmp_path)
    (tmp_path/'annotations.zip').unlink()
    import sys
    out = tmp_path/'report.json'
    monkeypatch.setattr(sys, 'argv', ['audit_roadwork.py', '--root', str(tmp_path),
                                      '--output', str(out), '--samples-per-split', '1'])
    assert mod.main() == 4
    report = json.loads(out.read_text())
    assert report['status'] == 'ERROR'
    assert 'missing archive: annotations.zip' in report['reason']
    assert any('FileNotFoundError' in line for line in report['traceback'])
    assert 'missing archive' in capsys.readouterr().err


def test_16bit_label_ids_remain_scalar_without_rgb_conversion(tmp_path):
    make(tmp_path)
    with zipfile.ZipFile(tmp_path/'sem_seg_labels.zip') as src:
        data = [(item.filename, src.read(item)) for item in src.infolist()]
    with zipfile.ZipFile(tmp_path/'sem_seg_labels.zip', 'w') as dst:
        for name, raw in data:
            if name.endswith('train_labelIds.png'):
                out = io.BytesIO()
                Image.new('I;16', (12, 10), 256).save(out, 'PNG')
                raw = out.getvalue()
            dst.writestr(name, raw)
    result = mod.audit(tmp_path, 1)
    assert result['status'] == 'BOUNDED_ROADWORK_ALIGNMENT_PASS'
    assert result['splits'][0]['decoded_samples'][0]['mask_pixel_counts'] == {256: 120}


def test_reject_image_present_only_in_wrong_split(tmp_path):
    make(tmp_path)
    with zipfile.ZipFile(tmp_path/'images.zip') as src:
        images = [(item.filename, src.read(item)) for item in src.infolist()]
    with zipfile.ZipFile(tmp_path/'images.zip', 'w') as dst:
        for name, raw in images:
            dst.writestr('images/val/' + Path(name).name, raw)
    with pytest.raises(ValueError, match='missing train image'):
        mod.audit(tmp_path, 1)


def _replace_val_bbox(tmp_path, bbox, *, annotation_id=17793, width=12, height=10):
    """Inject an official-style val anomaly without changing the parser's inputs."""
    path = tmp_path / 'annotations.zip'
    with zipfile.ZipFile(path) as src:
        rows = [(member.filename, src.read(member)) for member in src.infolist()]
    with zipfile.ZipFile(path, 'w') as dst:
        for name, raw in rows:
            if name.endswith('instances_val_gps_split.json'):
                data = json.loads(raw)
                data['annotations'][0]['id'] = annotation_id
                data['annotations'][0]['bbox'] = bbox
                data['images'][0]['width'] = width
                data['images'][0]['height'] = height
                raw = json.dumps(data).encode()
            dst.writestr(name, raw)
    if (width, height) != (12, 10):
        for fname, entry, mode, fmt in (
            ('images.zip', 'images/val.jpg', 'RGB', 'JPEG'),
            ('sem_seg_labels.zip', 'gtFine/val/val_labelIds.png', 'L', 'PNG')):
            path = tmp_path / fname
            with zipfile.ZipFile(path) as src:
                rows = [(member.filename, src.read(member)) for member in src.infolist()]
            with zipfile.ZipFile(path, 'w') as dst:
                for name, raw in rows:
                    if name == entry:
                        stream = io.BytesIO()
                        Image.new(mode, (width, height)).save(stream, format=fmt)
                        raw = stream.getvalue()
                    dst.writestr(name, raw)


def test_zero_extent_at_exact_roadwork_boundary_does_not_fake_geometry(tmp_path):
    make(tmp_path)
    _replace_val_bbox(tmp_path, [1920.0, 502.85, 0.0, 0.2],
                      width=1920, height=1080)
    report = mod.audit(tmp_path, 1, tmp_path / 'audit.png')
    val = next(s for s in report['splits'] if s['split'] == 'val')
    assert report['status'] == 'BOUNDED_ROADWORK_ALIGNMENT_PASS'
    assert report['data_quality_warnings']
    assert val['annotations'] == 1 and val['category_instances'] == {'cone': 1}
    assert val['bbox_zero_extent'] == 1 and val['bbox_outside_image'] == 0
    assert val['bbox_geometry_usable'] == 0 and val['bbox_geometry_excluded'] == 1
    assert val['median_relative_bbox_area'] == {}
    assert val['decoded_samples'][0]['annotations'] == 1
    assert val['bbox_zero_extent_examples'][0]['annotation_id'] == 17793
    assert val['bbox_zero_extent_examples'][0]['bbox'] == [1920., 502.85, 0., .2]
    assert val['bbox_zero_extent_examples'][0]['image_size'] == [1920, 1080]
    assert (tmp_path / 'audit.png').is_file()


def test_zero_height_is_quality_warning_not_geometry(tmp_path):
    make(tmp_path)
    _replace_val_bbox(tmp_path, [2.0, 10.0, 2.0, 0.0])
    val = mod.audit(tmp_path, 1)['splits'][1]
    assert val['bbox_zero_extent'] == 1
    assert val['bbox_geometry_usable'] == 0
    assert val['bbox_outside_image'] == 0


def test_negative_bbox_remains_hard_error(tmp_path):
    make(tmp_path)
    _replace_val_bbox(tmp_path, [2., 2., -.1, 1.])
    with pytest.raises(ValueError, match='negative bbox extent'):
        mod.audit(tmp_path, 1)


def test_zero_bbox_outside_image_not_promoted_to_alignment_pass(tmp_path):
    make(tmp_path)
    _replace_val_bbox(tmp_path, [13., 3., 0., 1.])
    result = mod.audit(tmp_path, 1)
    assert result['status'] == 'REVIEW_REQUIRED_BBOX_EXTENTS'
    assert result['splits'][1]['bbox_zero_extent'] == 1
    assert result['splits'][1]['bbox_outside_image'] == 1


def test_positive_extent_outside_image_still_requires_review(tmp_path):
    make(tmp_path)
    _replace_val_bbox(tmp_path, [11., 2., 2., 1.])
    result = mod.audit(tmp_path, 1)
    assert result['status'] == 'REVIEW_REQUIRED_BBOX_EXTENTS'
    assert result['splits'][1]['bbox_zero_extent'] == 0
    assert result['splits'][1]['bbox_geometry_usable'] == 0


def test_nonfinite_bbox_remains_hard_error(tmp_path):
    make(tmp_path)
    _replace_val_bbox(tmp_path, [2., 2., float('nan'), 2.])
    with pytest.raises(ValueError, match='invalid bbox'):
        mod.audit(tmp_path, 1)
