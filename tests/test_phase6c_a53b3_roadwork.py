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
