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
