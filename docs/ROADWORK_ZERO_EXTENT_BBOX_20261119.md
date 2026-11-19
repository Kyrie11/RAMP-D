# ROADWork zero-extent COCO bbox audit compatibility (2026-11-19)

## Confirmed failure and scope

The real-data report shows an annotation-level rejection, not missing archives:

```
val annotation id=17793: nonpositive bbox extent [1920.0, 502.85, 0.0, 0.2]
```

This annotation has bbox format `[x,y,w,h]` with `w=0`; it cannot represent a positive-area image-space rectangle. The observed `x=1920` may lie on the image right edge **if and only if** that image reports width 1920. The failure is in `scripts/audit_roadwork.py`, not proof that `images/` or `gtFine/` is broken. The actual image dimensions, source `area`, and segmentation content for ID 17793 require the server's original annotation JSON to establish. We do **not** assert why the upstream annotation acquired zero width.

The audit remains a *GPS-split metadata, path existence, and bounded sample image/mask alignment audit*. It is not a COCO annotation geometry certification, collision-proof source, or traffic rule label generator. The script does not import annotations into RAMP-D's 2D/3D obstacle or certified resource geometry.

## Data handling contract (no silent data editing)

- Preserve all official JSON bytes; do not mutate original annotations, crop images, inject positive widths, clamp coordinates, or recreate missing boxes.
- Preserve all source `images`, `annotations`, `category_instances`, category co-occurrence, split boundaries, and original `annotation_sha256` semantics (hash of JSON input).
- For bbox with `w == 0 or h == 0` (but both dimensions nonnegative and finite), count it in `bbox_zero_extent` and report up to 50 original annotation IDs/filenames/boxes/image sizes/source areas. Do **not** use it for positive-area bbox statistics or draw a 1-pixel rectangle. `bbox_geometry_excluded` counts the affected records; its companion `bbox_geometry_usable` counts positive extents inside the image.
- `median_relative_bbox_area` contains medians **only of usable positive-area, in-image boxes**. Categories with no usable boxes are absent from this geometry-specific summary. This is deliberate, rather than passing `area=0` as a valid geometry example.
- Source `annotations`, `category_instances`, `category_image_counts`, `segmentation_types`, image-level sample `annotations` counts remain unchanged. `bbox_zero_extent_examples` is a bounded preview, not a complete downstream filter list.
- Reject negative extents, wrong image/category IDs, non-finite/ill-shaped bbox, missing images/masks, and train/val leakage exactly as before.
- If any bbox has coordinates outside the image, keep `REVIEW_REQUIRED_BBOX_EXTENTS` and exit code 4. The exact boundary `[x=W,w=0]` is *not* outside by itself; it is still zero-extent geometry and explicitly reported. Coordinates beyond the boundary with zero width are outside and require review.
- When only in-image zero-extent boxes are found and path/sample consistency passes, retain existing `BOUNDED_ROADWORK_ALIGNMENT_PASS` and exit code 0 **with `data_quality_warnings`**. PASS here means only the narrowly defined alignment gate, not that every COCO bbox is usable. Warnings are printed to stderr for visibility.

This maintains a conservative separation between *source instances* and *usable bbox geometry*. A zero-width bbox does not prove there is no obstacle in the image; to use such an object for planning, a separately validated segmentation/perception/3D reconstruction with explicit uncertainty would be required. No formal rule change time, authoritative report timing or safety support is inferred from ROADWork annotations.

## Why the three original ZIPs need not be restored

This script gives priority to extracted `annotations/`, `images/`, and `gtFine/`; it searches ZIPs only when a matching extracted directory does not exist. Missing archives are irrelevant if extraction succeeded. A successful read of the val COCO annotation proves annotation JSON discovery/parsing, but **not** that every image/mask file has valid bytes. The audit verifies declared image/mask presence for all images, but decodes pixel dimensions for at most `--samples-per-split` per split. Re-download only if source files are missing/corrupt or authoritative archive-level SHA-256 provenance needs to be reestablished.

## Reproduce and inspect on the server

Unpack this patch as a **new release folder** so `verify_release.py` matches the updated source manifest. Keep the old checkout for reproducibility.

```
python scripts/verify_release.py
python -m pytest -q tests/test_phase6c_a53b3_roadwork.py
python scripts/audit_roadwork.py \
    --root /data0/senzeyu2/dataset/ROADWork \
    --samples-per-split 6 \
    --output reports/a5_3b4_roadwork.json \
    --plot reports/a5_3b4_roadwork.png
```

The command-line interface, output filename, `scope`, and existing `status` values are unchanged. Inspect:

```
python - <<'PY'
import json
report=json.load(open('reports/a5_3b4_roadwork.json'))
print(report['status'])
for split in report.get('splits',[]):
    print(split['split'], 'source annotations:', split['annotations'],
          'zero extents:', split['bbox_zero_extent'],
          'outside:', split['bbox_outside_image'],
          'usable geometry:', split['bbox_geometry_usable'])
    print('first zero examples:', split['bbox_zero_extent_examples'][:3])
print('warnings:', report.get('data_quality_warnings',[]))
PY
```

To inspect source annotation 17793 without changing it:

```
python - <<'PY'
import json
from pathlib import Path
folder=Path('/data0/senzeyu2/dataset/ROADWork/annotations')
files=list(folder.rglob('instances_val_gps_split.json'))
assert len(files)==1, f'expected one val GPS JSON, got {files}'
d=json.loads(files[0].read_text())
rows=[a for a in d['annotations'] if a.get('id')==17793]
assert len(rows)==1, f'found {len(rows)} records'
a=rows[0]
im=next(i for i in d['images'] if i['id']==a['image_id'])
print('image:', im['file_name'], 'size:', im['width'],im['height'])
print('bbox:',a['bbox'],'source area:',a.get('area'))
seg=a.get('segmentation')
print('segmentation type:',type(seg).__name__, 'nonempty:',bool(seg))
PY
```

## Local verification

- Synthetic test reproduces annotation `17793` exactly on an image with width `1920`, retains original annotation statistics, excludes it from bbox geometry, and generates sample plot without a 1px phantom object.
- Explicit regression tests cover zero-height, negative, zero-extent beyond image edge, positive bbox beyond edge, NaN, preexisting archive and extracted-directory behavior.
- These tests are **not** proof that the unseen real server data contains no other errors. If the next run returns another `ERROR` or `REVIEW_REQUIRED_BBOX_EXTENTS`, retain the report instead of suppressing that new finding.
