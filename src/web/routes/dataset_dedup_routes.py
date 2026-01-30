from flask import Blueprint, jsonify, request
import os
import sys
import hashlib

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

bp = Blueprint('dataset_dedup', __name__)


@bp.route('/api/dataset/deduplicate_images', methods=['POST'])
def api_dataset_deduplicate_images():
    try:
        data = request.get_json() or {}
        project_path = data.get('project_path')
        dataset_name = data.get('dataset_name')
        dataset_path = data.get('dataset_path')
        keep_split = str(data.get('keep_split') or 'train').strip().lower()

        if not project_path or (not dataset_name and not dataset_path):
            return jsonify({'success': False, 'error': '缺少必要参数'})

        project_real = os.path.realpath(project_path)

        ds_candidates = []
        if dataset_path:
            ds_candidates.append(dataset_path)
        if dataset_name:
            ds_candidates.append(os.path.join(project_path, 'training', dataset_name))
            ds_candidates.append(os.path.join(project_path, 'datasets', dataset_name))

        ds_root = None
        for p in ds_candidates:
            if not p:
                continue
            rp = os.path.realpath(p)
            if not (rp == project_real or rp.startswith(project_real + os.sep)):
                continue
            if os.path.isdir(rp):
                ds_root = rp
                break

        if not ds_root:
            return jsonify({'success': False, 'error': '数据集不存在'})

        splits = ['train', 'val', 'test']
        if keep_split not in splits:
            keep_split = 'train'
        order = [keep_split] + [s for s in splits if s != keep_split]
        priority = {s: i for i, s in enumerate(order)}

        def file_md5(fp):
            h = hashlib.md5()
            with open(fp, 'rb') as f:
                for chunk in iter(lambda: f.read(8 * 1024 * 1024), b''):
                    h.update(chunk)
            return h.hexdigest()

        scanned = 0
        kept = {}
        dups = []
        errs = []

        for split in order:
            img_dir = os.path.join(ds_root, split, 'images')
            if not os.path.isdir(img_dir):
                continue
            for root, dirs, files in os.walk(img_dir):
                dirs.sort()
                files.sort()
                for fn in files:
                    if not fn.lower().endswith(('.jpg', '.jpeg', '.png', '.bmp')):
                        continue
                    img_path = os.path.join(root, fn)
                    try:
                        rel_noext = os.path.splitext(os.path.relpath(img_path, img_dir))[0]
                        md5 = file_md5(img_path)
                        scanned += 1
                        item = {'split': split, 'img': img_path, 'rel_noext': rel_noext, 'p': priority.get(split, 9999)}
                        prev = kept.get(md5)
                        if prev is None:
                            kept[md5] = item
                        else:
                            if item['p'] < prev['p']:
                                dups.append(prev)
                                kept[md5] = item
                            else:
                                dups.append(item)
                    except Exception as e:
                        errs.append({'path': img_path, 'error': str(e)})

        deleted_images = 0
        deleted_labels = 0
        for it in dups:
            try:
                if os.path.exists(it['img']):
                    os.remove(it['img'])
                    deleted_images += 1
            except Exception as e:
                errs.append({'path': it['img'], 'error': str(e)})
            rel_noext = it['rel_noext']
            split = it['split']
            for lp in (
                os.path.join(ds_root, split, 'labels', rel_noext + '.txt'),
                os.path.join(ds_root, 'labels', split, rel_noext + '.txt'),
                os.path.join(ds_root, 'auto_labels', split, rel_noext + '.txt'),
            ):
                try:
                    if os.path.exists(lp):
                        os.remove(lp)
                        deleted_labels += 1
                except Exception as e:
                    errs.append({'path': lp, 'error': str(e)})

        return jsonify({
            'success': True,
            'dataset_root': ds_root,
            'keep_split': keep_split,
            'scanned_images': scanned,
            'unique_images': len(kept),
            'duplicate_images': len(dups),
            'deleted_images': deleted_images,
            'deleted_label_files': deleted_labels,
            'errors': errs[:50],
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

