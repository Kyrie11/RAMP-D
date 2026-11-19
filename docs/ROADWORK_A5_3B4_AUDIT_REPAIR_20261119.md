# ROADWork A5/3b-4 alignment-audit repair (2026-11-19)

## Scientific scope and invariant

This patch changes **only** `scripts/audit_roadwork.py`, its regression tests, and this note. The manuscript and planner, GPS train/val partition, all-pairs COCO inventories, validation rules, output `--root/--samples-per-split/--output/--plot` arguments, output schema, and success status `BOUNDED_ROADWORK_ALIGNMENT_PASS` remain intact.

RAMP-D's actual research problem is goal-conditioned safe continuation with uncertain rule effectivity/notification and partially observable actors; ROADWork provides visual work-zone objects, signs, and scene context. It does **not** contain authoritative traffic-rule issue/receipt/effective times or a counterfactual response dataset. The three scene archives are sufficient for this bounded *image/label* audit. `traj_images.zip` and `traj_annotations.zip` are separate and intentionally unused; camera-derived travelled paths are not certified safe or universal available routes.

ROADWork's official GitHub README (`https://github.com/anuragxel/roadwork-dataset`) documents the `instances_{train,val}_gps_split.json` family, COCO-like instance fields, `gtFine/train` and `gtFine/val` with `*_labelIds.png` labels and scene extraction beneath `/scene`, `/scene/sem_seg`. The custom root layout `/data0/senzeyu2/dataset/ROADWork/{annotations,images,gtFine}` is also supported without copying or reorganizing datasets.

## Problems addressed

1. The earlier file index resolved all masks by basename using `unique(idx,name)`. Duplicate basename keys across splits can be falsely rejected, and a unique wrong-split match can be falsely accepted. The new matcher uses the official `train`/`val` directory when present; only genuinely flat legacy layouts use basename fallback. It handles duplicate image basenames in separate split directories without silently matching ambiguous files.
2. The original script has an `except` block that prints only `ERROR` to stdout. The revised script also prints a concise reason to stderr and includes a bounded Python traceback, root, and layout hint in the JSON error report. This exposes data/schema errors without hiding them.
3. The sampled semantic mask remains scalar; the pixel counter uses a fast histogram for `L`/`P` and a compatible `get_flattened_data`/`getdata` branch for 16-bit `I;16` modes across Pillow versions.
4. Plotting is done on thumbnail-resolution images, keeping overlays consistent and avoiding unnecessary full-resolution drawing. Every declared COCO image and mask still needs a resolvable file, but only the requested sample is decoded and dimension-checked.
5. Invalid metadata, missing masks, wrong-split masks, train/val filename overlap, out-of-image bounding boxes, and non-scalar labels are **not** suppressed. The `REVIEW_REQUIRED_BBOX_EXTENTS` status still fails the acceptance command by design.

## Test evidence and limitation

- Uploaded original ZIP: `python scripts/verify_release.py` produced `RELEASE_INTEGRITY_PASS: 270 files hashed, 175 source files present` on an untouched extraction.
- After modifying script: **11 ROADWork unit tests pass**, including old ZIP/extracted/missing-mask checks, same-stem train/val masks, wrong-split rejection, duplicated image basenames, 16-bit masks and diagnostics.
- Isolated Phase6C dependency-free gate: **172 passed**; this includes ROADWork and unrelated model/data/rule regression tests. No MPFR-backed native core was substituted.
- The server path `/data0/senzeyu2/dataset/ROADWork` is inaccessible in this environment. The exact original `ERROR` cannot be attributed to a specific exception without the original `reports/a5_3b4_roadwork.json`. This release is not represented as a real ROADWork full-data audit pass.

## Server acceptance (use a NEW unpack directory)

```bash
mkdir -p /home/senzeyu2/code/RAMP-D_roadwork_audit_fix
cd /home/senzeyu2/code/RAMP-D_roadwork_audit_fix
unzip -q /path/to/RAMP-D_ROADWork_Audit_Fix_20261119.zip
python scripts/verify_release.py
python scripts/audit_roadwork.py \
    --root /data0/senzeyu2/dataset/ROADWork \
    --samples-per-split 6 \
    --output reports/a5_3b4_roadwork.json \
    --plot reports/a5_3b4_roadwork.png
python - <<'PY'
import json
x=json.load(open('reports/a5_3b4_roadwork.json'))
print('status:', x.get('status'))
print('reason:', x.get('reason', '(none)'))
print('\n'.join(x.get('traceback', [])[-6:]))
PY
```

Interpretation: `BOUNDED_ROADWORK_ALIGNMENT_PASS` means only that the declared GPS split metadata and bounded sampled pixel alignment checks pass. `REVIEW_REQUIRED_BBOX_EXTENTS` demands review of out-of-bounds COCO boxes; it must not be reported as PASS. `ERROR` includes an explicit failure cause in JSON/stderr. Do **not** alter source manifests in an existing worktree to hide a mismatch: the manifest in this *new* release lists the actual new source hashes.
