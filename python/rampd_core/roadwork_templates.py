"""Lossless image-level ROADWork template export; NO metric/rule labels."""
from collections import Counter
import hashlib,json

def template_from_manifest_row(row):
    if not row.get('group') or not row.get('source_annotation_sha256') or not row.get('source_split') or not row.get('file_name'):
        raise ValueError('grouped and provenance-bound ROADWork row required')
    objects=row.get('objects')
    if not isinstance(objects,list) or not all(isinstance(x,dict) and x.get('category') and x.get('bbox_usable') is True for x in objects):
        raise ValueError('invalid object geometry: quarantine instead of deleting objects')
    key={'source_image_id':row['image_id'], 'image_file':row['file_name'],
         'source_split':row['source_split'], 'source_group':row['group'],
         'source_annotation_sha256':row['source_annotation_sha256'],
         'scene_tags':row.get('scene_tags'), 'description':row.get('description'),
         'objects':[{k:o.get(k) for k in ('id','category','sign_subclass','attributes','bbox')} for o in objects]}
    digest=hashlib.sha256(json.dumps(key,sort_keys=True,ensure_ascii=False,default=str).encode()).hexdigest()
    return {'template_id':'rw_'+digest[:24], 'source':key,
            'object_count_by_class':dict(sorted(Counter(o['category'] for o in objects).items())),
            'physical_world_positions':None,'resource_geometry':None,'formal_traffic_rule':None,
            'authority_effectivity':None,'message_issue_receipt':None,
            'counterfactual_response':None,'teacher_safety_label':None,
            'status':'VISUAL_SEMANTICS_ONLY_NEEDS_CALIBRATED_WORLD_GENERATOR'}
