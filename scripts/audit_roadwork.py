#!/usr/bin/env python3
"""Audit official ROADWork GPS-split scene annotations against images and labelIds.

Supports the unchanged extracted layout (annotations/, images/, gtFine/) and
official ZIP layout, with no pathway mixing. All image/mask members are checked
for existence, and a bounded deterministic sample is decoded. Zero-extent
COCO boxes remain present as source annotations, but are excluded from usable
bbox geometry and recorded as warnings. This is a visual alignment/inventory
audit, *not* a formal traffic-rule or safety-label generator.
"""
import argparse
from collections import Counter, defaultdict
from contextlib import ExitStack
import hashlib
import io
import json
import math
from pathlib import Path, PurePosixPath
import statistics
import sys
import traceback
import zipfile


def archive(root, names):
    for folder in (root, root / 'archives'):
        for name in names:
            p = folder / name
            if p.is_file():
                return p
    raise FileNotFoundError('missing archive: ' + ', '.join(names))


class DirectoryMember:
    def __init__(self, path, root):
        self.path = path
        self.filename = path.relative_to(root).as_posix()

    def is_dir(self):
        return False


class DirectoryReader:
    def __init__(self, root):
        self.root = root

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def infolist(self):
        return [DirectoryMember(p, self.root) for p in sorted(self.root.rglob('*')) if p.is_file()]

    def read(self, member):
        return member.path.read_bytes()


def locate(root, dirs, archives):
    # Explicit scene roots only: never fall through to pathways/scene-discovery archives.
    for name in dirs:
        p = root / name
        if p.is_dir():
            return p
    return archive(root, archives)


def reader(path):
    return DirectoryReader(path) if path.is_dir() else zipfile.ZipFile(path)


def index(z):
    out = defaultdict(list)
    for member in z.infolist():
        if not member.is_dir():
            out[PurePosixPath(member.filename).name].append(member)
    return out


def unique(idx, name):
    rows = idx.get(PurePosixPath(name).name, [])
    if len(rows) != 1:
        locations = [r.filename for r in rows[:5]]
        raise ValueError(f'expected unique archive member {name}, got {len(rows)}; candidates={locations}')
    return rows[0]


def _parts(name):
    """Reject unsafe/ambiguous embedded paths in untrusted COCO metadata."""
    if not isinstance(name, str) or not name or '\\' in name:
        raise ValueError(f'invalid COCO image filename {name!r}')
    path = PurePosixPath(name)
    if path.is_absolute() or '..' in path.parts:
        raise ValueError(f'unsafe COCO image filename {name!r}')
    return path.parts


def member_for_image(idx, file_name, split):
    """Resolve image by actual COCO filename, without silently picking a duplicate.

    Official images.zip is flat. The source can also contain image split dirs;
    in that case a basename alone is not enough to establish alignment.
    """
    parts = _parts(file_name)
    if any(q in parts[:-1] for q in ('train','val') if q != split):
        raise ValueError(f'COCO filename points to contrary split: {file_name}')
    rows = idx.get(parts[-1], [])
    if len(rows) == 1:
        member = rows[0]
        dirs = PurePosixPath(member.filename).parts[:-1]
        if any(s in dirs for s in ('train', 'val') if s != split):
            raise ValueError(f'missing {split} image: {file_name}; exists only in {member.filename}')
        return member
    if not rows:
        raise ValueError(f'missing image for {split}: {file_name}')
    # Reject contrary split before any suffix resolution.
    rows = [r for r in rows if not any(q in PurePosixPath(r.filename).parts[:-1] for q in ('train','val') if q != split)]
    if not rows:
        raise ValueError(f'missing {split} image: {file_name}')
    # If full/relative COCO path is available, prefer an exact suffix match.
    if len(parts) > 1:
        path_matches = [r for r in rows if tuple(PurePosixPath(r.filename).parts[-len(parts):]) == parts]
        if len(path_matches) == 1:
            return path_matches[0]
        if path_matches:
            rows = path_matches
    # An actual split directory is a valid discriminator only when unique.
    split_matches = [r for r in rows if split in PurePosixPath(r.filename).parts[:-1]]
    if len(split_matches) == 1:
        return split_matches[0]
    raise ValueError(f'ambiguous image for {split}: {file_name}; matches={[r.filename for r in rows[:6]]}')


def member_for_mask(idx, name, split):
    """Match labelIds in the correct GPS split (or a truly flat legacy layout).

    The old basename-only matcher could silently pair train to val when names
    collide; conversely, it rejected otherwise unambiguous split-local files.
    """
    rows = idx.get(name, [])
    split_rows = [r for r in rows if split in PurePosixPath(r.filename).parts[:-1] and not any(s in PurePosixPath(r.filename).parts[:-1] for s in ('train','val') if s != split)]
    other_rows = [r for r in rows if any(s in PurePosixPath(r.filename).parts[:-1]
                                      for s in ('train', 'val') if s != split)]
    if len(split_rows) == 1:
        return split_rows[0]
    if len(split_rows) > 1:
        raise ValueError(f'ambiguous {split} labelIds: {name}; matches={[r.filename for r in split_rows[:6]]}')
    if other_rows:
        raise ValueError(f'missing {split} labelIds: {name}; exists only in other split: '
                         f'{[r.filename for r in other_rows[:4]]}')
    if len(rows) == 1:  # ZIP/legacy layout without explicit train/val directories
        return rows[0]
    raise ValueError(f'expected unique archive member {name} in {split}, got {len(rows)}; '
                     f'candidates={[r.filename for r in rows[:6]]}')


def unique_ids(rows, key):
    out = {}
    for row in rows:
        k = row[key]
        if k in out:
            raise ValueError(f'duplicate {key}: {k}')
        out[k] = row
    return out


def positive_int(x):
    return type(x) is int and x > 0


def _pixel_counts(mask):
    # Fast 8-bit palette histogram; Pillow getcolors() may reject I;16.
    if mask.mode in ('L', 'P'):
        colors = mask.getcolors(maxcolors=256)
        if colors is not None:
            return {int(value): int(count) for count, value in colors}
    values = mask.get_flattened_data() if hasattr(mask, 'get_flattened_data') else mask.getdata()
    return dict(Counter(values))


def audit(root: Path, sample_per_split=6, plot=None):
    from PIL import Image, ImageDraw

    if type(sample_per_split) is not int or sample_per_split <= 0:
        raise ValueError('positive sample required')
    root = Path(root)
    files = {
        'annotations': locate(root, ('annotations', 'scene/annotations'), ('annotations.zip',)),
        'images': locate(root, ('images', 'scene/images'), ('images.zip',)),
        'semantic': locate(root, ('gtFine', 'scene/gtFine', 'scene/sem_seg/gtFine', 'sem_seg/gtFine'),
                           ('sem_seg_labels.zip', 'sem_seg_lables.zip')),
    }
    out = {
        'status': 'ERROR',
        'scope': 'GPS_SPLIT_METADATA_AND_BOUNDED_PIXEL_ALIGNMENT_ONLY',
        'archives': {k: {'path': str(p), 'bytes': p.stat().st_size if p.is_file() else None,
                         'storage': 'directory' if p.is_dir() else 'zip'} for k, p in files.items()},
        'splits': [], 'formal_rule_labels_generated': False,
        'metric_resource_geometry_generated': False, 'traffic_flow_labels_generated': False,
        'semantic_class_mapping_verified': False,
        'event_time_labels_generated': False, 'full_geographic_leakage_checked': False,
    }
    panels = []
    sets = {}
    with ExitStack() as ctx:
        za, zi, zs = (ctx.enter_context(reader(files[k])) for k in ('annotations', 'images', 'semantic'))
        ia, ii, iss = map(index, (za, zi, zs))
        for split in ('train', 'val'):
            member = unique(ia, f'instances_{split}_gps_split.json')
            raw = za.read(member)
            data = json.loads(raw)
            images = unique_ids(data['images'], 'id')
            categories = unique_ids(data['categories'], 'id')
            anns = unique_ids(data['annotations'], 'id')
            if not images or not categories or not anns:
                raise ValueError(f'empty official {split} split')
            names = {}
            image_members = {}
            mask_members = {}
            imfields = Counter()
            anfields = Counter()
            percat = Counter()
            imagecats = defaultdict(set)
            usable_cats = defaultdict(set)
            usable_percat = Counter()
            sizes = defaultdict(list)
            byimage = defaultdict(list)
            segtypes = Counter()
            pairs = Counter()
            degenerate_bbox_examples = []
            usable_bbox_geometry_count = 0
            for image_id, image_record in images.items():
                if not positive_int(image_record['width']) or not positive_int(image_record['height']):
                    raise ValueError(f'invalid {split} image size {image_id}')
                file_name = image_record['file_name']
                name = _parts(file_name)[-1]
                if name in names:
                    raise ValueError(f'duplicate {split} filename {name}')
                if split == 'val' and name in sets.get('train', set()):
                    raise ValueError(f'GPS split exact filename overlap: {name}')
                names[name] = image_id
                image_members[name] = member_for_image(ii, file_name, split)
                mask_members[name] = member_for_mask(iss, PurePosixPath(name).stem + '_labelIds.png', split)
                imfields.update(image_record.keys())
            for ann in anns.values():
                image_id, category_id = ann['image_id'], ann['category_id']
                if image_id not in images or category_id not in categories:
                    raise ValueError(f'{split} annotation id={ann["id"]}: invalid image/category reference '
                                     f'{image_id}/{category_id}')
                image_record = images[image_id]
                category = categories[category_id]['name']
                box = ann['bbox']
                if (not isinstance(box, (list, tuple)) or len(box) != 4
                        or any(not isinstance(x, (float, int)) or isinstance(x, bool)
                               or not math.isfinite(x) for x in box)):
                    raise ValueError(f'{split} annotation id={ann["id"]}: invalid bbox {box!r}')
                x, y, w, h = box
                # Zero-width or zero-height annotations can occur at cropped image
                # boundaries. They have no bbox geometry, and MUST NOT be silently
                # expanded into obstacles or silently removed from source counts.
                # Negative extents remain malformed metadata and are rejected.
                if w < 0 or h < 0:
                    raise ValueError(f'{split} annotation id={ann["id"]}: negative bbox extent {box}')
                degenerate = (w == 0 or h == 0)
                outside = (x < 0 or y < 0 or
                           x + w > image_record['width'] + 1e-6 or
                           y + h > image_record['height'] + 1e-6)
                if outside:
                    pairs['bbox_outside_image'] += 1
                if degenerate:
                    pairs['bbox_zero_extent'] += 1
                    if len(degenerate_bbox_examples) < 50:
                        degenerate_bbox_examples.append({
                            'annotation_id': ann['id'], 'image_id': image_id,
                            'file_name': image_record['file_name'],
                            'category_id': category_id, 'category': category,
                            'bbox': list(box),
                            'image_size': [image_record['width'], image_record['height']],
                            'source_area': ann.get('area'),
                            'outside_image': outside,
                        })
                # Source instance counts and co-occurrences preserve *all* original
                # annotations, including malformed geometry (for transparency).
                percat[category] += 1
                imagecats[image_id].add(category)
                byimage[image_id].append(ann)
                if not degenerate and not outside:
                    usable_bbox_geometry_count += 1
                    usable_cats[image_id].add(category)
                    usable_percat[category] += 1
                    sizes[category].append(w * h / (image_record['width'] * image_record['height']))
                anfields.update(ann.keys())
                seg = ann.get('segmentation')
                segtypes['polygon' if isinstance(seg, list) and seg else 'rle'
                         if isinstance(seg, dict) else 'missing_or_empty'] += 1
            for values in imagecats.values():
                cats = sorted(values)
                for j, left in enumerate(cats):
                    for right in cats[j + 1:]:
                        pairs[(left, right)] += 1
            usable_pairs = Counter(pair for values in usable_cats.values()
                                   for i,left in enumerate(sorted(values))
                                   for pair in ((left,right) for right in sorted(values)[i+1:]))
            keys = sorted(names)
            count = min(sample_per_split, len(keys))
            selected = [keys[i * len(keys) // count] for i in range(count)]
            samples = []
            for name in selected:
                image_record = images[names[name]]
                with Image.open(io.BytesIO(zi.read(image_members[name]))) as src:
                    src.load()
                    image = src.convert('RGB')
                if image.size != (image_record['width'], image_record['height']):
                    raise ValueError(f'{split} image metadata size mismatch: {name} '
                                     f'expected {(image_record["width"], image_record["height"])}, got {image.size}')
                with Image.open(io.BytesIO(zs.read(mask_members[name]))) as src:
                    src.load()
                    mask_size, mask_mode, extrema = src.size, src.mode, src.getextrema()
                    if mask_mode not in ('L', 'P', 'I', 'I;16', 'I;16B', 'I;16L'):
                        raise ValueError(f'{split} labelIds must be scalar or palette indices: {name} ({mask_mode})')
                    hist = _pixel_counts(src)
                    if sum(hist.values()) != mask_size[0]*mask_size[1] or any(type(k) is not int or not 0 <= k <= 65535 for k in hist):
                        raise ValueError(f'{split} invalid scalar labelIds histogram: {name}')
                if mask_size != image.size:
                    raise ValueError(f'{split} image / labelIds size mismatch: {name} '
                                     f'{image.size} vs {mask_size}')
                samples.append({'image': name, 'size': list(image.size), 'mask_mode': mask_mode,
                                'mask_extrema': extrema, 'mask_pixel_counts': hist,
                                'mask_ids_outside_uint8': sorted(k for k in hist if k > 255),
                                'annotations': len(byimage[image_record['id']])})
                if plot is not None:
                    # Draw after resizing so boxes remain visible and memory use stays bounded.
                    full_w, full_h = image.size
                    image.thumbnail((480, 270))
                    scale_x, scale_y = image.width / full_w, image.height / full_h
                    draw = ImageDraw.Draw(image)
                    for ann in byimage[image_record['id']]:
                        x, y, w, h = ann['bbox']
                        if w == 0 or h == 0 or x < 0 or y < 0 or x+w > full_w+1e-6 or y+h > full_h+1e-6:  # no usable geometry
                            continue
                        draw.rectangle((x * scale_x, y * scale_y, (x+w) * scale_x,
                                        (y+h) * scale_y), outline='yellow', width=1)
                        draw.text((max(0, x * scale_x), max(0, y * scale_y - 11)),
                                  str(categories[ann['category_id']]['name'])[:24], fill='yellow')
                    panels.append((split, name, image))
            sets[split] = set(names)
            out['splits'].append({
                'split': split, 'annotation_member': member.filename,
                'annotation_sha256': hashlib.sha256(raw).hexdigest(),
                'images': len(images), 'annotations': len(anns),
                'categories': sorted(set(c['name'] for c in categories.values())),
                'category_instances': dict(percat),
                'geometry_usable_category_instances': dict(usable_percat),
                'geometry_usable_cooccurrence_image_counts': [{'categories': list(k), 'images': v} for k,v in sorted(usable_pairs.items())],
                'geometry_usable_category_image_counts': dict(Counter(c for v in usable_cats.values() for c in v)),
                'category_image_counts': dict(Counter(c for v in imagecats.values() for c in v)),
                'median_relative_bbox_area': {k: statistics.median(v) for k, v in sizes.items()},
                'cooccurrence_image_counts': [{'categories': list(k), 'images': v} for k, v
                                               in sorted((k, v) for k, v in pairs.items() if isinstance(k, tuple))],
                'bbox_outside_image': pairs['bbox_outside_image'],
                'bbox_zero_extent': pairs['bbox_zero_extent'],
                'bbox_zero_extent_examples': degenerate_bbox_examples,
                'bbox_zero_extent_examples_truncated': max(0, pairs['bbox_zero_extent'] - len(degenerate_bbox_examples)),
                'bbox_geometry_usable': usable_bbox_geometry_count,
                'bbox_geometry_excluded': len(anns) - usable_bbox_geometry_count,
                'image_fields': dict(imfields), 'annotation_fields': dict(anfields),
                'segmentation_types': dict(segtypes), 'decoded_samples': samples,
            })
        overlap = sorted(sets['train'] & sets['val'])
        out['exact_filename_overlap'] = overlap
        if overlap:
            raise ValueError('GPS split exact filename overlap')
        out['data_quality_warnings'] = [
            f'{s["split"]}: {s["bbox_zero_extent"]} source annotations have zero-width or '
            'zero-height bbox; retained in instance counts, excluded from geometric '
            'area statistics and box overlays. Do not promote to obstacles.'
            for s in out['splits'] if s['bbox_zero_extent']
        ]
        # The PASS status certifies the narrow image/mask metadata alignment
        # audit, NOT complete validity of every individual COCO bounding box.
        # Positive-extent boxes outside an image, or zero-extent boxes with
        # coordinates outside it, still require a separate review.
        out['status'] = ('REVIEW_REQUIRED_BBOX_EXTENTS' if any(s['bbox_outside_image'] for s in out['splits'])
                         else 'BOUNDED_ROADWORK_ALIGNMENT_PASS')
    if plot is not None:
        canvas = Image.new('RGB', (960, 300 * ((len(panels) + 1) // 2)), '#20252b')
        draw = ImageDraw.Draw(canvas)
        for k, (split, name, image) in enumerate(panels):
            x = (k % 2) * 480
            y = (k // 2) * 300
            canvas.paste(image, (x, y + 25))
            draw.text((x + 4, y + 4), f'{split}: {name}'[:75], fill='white')
        plot.parent.mkdir(parents=True, exist_ok=True)
        canvas.save(plot)
    return out


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--samples-per-split', type=int, default=6)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--plot', type=Path)
    args = parser.parse_args()
    try:
        out = audit(args.root, args.samples_per_split, args.plot)
    except Exception as exc:
        out = {'status': 'ERROR', 'scope': 'GPS_SPLIT_METADATA_AND_BOUNDED_PIXEL_ALIGNMENT_ONLY',
               'reason': f'{type(exc).__name__}: {exc}',
               'traceback': traceback.format_exc(limit=8).splitlines(),
               'root': str(args.root),
               'source_discovery_hint': ('Expected annotations/, images/, gtFine/ extracted from '
                                         'annotations.zip, images.zip, sem_seg_labels.zip.')}
        print(f"ROADWORK ERROR: {out['reason']}; details: {args.output}", file=sys.stderr)
    for warning in out.get('data_quality_warnings', []):
        print(f'ROADWORK DATA QUALITY WARNING: {warning}', file=sys.stderr)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(out, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    print(out['status'])
    return 0 if out['status'] == 'BOUNDED_ROADWORK_ALIGNMENT_PASS' else 4


if __name__ == '__main__':
    raise SystemExit(main())
