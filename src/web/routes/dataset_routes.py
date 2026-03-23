from flask import Blueprint, jsonify, request, send_file, after_this_request
import os
import sys
import json
import yaml
import shutil
import zipfile
import tempfile
import hashlib
import random
from PIL import Image, ImageEnhance

# Ensure parent directory is in sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from managers.project_manager import ProjectManager
from managers.training_manager import TrainingManager
from ultralytics import YOLO

bp = Blueprint('dataset', __name__)
_person_review_model = None

def _get_person_review_model():
    global _person_review_model
    if _person_review_model is None:
        _person_review_model = YOLO('yolo11n.pt')
    return _person_review_model

def _resolve_dataset_root(project_path, dataset_name):
    candidates = [
        os.path.join(project_path, 'training', dataset_name),
        os.path.join(project_path, 'datasets', dataset_name),
    ]
    for p in candidates:
        if os.path.isdir(p):
            return p
    return None

def _load_dataset_names(ds_root):
    names = []
    yaml_path = os.path.join(ds_root, 'data.yaml')
    if not os.path.exists(yaml_path):
        yaml_path = os.path.join(ds_root, 'dataset.yaml')
    if os.path.exists(yaml_path):
        try:
            with open(yaml_path, 'r', encoding='utf-8') as f:
                y = yaml.safe_load(f) or {}
            raw_names = y.get('names')
            if isinstance(raw_names, list):
                names = [str(x) for x in raw_names]
            elif isinstance(raw_names, dict):
                pairs = []
                for k, v in raw_names.items():
                    try:
                        kk = int(k)
                    except Exception:
                        continue
                    pairs.append((kk, str(v)))
                if pairs:
                    names = [v for _, v in sorted(pairs, key=lambda x: x[0])]
                else:
                    names = [str(v) for v in raw_names.values()]
        except Exception:
            names = []
    if not names:
        info = ProjectManager.analyze_dataset(ds_root)
        if info and isinstance(info.get('names'), list):
            names = [str(x) for x in info.get('names')]
    return names

def _parse_label_classes(label_path):
    cls_set = set()
    if not label_path or (not os.path.exists(label_path)):
        return cls_set
    try:
        with open(label_path, 'r', encoding='utf-8') as f:
            for line in f:
                s = line.strip()
                if not s:
                    continue
                parts = s.split()
                if not parts:
                    continue
                try:
                    cls_set.add(int(float(parts[0])))
                except Exception:
                    continue
    except Exception:
        return set()
    return cls_set

def _parse_bool(v, default=False):
    if v is None:
        return bool(default)
    if isinstance(v, bool):
        return v
    return str(v).strip().lower() in ('1', 'true', 'yes', 'y', 'on')

def _compute_balancing_params(target_count, non_target_count, desired_target_ratio, max_repeat=30):
    t = int(target_count or 0)
    n = int(non_target_count or 0)
    if t <= 0:
        return 1, 0.35, 0.0, 0, 0

    try:
        d = float(desired_target_ratio)
    except Exception:
        d = 0.05
    if d > 1.0 and d <= 100.0:
        d = d / 100.0
    d = min(0.99, max(0.001, d))

    best = None
    for r in range(1, int(max_repeat) + 1):
        for kx in range(0, 101):
            k = kx / 100.0
            keep_n = int(round(n * k))
            total = t * r + keep_n
            if total <= 0:
                continue
            ratio = float(t * r) / float(total)
            diff = abs(ratio - d)
            is_ge = ratio >= d
            cand = (is_ge, diff, -total, r, k, ratio, keep_n)
            if best is None:
                best = cand
            else:
                if best[0] != cand[0]:
                    if cand[0] and not best[0]:
                        best = cand
                else:
                    if cand[1] < best[1]:
                        best = cand
                    elif cand[1] == best[1]:
                        if cand[2] < best[2]:
                            best = cand
                        elif cand[2] == best[2] and cand[3] < best[3]:
                            best = cand
    if best is None:
        return 1, 0.35, 0.0, 0, 0
    _, _, _, r, k, ratio, keep_n = best
    return int(r), float(k), float(ratio), int(keep_n), int(t * r + keep_n)

def _augment_one_sample(src_img, src_lbl, dst_img, dst_lbl, rng, enable_hflip, enable_vflip, color_jitter):
    with Image.open(src_img) as im:
        img = im.convert('RGB')
    do_hflip = bool(enable_hflip) and (rng.random() < 0.5)
    do_vflip = bool(enable_vflip) and (rng.random() < 0.3)
    jitter = max(0.0, float(color_jitter or 0.0))
    if jitter > 0:
        b = 1.0 + rng.uniform(-jitter, jitter)
        c = 1.0 + rng.uniform(-jitter, jitter)
        s = 1.0 + rng.uniform(-jitter, jitter)
        img = ImageEnhance.Brightness(img).enhance(max(0.1, b))
        img = ImageEnhance.Contrast(img).enhance(max(0.1, c))
        img = ImageEnhance.Color(img).enhance(max(0.1, s))
    if do_hflip:
        img = img.transpose(Image.FLIP_LEFT_RIGHT)
    if do_vflip:
        img = img.transpose(Image.FLIP_TOP_BOTTOM)
    os.makedirs(os.path.dirname(dst_img), exist_ok=True)
    img.save(dst_img)

    lines = []
    if src_lbl and os.path.exists(src_lbl):
        with open(src_lbl, 'r', encoding='utf-8') as f:
            lines = f.readlines()

    out_lines = []
    for line in lines:
        s = line.strip()
        if not s:
            continue
        parts = s.split()
        if len(parts) < 5:
            out_lines.append(s + '\n')
            continue
        try:
            cid = int(float(parts[0]))
            x = float(parts[1])
            y = float(parts[2])
            w = float(parts[3])
            h = float(parts[4])
        except Exception:
            out_lines.append(s + '\n')
            continue
        if do_hflip:
            x = 1.0 - x
        if do_vflip:
            y = 1.0 - y
        x = min(1.0, max(0.0, x))
        y = min(1.0, max(0.0, y))
        w = min(1.0, max(0.0, w))
        h = min(1.0, max(0.0, h))
        rest = parts[5:]
        out_parts = [str(cid), f'{x:.6f}', f'{y:.6f}', f'{w:.6f}', f'{h:.6f}'] + rest
        out_lines.append(' '.join(out_parts) + '\n')

    os.makedirs(os.path.dirname(dst_lbl), exist_ok=True)
    with open(dst_lbl, 'w', encoding='utf-8') as f:
        f.writelines(out_lines)

@bp.route('/api/datasets')
def api_datasets():
    try:
        project_path = request.args.get('project_path')
        if not project_path:
            return jsonify({'success': False, 'error': '缺少项目路径'})
        datasets = ProjectManager.scan_datasets(project_path)
        return jsonify({'success': True, 'datasets': datasets})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@bp.route('/api/dataset/create_subset', methods=['POST'])
def api_dataset_create_subset():
    try:
        data = request.get_json() or {}
        project_path = data.get('project_path')
        source_dataset = data.get('source_dataset')
        new_dataset_name = data.get('new_dataset_name')
        image_paths = data.get('image_paths') or []

        if not project_path or not source_dataset or not new_dataset_name or not image_paths:
            return jsonify({'success': False, 'error': '缺少必要参数'})

        # 1. 确定目标路径
        target_root = os.path.join(project_path, 'training', new_dataset_name)
        if os.path.exists(target_root):
             return jsonify({'success': False, 'error': f'数据集 {new_dataset_name} 已存在'})

        # 2. 准备目录结构
        target_images_dir = os.path.join(target_root, 'train', 'images')
        target_labels_dir = os.path.join(target_root, 'train', 'labels')
        os.makedirs(target_images_dir, exist_ok=True)
        os.makedirs(target_labels_dir, exist_ok=True)

        # 3. 复制图片和标签
        count = 0
        for img_path in image_paths:
            if not os.path.exists(img_path):
                continue
            
            # 复制图片
            img_name = os.path.basename(img_path)
            shutil.copy2(img_path, os.path.join(target_images_dir, img_name))
            
            # 尝试查找标签
            lbl_path = None
            # 策略：替换路径中的 /images/ 为 /labels/ 并修改扩展名为 .txt
            parts = img_path.split(os.sep)
            if 'images' in parts:
                try:
                    # 找到最后一个 'images'
                    idx = len(parts) - 1 - parts[::-1].index('images')
                    parts[idx] = 'labels'
                    parts[-1] = os.path.splitext(parts[-1])[0] + '.txt'
                    candidate = os.sep.join(parts)
                    if os.path.exists(candidate):
                        lbl_path = candidate
                except ValueError:
                    pass
            
            # 如果上述策略失败，尝试简单的同级 labels 目录
            if not lbl_path:
                parent = os.path.dirname(img_path)
                grandparent = os.path.dirname(parent)
                if os.path.basename(parent) == 'images': # dataset/images/x.jpg
                     candidate = os.path.join(grandparent, 'labels', os.path.splitext(img_name)[0] + '.txt')
                     if os.path.exists(candidate):
                         lbl_path = candidate

            if lbl_path:
                shutil.copy2(lbl_path, os.path.join(target_labels_dir, os.path.basename(lbl_path)))
            
            count += 1

        # 4. 创建 dataset.yaml
        names = {}
        # 尝试查找源数据集路径
        source_candidates = [
            os.path.join(project_path, 'training', source_dataset),
            os.path.join(project_path, 'datasets', source_dataset)
        ]
        source_root = None
        for p in source_candidates:
            if os.path.exists(p):
                source_root = p
                break
        
        if source_root:
             # 优先直接读取 dataset.yaml
            yaml_path = os.path.join(source_root, 'dataset.yaml')
            if not os.path.exists(yaml_path):
                yaml_path = os.path.join(source_root, 'data.yaml')
            
            if os.path.exists(yaml_path):
                try:
                    with open(yaml_path, 'r', encoding='utf-8') as f:
                        data = yaml.safe_load(f) or {}
                        if 'names' in data:
                            names = data['names']
                except:
                    pass
            
            # 如果没读到，使用 ProjectManager 分析
            if not names:
                info = ProjectManager.analyze_dataset(source_root)
                if info and info.get('names'):
                    names = {i: n for i, n in enumerate(info['names'])}
        
        # 写入 dataset.yaml
        yaml_data = {
            'path': target_root,
            'train': 'train/images',
            'val': 'train/images', 
            'names': names
        }
        
        with open(os.path.join(target_root, 'dataset.yaml'), 'w', encoding='utf-8') as f:
            yaml.safe_dump(yaml_data, f, allow_unicode=True, sort_keys=False)

        return jsonify({'success': True, 'message': f'成功创建子数据集 {new_dataset_name}，包含 {count} 张图片'})

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)})

@bp.route('/api/dataset/augment_subset', methods=['POST'])
def api_dataset_augment_subset():
    try:
        data = request.get_json() or {}
        project_path = data.get('project_path')
        source_dataset = data.get('source_dataset')
        new_dataset_name = data.get('new_dataset_name')
        split = str(data.get('split') or 'train').strip() or 'train'
        target_class_id = data.get('target_class_id')
        target_repeat = int(data.get('target_repeat') or 8)
        non_target_keep_ratio = float(data.get('non_target_keep_ratio') if data.get('non_target_keep_ratio') is not None else 0.35)
        seed = int(data.get('seed') or 42)
        copy_eval_splits = _parse_bool(data.get('copy_eval_splits', True), default=True)
        enable_hflip = _parse_bool(data.get('enable_hflip', True), default=True)
        enable_vflip = _parse_bool(data.get('enable_vflip', False), default=False)
        dry_run = _parse_bool(data.get('dry_run', False), default=False)
        desired_target_ratio = data.get('desired_target_ratio')
        color_jitter = float(data.get('color_jitter') if data.get('color_jitter') is not None else 0.2)

        if not project_path or not source_dataset or target_class_id is None:
            return jsonify({'success': False, 'error': '缺少必要参数'})
        if (not dry_run) and (not new_dataset_name):
            return jsonify({'success': False, 'error': '缺少必要参数'})
        try:
            target_class_id = int(target_class_id)
        except Exception:
            return jsonify({'success': False, 'error': 'target_class_id 无效'})
        if target_repeat < 1:
            target_repeat = 1
        if target_repeat > 30:
            target_repeat = 30
        non_target_keep_ratio = min(1.0, max(0.0, non_target_keep_ratio))
        color_jitter = min(0.8, max(0.0, color_jitter))

        source_root = _resolve_dataset_root(project_path, source_dataset)
        if not source_root:
            return jsonify({'success': False, 'error': '源数据集不存在'})

        src_img_dir = os.path.join(source_root, split, 'images')
        src_lbl_dir = os.path.join(source_root, split, 'labels')
        if not os.path.isdir(src_img_dir):
            return jsonify({'success': False, 'error': f'{split}/images 不存在'})

        target_root = os.path.join(project_path, 'training', new_dataset_name)
        if os.path.exists(target_root):
            return jsonify({'success': False, 'error': f'数据集 {new_dataset_name} 已存在'})

        items = []
        for root, _, files in os.walk(src_img_dir):
            for fn in files:
                low = fn.lower()
                if not low.endswith(('.jpg', '.jpeg', '.png', '.bmp', '.webp')):
                    continue
                img_path = os.path.join(root, fn)
                rel = os.path.relpath(img_path, src_img_dir)
                lbl_path = os.path.join(src_lbl_dir, os.path.splitext(rel)[0] + '.txt')
                classes = _parse_label_classes(lbl_path)
                has_target = target_class_id in classes
                items.append({
                    'img': img_path,
                    'lbl': lbl_path if os.path.exists(lbl_path) else None,
                    'rel': rel,
                    'has_target': has_target
                })

        if not items:
            return jsonify({'success': False, 'error': '源数据集图片为空'})

        target_items = [x for x in items if x['has_target']]
        non_target_items = [x for x in items if not x['has_target']]
        if len(target_items) == 0:
            return jsonify({'success': False, 'error': '未找到包含该标签的样本'})

        if desired_target_ratio is not None and str(desired_target_ratio).strip() != '':
            auto_repeat, auto_keep_ratio, _, _, _ = _compute_balancing_params(
                target_count=len(target_items),
                non_target_count=len(non_target_items),
                desired_target_ratio=desired_target_ratio,
                max_repeat=30
            )
            target_repeat = int(auto_repeat)
            non_target_keep_ratio = float(auto_keep_ratio)

        rng = random.Random(seed)
        rng.shuffle(non_target_items)
        keep_non_target_count = int(round(len(non_target_items) * non_target_keep_ratio))
        kept_non_target_items = non_target_items[:keep_non_target_count]

        keep_base_items = target_items + kept_non_target_items
        original_target_count = len(target_items)
        original_total_count = len(items)
        output_total_count = len(target_items) * int(target_repeat) + keep_non_target_count
        output_target_count = len(target_items) * int(target_repeat)
        output_target_ratio = (float(output_target_count) / float(output_total_count)) if output_total_count > 0 else 0.0

        if dry_run:
            return jsonify({
                'success': True,
                'dry_run': True,
                'source_split': split,
                'target_class_id': target_class_id,
                'original_total': original_total_count,
                'original_target': original_target_count,
                'non_target_total': len(non_target_items),
                'resolved_target_repeat': int(target_repeat),
                'resolved_non_target_keep_ratio': round(float(non_target_keep_ratio), 4),
                'estimated_kept_non_target': int(keep_non_target_count),
                'estimated_output_total': int(output_total_count),
                'estimated_output_target': int(output_target_count),
                'estimated_output_target_ratio': round(output_target_ratio * 100, 2),
                'message': f'预估完成：目标类占比约 {round(output_target_ratio * 100, 2)}%'
            })

        out_train_img = os.path.join(target_root, 'train', 'images')
        out_train_lbl = os.path.join(target_root, 'train', 'labels')
        os.makedirs(out_train_img, exist_ok=True)
        os.makedirs(out_train_lbl, exist_ok=True)

        copied_base_count = 0
        for it in keep_base_items:
            dst_img = os.path.join(out_train_img, it['rel'])
            dst_lbl = os.path.join(out_train_lbl, os.path.splitext(it['rel'])[0] + '.txt')
            os.makedirs(os.path.dirname(dst_img), exist_ok=True)
            os.makedirs(os.path.dirname(dst_lbl), exist_ok=True)
            shutil.copy2(it['img'], dst_img)
            if it['lbl'] and os.path.exists(it['lbl']):
                shutil.copy2(it['lbl'], dst_lbl)
            else:
                with open(dst_lbl, 'w', encoding='utf-8') as f:
                    f.write('')
            copied_base_count += 1

        extra_needed = max(0, target_repeat - 1) * len(target_items)
        augmented_count = 0
        if extra_needed > 0:
            pool = list(target_items)
            rng.shuffle(pool)
            for i in range(extra_needed):
                src = pool[i % len(pool)]
                rel_noext, ext = os.path.splitext(src['rel'])
                if not ext:
                    ext = '.jpg'
                aug_rel = f'{rel_noext}__aug_{i+1:05d}{ext}'
                dst_img = os.path.join(out_train_img, aug_rel)
                dst_lbl = os.path.join(out_train_lbl, f'{rel_noext}__aug_{i+1:05d}.txt')
                _augment_one_sample(
                    src_img=src['img'],
                    src_lbl=src['lbl'],
                    dst_img=dst_img,
                    dst_lbl=dst_lbl,
                    rng=rng,
                    enable_hflip=enable_hflip,
                    enable_vflip=enable_vflip,
                    color_jitter=color_jitter
                )
                augmented_count += 1

        copied_eval = {}
        if copy_eval_splits:
            for eval_split in ('val', 'test'):
                copied_eval[eval_split] = {'images': 0, 'labels': 0}
                src_eval_img = os.path.join(source_root, eval_split, 'images')
                src_eval_lbl = os.path.join(source_root, eval_split, 'labels')
                dst_eval_img = os.path.join(target_root, eval_split, 'images')
                dst_eval_lbl = os.path.join(target_root, eval_split, 'labels')

                if os.path.isdir(src_eval_img):
                    for root, _, files in os.walk(src_eval_img):
                        for fn in files:
                            src_fp = os.path.join(root, fn)
                            rel = os.path.relpath(src_fp, src_eval_img)
                            dst_fp = os.path.join(dst_eval_img, rel)
                            os.makedirs(os.path.dirname(dst_fp), exist_ok=True)
                            shutil.copy2(src_fp, dst_fp)
                            copied_eval[eval_split]['images'] += 1
                if os.path.isdir(src_eval_lbl):
                    for root, _, files in os.walk(src_eval_lbl):
                        for fn in files:
                            src_fp = os.path.join(root, fn)
                            rel = os.path.relpath(src_fp, src_eval_lbl)
                            dst_fp = os.path.join(dst_eval_lbl, rel)
                            os.makedirs(os.path.dirname(dst_fp), exist_ok=True)
                            shutil.copy2(src_fp, dst_fp)
                            copied_eval[eval_split]['labels'] += 1

        names = _load_dataset_names(source_root)
        yaml_names = {i: n for i, n in enumerate(names)}
        yaml_data = {
            'path': target_root,
            'train': 'train/images',
            'val': 'val/images' if os.path.isdir(os.path.join(target_root, 'val', 'images')) else 'train/images',
            'names': yaml_names
        }
        if os.path.isdir(os.path.join(target_root, 'test', 'images')):
            yaml_data['test'] = 'test/images'
        with open(os.path.join(target_root, 'dataset.yaml'), 'w', encoding='utf-8') as f:
            yaml.safe_dump(yaml_data, f, allow_unicode=True, sort_keys=False)

        output_total_count = copied_base_count + augmented_count
        output_target_count = len(target_items) + augmented_count
        output_target_ratio = (float(output_target_count) / float(output_total_count)) if output_total_count > 0 else 0.0

        return jsonify({
            'success': True,
            'dry_run': False,
            'new_dataset_name': new_dataset_name,
            'source_split': split,
            'target_class_id': target_class_id,
            'original_total': original_total_count,
            'original_target': original_target_count,
            'copied_non_target': len(kept_non_target_items),
            'resolved_target_repeat': int(target_repeat),
            'resolved_non_target_keep_ratio': round(float(non_target_keep_ratio), 4),
            'copied_base': copied_base_count,
            'augmented': augmented_count,
            'output_total': output_total_count,
            'output_target': output_target_count,
            'output_target_ratio': round(output_target_ratio * 100, 2),
            'copied_eval': copied_eval,
            'message': f'已创建增强子集 {new_dataset_name}：train样本 {output_total_count} 张，目标类占比 {round(output_target_ratio * 100, 2)}%'
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@bp.route('/api/dataset/info')
def api_dataset_info():
    try:
        project_path = request.args.get('project_path')
        dataset_name = request.args.get('dataset_name')
        if not project_path or not dataset_name:
            return jsonify({'success': False, 'error': '缺少必要参数'})
            
        # 优先检查 training 目录
        p = os.path.join(project_path, "training", dataset_name)
        if not os.path.exists(p):
            p = os.path.join(project_path, "datasets", dataset_name)
            
        if not os.path.exists(p):
            return jsonify({'success': False, 'error': '数据集不存在'})
            
        info = ProjectManager.analyze_dataset(p)
        info['name'] = dataset_name
        info['path'] = p
        return jsonify({'success': True, 'info': info})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@bp.route('/api/dataset/download')
def api_dataset_download():
    try:
        project_path = request.args.get('project_path')
        dataset_name = request.args.get('dataset_name')
        if not project_path or not dataset_name:
            return jsonify({'success': False, 'error': '缺少必要参数'})

        project_real = os.path.realpath(project_path)
        ds_candidates = [
            os.path.join(project_path, 'training', dataset_name),
            os.path.join(project_path, 'datasets', dataset_name),
        ]
        ds_root = None
        for p in ds_candidates:
            if p and os.path.isdir(p):
                ds_root = p
                break
        if not ds_root:
            return jsonify({'success': False, 'error': '数据集不存在'})

        ds_root_real = os.path.realpath(ds_root)
        if not (ds_root_real == project_real or ds_root_real.startswith(project_real + os.sep)):
            return jsonify({'success': False, 'error': '非法路径'})

        fd, tmp_zip = tempfile.mkstemp(prefix=f'{dataset_name}_', suffix='.zip')
        os.close(fd)

        @after_this_request
        def cleanup(response):
            try:
                if os.path.exists(tmp_zip):
                    os.remove(tmp_zip)
            except Exception:
                pass
            return response

        base_prefix = dataset_name.strip().replace(os.sep, '_') or 'dataset'
        with zipfile.ZipFile(tmp_zip, 'w', compression=zipfile.ZIP_DEFLATED) as zf:
            for root, dirs, files in os.walk(ds_root_real):
                dirs[:] = [d for d in dirs if d not in ('__pycache__', '.git')]
                for fn in files:
                    fp = os.path.join(root, fn)
                    rel = os.path.relpath(fp, ds_root_real)
                    arcname = os.path.join(base_prefix, rel)
                    zf.write(fp, arcname)

        try:
            return send_file(tmp_zip, mimetype='application/zip', as_attachment=True, download_name=f'{base_prefix}.zip')
        except TypeError:
            return send_file(tmp_zip, mimetype='application/zip', as_attachment=True, attachment_filename=f'{base_prefix}.zip')
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@bp.route('/api/dataset/images')
def api_dataset_images():
    try:
        project_path = request.args.get('project_path')
        dataset_name = request.args.get('dataset_name')
        split = request.args.get('split', 'train')
        offset = int(request.args.get('offset', '0'))
        limit = int(request.args.get('limit', '50'))
        classes_raw = request.args.get('classes') or request.args.get('class')
        mode = (request.args.get('mode') or 'include').strip().lower()
        unannotated_raw = request.args.get('unannotated')
        has_auto_label_raw = request.args.get('has_auto_label')
        
        if not project_path or not dataset_name:
            return jsonify({'success': False, 'error': '缺少必要参数'})
            
        ds_root = os.path.join(project_path, 'training', dataset_name)
        img_dir = os.path.join(ds_root, split, 'images')
        lbl_dir = os.path.join(ds_root, split, 'labels')
        auto_dir = os.path.join(ds_root, 'auto_labels', split)
        
        if not os.path.exists(img_dir):
            return jsonify({'success': True, 'images': [], 'total': 0})
            
        def parse_bool(v):
            if v is None:
                return False
            if isinstance(v, bool):
                return v
            return str(v).strip().lower() in ('1', 'true', 'yes', 'y', 'on')

        unannotated = parse_bool(unannotated_raw)
        has_auto_label = parse_bool(has_auto_label_raw)

        class_ids = []
        if classes_raw is not None and str(classes_raw).strip() != '':
            for part in str(classes_raw).split(','):
                s = part.strip()
                if s == '':
                    continue
                try:
                    class_ids.append(int(float(s)))
                except Exception:
                    continue
        class_id_set = set(class_ids)

        images = []
        # 遍历图片
        for root, _, files in os.walk(img_dir):
            for f in files:
                if f.lower().endswith(('.jpg', '.jpeg', '.png')):
                    img_path = os.path.join(root, f)
                    rel = os.path.relpath(img_path, img_dir)
                    lp = os.path.join(lbl_dir, os.path.splitext(rel)[0] + '.txt')
                    label_exists = os.path.exists(lp)
                    label_has_content = label_exists and os.path.getsize(lp) > 0

                    if has_auto_label:
                        auto_lbl_path = os.path.join(auto_dir, os.path.splitext(rel)[0] + '.txt')
                        if not os.path.exists(auto_lbl_path):
                            continue

                    if unannotated:
                        if label_exists:
                            continue
                        images.append(img_path)
                        continue

                    if class_id_set:
                        present = set()
                        if label_has_content:
                            try:
                                with open(lp, 'r') as lf:
                                    for line in lf:
                                        parts = line.strip().split()
                                        if not parts:
                                            continue
                                        try:
                                            present.add(int(float(parts[0])))
                                        except Exception:
                                            continue
                            except Exception:
                                present = set()
                        has_any = bool(present & class_id_set)
                        if mode == 'exclude':
                            if has_any:
                                continue
                        else:
                            if not has_any:
                                continue
                            
                    images.append(img_path)
                    
        total = len(images)
        images.sort()
        page_imgs = images[offset:offset+limit]
        
        # 转换为 API URL
        items = []
        for p in page_imgs:
            items.append({
                'url': f"/api/file?path={p}",
                'path': p,
                'name': os.path.basename(p)
            })
            
        return jsonify({'success': True, 'images': items, 'total': total})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@bp.route('/api/dataset/person_review')
def api_dataset_person_review():
    try:
        project_path = request.args.get('project_path')
        dataset_name = request.args.get('dataset_name')
        split = request.args.get('split', 'train')
        offset = int(request.args.get('offset', '0'))
        limit = int(request.args.get('limit', '50'))
        conf = float(request.args.get('conf', '0.25'))
        iou_thresh = float(request.args.get('iou', '0.5'))

        if not project_path or not dataset_name:
            return jsonify({'success': False, 'error': '缺少必要参数'})

        ds_root = os.path.join(project_path, 'training', dataset_name)
        img_dir = os.path.join(ds_root, split, 'images')
        lbl_dir = os.path.join(ds_root, split, 'labels')
        if not os.path.isdir(img_dir) or not os.path.isdir(lbl_dir):
            return jsonify({'success': True, 'images': [], 'total': 0})

        # 读取数据集的 person 类索引
        yaml_path = os.path.join(ds_root, 'data.yaml')
        if not os.path.exists(yaml_path):
            yaml_path = os.path.join(ds_root, 'dataset.yaml')
        person_id = None
        if os.path.exists(yaml_path):
            try:
                with open(yaml_path, 'r', encoding='utf-8') as f:
                    y = yaml.safe_load(f) or {}
                names = y.get('names')
                resolved = []
                if isinstance(names, list):
                    resolved = list(names)
                elif isinstance(names, dict):
                    pairs = []
                    for k, v in names.items():
                        try:
                            kk = int(k)
                        except Exception:
                            continue
                        pairs.append((kk, v))
                    resolved = [v for _, v in sorted(pairs, key=lambda x: x[0])] if pairs else list(names.values())
                if resolved:
                    try:
                        person_id = resolved.index('person')
                    except ValueError:
                        person_id = None
            except Exception:
                person_id = None

        # 收集包含 person 标注的图片
        candidates = []
        for root, _, files in os.walk(img_dir):
            for f in files:
                if not f.lower().endswith(('.jpg', '.jpeg', '.png')):
                    continue
                img_path = os.path.join(root, f)
                rel = os.path.relpath(img_path, img_dir)
                lbl_path = os.path.join(lbl_dir, os.path.splitext(rel)[0] + '.txt')
                if not os.path.exists(lbl_path):
                    continue
                # 检查是否存在 person 标注
                has_person = False
                try:
                    with open(lbl_path, 'r', encoding='utf-8') as lf:
                        for line in lf:
                            parts = line.strip().split()
                            if len(parts) >= 5:
                                try:
                                    cid = int(float(parts[0]))
                                except Exception:
                                    continue
                                if person_id is None or cid == person_id:
                                    has_person = True
                                    break
                except Exception:
                    continue
                if has_person:
                    candidates.append((img_path, lbl_path))

        candidates.sort()
        total = len(candidates)
        page_items = candidates[offset:offset+limit]

        # 逐张图片进行模型校验（轻量模型或项目最佳）
        items = []
        for img_path, lbl_path in page_items:
            # 读取图片尺寸
            w, h = 1, 1
            try:
                from PIL import Image
                with Image.open(img_path) as im:
                    w, h = im.size
            except Exception:
                try:
                    import cv2
                    im = cv2.imread(img_path)
                    if im is not None and getattr(im, 'shape', None) is not None:
                        h, w = im.shape[:2]
                except Exception:
                    pass

            # 读取人工 person 框（转为像素坐标）
            manual_person_boxes = []
            try:
                with open(lbl_path, 'r', encoding='utf-8') as lf:
                    for line in lf:
                        parts = line.strip().split()
                        if len(parts) >= 5:
                            try:
                                cid = int(float(parts[0]))
                                cx = float(parts[1]) * w
                                cy = float(parts[2]) * h
                                ww = float(parts[3]) * w
                                hh = float(parts[4]) * h
                                x1 = max(0.0, cx - ww/2.0)
                                y1 = max(0.0, cy - hh/2.0)
                                x2 = min(float(w), cx + ww/2.0)
                                y2 = min(float(h), cy + hh/2.0)
                            except Exception:
                                continue
                            if person_id is None or cid == person_id:
                                manual_person_boxes.append({'x1': x1, 'y1': y1, 'x2': x2, 'y2': y2})
            except Exception:
                manual_person_boxes = []

            # 模型预测（只保留可能为人类的框）
            preds = []
            try:
                model = _get_person_review_model()
                results = model.predict(img_path, conf=float(conf), max_det=200, verbose=False)
                for r in results:
                    for b in r.boxes:
                        xyxy = b.xyxy[0].tolist()
                        cls = int(b.cls.item()) if hasattr(b, 'cls') else 0
                        preds.append({'class': cls, 'x1': xyxy[0], 'y1': xyxy[1], 'x2': xyxy[2], 'y2': xyxy[3]})
            except Exception:
                preds = []

            pred_person_ids = set()
            if person_id is not None:
                pred_person_ids.add(int(person_id))
            pred_person_ids.add(0)

            pred_person_boxes = [
                {'x1': float(b.get('x1', 0.0)), 'y1': float(b.get('y1', 0.0)), 'x2': float(b.get('x2', 0.0)), 'y2': float(b.get('y2', 0.0))}
                for b in preds
                if int(b.get('class', -1)) in pred_person_ids
            ]

            def iou(a, b):
                ix1 = max(a['x1'], b['x1']); iy1 = max(a['y1'], b['y1'])
                ix2 = min(a['x2'], b['x2']); iy2 = min(a['y2'], b['y2'])
                iw = max(0.0, ix2 - ix1); ih = max(0.0, iy2 - iy1)
                inter = iw * ih
                area_a = max(0.0, (a['x2']-a['x1'])) * max(0.0, (a['y2']-a['y1']))
                area_b = max(0.0, (b['x2']-b['x1'])) * max(0.0, (b['y2']-b['y1']))
                union = area_a + area_b - inter + 1e-6
                return inter / union

            suspect = 0
            suspect_boxes = []
            for mb in manual_person_boxes:
                matched = False
                for pb in pred_person_boxes:
                    if iou(mb, pb) >= iou_thresh:
                        matched = True
                        break
                if not matched:
                    suspect += 1
                    suspect_boxes.append({
                        'x1': float(mb['x1']) / float(w or 1),
                        'y1': float(mb['y1']) / float(h or 1),
                        'x2': float(mb['x2']) / float(w or 1),
                        'y2': float(mb['y2']) / float(h or 1)
                    })

            rel = os.path.relpath(img_path, img_dir)
            items.append({
                'url': f"/api/file?path={img_path}",
                'path': img_path,
                'name': os.path.basename(img_path),
                'pending': suspect > 0,
                'review': {
                    'manual_person_count': len(manual_person_boxes),
                    'pred_person_count': len(pred_person_boxes),
                    'suspect_person_count': suspect,
                    'suspect_boxes': suspect_boxes,
                    'iou_thresh': iou_thresh,
                    'conf': conf
                }
            })

        return jsonify({'success': True, 'images': items, 'total': total})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@bp.route('/api/dataset/upload', methods=['POST'])
def api_dataset_upload():
    try:
        project_path = request.form.get('project_path')
        dataset_name = request.form.get('dataset_name')
        split = request.form.get('split', 'train')
        files = request.files.getlist('files')
        if not project_path or not dataset_name or not files:
            return jsonify({'success': False, 'error': '缺少必要参数'})
        target_dir = os.path.join(project_path, 'training', dataset_name, split, 'images')
        os.makedirs(target_dir, exist_ok=True)
        saved = []
        for f in files:
            fn = os.path.basename(f.filename or '')
            if not fn or (not fn.lower().endswith(('.jpg', '.jpeg', '.png'))):
                continue
            name, ext = os.path.splitext(fn)
            dst = os.path.join(target_dir, fn)
            idx = 1
            while os.path.exists(dst):
                dst = os.path.join(target_dir, f"{name}_{idx}{ext}")
                idx += 1
            f.save(dst)
            saved.append(dst)
        return jsonify({'success': True, 'saved': [f"/api/file?path={p}" for p in saved], 'count': len(saved)})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@bp.route('/api/dataset/delete', methods=['POST'])
def api_dataset_delete():
    try:
        data = request.get_json() or {}
        project_path = data.get('project_path')
        dataset_name = data.get('dataset_name')
        split = data.get('split', 'train')
        image_rel = data.get('image_rel')
        image_path = data.get('image_path')
        if not project_path or not dataset_name:
            return jsonify({'success': False, 'error': '缺少必要参数'})
        ds_root = os.path.join(project_path, 'training', dataset_name)
        img_dir = os.path.join(ds_root, split, 'images')
        lbl_dir = os.path.join(ds_root, split, 'labels')
        auto_dir = os.path.join(ds_root, 'auto_labels', split)

        img_dir_real = os.path.realpath(img_dir) + os.sep
        if not image_rel and image_path:
            try:
                ip_real = os.path.realpath(str(image_path))
                if ip_real.startswith(img_dir_real):
                    image_rel = os.path.relpath(ip_real, os.path.realpath(img_dir))
            except Exception:
                image_rel = None
            if not image_rel:
                key = os.sep + split + os.sep + 'images' + os.sep
                pos = str(image_path).find(key)
                if pos >= 0:
                    image_rel = str(image_path)[pos+len(key):]
                else:
                    image_rel = os.path.basename(str(image_path))
        if not image_rel:
            return jsonify({'success': False, 'error': '缺少必要参数'})
        img_path = os.path.join(img_dir, image_rel)
        img_path_real = os.path.realpath(img_path)
        if not img_path_real.startswith(img_dir_real):
            return jsonify({'success': False, 'error': '非法路径'})

        rel_noext = os.path.splitext(image_rel)[0]
        lbl_path = os.path.join(lbl_dir, rel_noext + '.txt')
        auto_path = os.path.join(auto_dir, rel_noext + '.txt')

        deleted = {'image': False, 'label': False, 'auto_label': False}
        if os.path.exists(img_path_real):
            os.remove(img_path_real)
            deleted['image'] = True
        if os.path.exists(lbl_path):
            os.remove(lbl_path)
            deleted['label'] = True
        if os.path.exists(auto_path):
            os.remove(auto_path)
            deleted['auto_label'] = True
        return jsonify({'success': True, 'deleted': deleted})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@bp.route('/api/dataset/batch_delete', methods=['POST'])
def api_dataset_batch_delete():
    try:
        data = request.get_json() or {}
        project_path = data.get('project_path')
        dataset_name = data.get('dataset_name')
        split = data.get('split', 'train')
        image_paths = data.get('image_paths') or []
        if not project_path or not dataset_name:
            return jsonify({'success': False, 'error': '缺少必要参数'})
        if not isinstance(image_paths, list) or len(image_paths) == 0:
            return jsonify({'success': False, 'error': '缺少必要参数'})

        ds_root = os.path.join(project_path, 'training', dataset_name)
        img_dir = os.path.join(ds_root, split, 'images')
        lbl_dir = os.path.join(ds_root, split, 'labels')
        auto_dir = os.path.join(ds_root, 'auto_labels', split)

        img_dir_real = os.path.realpath(img_dir) + os.sep

        results = []
        deleted_count = 0
        for image_path in image_paths:
            image_rel = None
            if isinstance(image_path, str):
                try:
                    ip_real = os.path.realpath(image_path)
                    if ip_real.startswith(img_dir_real):
                        image_rel = os.path.relpath(ip_real, os.path.realpath(img_dir))
                except Exception:
                    image_rel = None

                if not image_rel:
                    key = os.sep + split + os.sep + 'images' + os.sep
                    pos = image_path.find(key)
                    if pos >= 0:
                        image_rel = image_path[pos + len(key):]
                    else:
                        image_rel = os.path.basename(image_path)

            if not image_rel:
                results.append({'path': image_path, 'success': False, 'error': '非法路径'})
                continue

            img_path = os.path.join(img_dir, image_rel)
            img_path_real = os.path.realpath(img_path)
            if not img_path_real.startswith(img_dir_real):
                results.append({'path': image_path, 'success': False, 'error': '非法路径'})
                continue

            rel_noext = os.path.splitext(image_rel)[0]
            lbl_path = os.path.join(lbl_dir, rel_noext + '.txt')
            auto_path = os.path.join(auto_dir, rel_noext + '.txt')

            deleted = {'image': False, 'label': False, 'auto_label': False}
            try:
                if os.path.exists(img_path_real):
                    os.remove(img_path_real)
                    deleted['image'] = True
                    deleted_count += 1
                if os.path.exists(lbl_path):
                    os.remove(lbl_path)
                    deleted['label'] = True
                if os.path.exists(auto_path):
                    os.remove(auto_path)
                    deleted['auto_label'] = True
                results.append({'path': image_path, 'success': True, 'deleted': deleted})
            except Exception as e:
                results.append({'path': image_path, 'success': False, 'error': str(e), 'deleted': deleted})

        return jsonify({'success': True, 'deleted_count': deleted_count, 'results': results})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@bp.route('/api/dataset/reorder_labels', methods=['POST'])
def api_dataset_reorder_labels():
    try:
        data = request.get_json() or {}
        project_path = data.get('project_path')
        dataset_name = data.get('dataset_name')
        order = data.get('order')
        splits = data.get('splits')

        if not project_path or not dataset_name:
            return jsonify({'success': False, 'error': '缺少必要参数'})
        if not isinstance(order, list) or len(order) == 0:
            return jsonify({'success': False, 'error': '缺少必要参数'})

        ds_candidates = [
            os.path.join(project_path, 'training', dataset_name),
            os.path.join(project_path, 'datasets', dataset_name),
        ]
        ds_root = None
        for p in ds_candidates:
            if p and os.path.isdir(p):
                ds_root = p
                break
        if not ds_root:
            return jsonify({'success': False, 'error': '数据集不存在'})

        yaml_path = os.path.join(ds_root, 'data.yaml')
        if not os.path.exists(yaml_path):
            yaml_path = os.path.join(ds_root, 'dataset.yaml')
            
        if not os.path.exists(yaml_path):
            return jsonify({'success': False, 'error': '未找到 data.yaml 或 dataset.yaml'})

        with open(yaml_path, 'r', encoding='utf-8') as f:
            y = yaml.safe_load(f) or {}

        original_names = y.get('names')
        if isinstance(original_names, dict):
            pairs = []
            for k, v in original_names.items():
                try:
                    kk = int(k)
                except Exception:
                    continue
                pairs.append((kk, v))
            if pairs:
                old_names = [v for _, v in sorted(pairs, key=lambda x: x[0])]
            else:
                old_names = list(original_names.values())
        elif isinstance(original_names, list):
            old_names = list(original_names)
        else:
            return jsonify({'success': False, 'error': 'data.yaml 缺少 names'})

        n = len(old_names)
        try:
            order_ints = [int(x) for x in order]
        except Exception:
            return jsonify({'success': False, 'error': 'order 参数无效'})

        if len(order_ints) != n:
            return jsonify({'success': False, 'error': 'order 长度必须等于类别数'})
        if len(set(order_ints)) != n:
            return jsonify({'success': False, 'error': 'order 不能包含重复项'})
        if any((i < 0 or i >= n) for i in order_ints):
            return jsonify({'success': False, 'error': 'order 存在越界索引'})

        new_names = [old_names[i] for i in order_ints]
        id_map = {old_idx: new_idx for new_idx, old_idx in enumerate(order_ints)}

        if isinstance(original_names, dict):
            y['names'] = {i: name for i, name in enumerate(new_names)}
        else:
            y['names'] = new_names
        y['nc'] = len(new_names)

        with open(yaml_path, 'w', encoding='utf-8') as f:
            yaml.safe_dump(y, f, allow_unicode=True, sort_keys=False)

        if splits is None:
            split_list = ['train', 'val', 'test']
        elif isinstance(splits, list):
            split_list = [str(s).strip() for s in splits if str(s).strip()]
        else:
            return jsonify({'success': False, 'error': 'splits 参数无效'})

        updated_files = 0
        updated_lines = 0
        skipped_files = 0

        def rewrite_label_file(fp):
            nonlocal updated_lines
            changed = False
            try:
                with open(fp, 'r', encoding='utf-8') as rf:
                    lines = rf.readlines()
            except Exception:
                return False

            out = []
            for line in lines:
                s = line.strip()
                if not s:
                    out.append(line)
                    continue
                parts = s.split()
                if not parts:
                    out.append(line)
                    continue
                try:
                    cid = int(float(parts[0]))
                except Exception:
                    out.append(line)
                    continue

                if cid in id_map:
                    new_cid = id_map[cid]
                    if new_cid != cid:
                        parts[0] = str(new_cid)
                        changed = True
                        updated_lines += 1
                    out.append(' '.join(parts) + '\n')
                else:
                    out.append(line if line.endswith('\n') else (line + '\n'))

            if not changed:
                return False

            try:
                with open(fp, 'w', encoding='utf-8') as wf:
                    wf.writelines(out)
                return True
            except Exception:
                return False

        for split in split_list:
            lbl_dir = os.path.join(ds_root, split, 'labels')
            auto_dir = os.path.join(ds_root, 'auto_labels', split)
            for base in (lbl_dir, auto_dir):
                if not os.path.isdir(base):
                    continue
                for root, _, files in os.walk(base):
                    for fn in files:
                        if not fn.lower().endswith('.txt'):
                            continue
                        fp = os.path.join(root, fn)
                        ok = rewrite_label_file(fp)
                        if ok:
                            updated_files += 1
                        else:
                            skipped_files += 1

        return jsonify({
            'success': True,
            'dataset_root': ds_root,
            'yaml_path': yaml_path,
            'updated_files': updated_files,
            'updated_lines': updated_lines,
            'skipped_files': skipped_files,
            'order': order_ints,
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


def _dataset_delete_label(ds_root, yaml_path, delete_id, splits=None, delete_empty_files=True):
    with open(yaml_path, 'r', encoding='utf-8') as f:
        y = yaml.safe_load(f) or {}

    original_names = y.get('names')
    original_is_dict = isinstance(original_names, dict)
    if isinstance(original_names, dict):
        pairs = []
        for k, v in original_names.items():
            try:
                kk = int(k)
            except Exception:
                continue
            pairs.append((kk, v))
        if pairs:
            old_names = [v for _, v in sorted(pairs, key=lambda x: x[0])]
        else:
            old_names = list(original_names.values())
    elif isinstance(original_names, list):
        old_names = list(original_names)
    else:
        raise ValueError('data.yaml 缺少 names')

    n = len(old_names)
    if delete_id < 0 or delete_id >= n:
        raise ValueError('class_id 越界')
    deleted_name = old_names[delete_id]

    new_names = [name for idx, name in enumerate(old_names) if idx != delete_id]
    if original_is_dict:
        y['names'] = {i: name for i, name in enumerate(new_names)}
    else:
        y['names'] = new_names
    y['nc'] = len(new_names)

    with open(yaml_path, 'w', encoding='utf-8') as f:
        yaml.safe_dump(y, f, allow_unicode=True, sort_keys=False)

    if splits is None:
        split_list = ['train', 'val', 'test']
    elif isinstance(splits, list):
        split_list = [str(s).strip() for s in splits if str(s).strip()]
    else:
        raise ValueError('splits 参数无效')

    updated_files = 0
    deleted_files = 0
    shifted_lines = 0
    removed_lines = 0
    skipped_files = 0

    def rewrite_label_file(fp):
        nonlocal shifted_lines, removed_lines, deleted_files
        try:
            with open(fp, 'r', encoding='utf-8') as rf:
                lines = rf.readlines()
        except Exception:
            return False

        out = []
        changed = False
        for line in lines:
            s = line.strip()
            if not s:
                continue
            parts = s.split()
            if not parts:
                continue
            try:
                cid = int(float(parts[0]))
            except Exception:
                out.append(line if line.endswith('\n') else (line + '\n'))
                continue

            if cid == delete_id:
                changed = True
                removed_lines += 1
                continue
            if cid > delete_id:
                parts[0] = str(cid - 1)
                changed = True
                shifted_lines += 1
                out.append(' '.join(parts) + '\n')
                continue

            out.append(' '.join(parts) + '\n')

        if not changed:
            return False

        if delete_empty_files and len(out) == 0:
            try:
                os.remove(fp)
                deleted_files += 1
                return True
            except Exception:
                pass

        try:
            with open(fp, 'w', encoding='utf-8') as wf:
                wf.writelines(out)
            return True
        except Exception:
            return False

    for split in split_list:
        lbl_dir = os.path.join(ds_root, split, 'labels')
        auto_dir = os.path.join(ds_root, 'auto_labels', split)
        for base in (lbl_dir, auto_dir):
            if not os.path.isdir(base):
                continue
            for root, _, files in os.walk(base):
                for fn in files:
                    if not fn.lower().endswith('.txt'):
                        continue
                    fp = os.path.join(root, fn)
                    ok = rewrite_label_file(fp)
                    if ok:
                        updated_files += 1
                    else:
                        skipped_files += 1

    return {
        'dataset_root': ds_root,
        'yaml_path': yaml_path,
        'deleted_label_id': delete_id,
        'deleted_label_name': deleted_name,
        'nc': len(new_names),
        'updated_files': updated_files,
        'deleted_files': deleted_files,
        'shifted_lines': shifted_lines,
        'removed_lines': removed_lines,
        'skipped_files': skipped_files,
        'splits': split_list
    }


@bp.route('/api/dataset/delete_label', methods=['POST'])
def api_dataset_delete_label():
    try:
        data = request.get_json() or {}
        project_path = data.get('project_path')
        dataset_name = data.get('dataset_name')
        class_id = data.get('class_id')
        class_name = data.get('class_name')
        splits = data.get('splits')

        if not project_path or not dataset_name:
            return jsonify({'success': False, 'error': '缺少必要参数'})
        if class_id is None and (class_name is None or str(class_name).strip() == ''):
            return jsonify({'success': False, 'error': '缺少必要参数'})

        ds_candidates = [
            os.path.join(project_path, 'training', dataset_name),
            os.path.join(project_path, 'datasets', dataset_name),
        ]
        ds_root = None
        for p in ds_candidates:
            if p and os.path.isdir(p):
                ds_root = p
                break
        if not ds_root:
            return jsonify({'success': False, 'error': '数据集不存在'})

        yaml_path = os.path.join(ds_root, 'data.yaml')
        if not os.path.exists(yaml_path):
            yaml_path = os.path.join(ds_root, 'dataset.yaml')
        if not os.path.exists(yaml_path):
            return jsonify({'success': False, 'error': '未找到 data.yaml 或 dataset.yaml'})

        delete_id = None
        if class_id is not None:
            try:
                delete_id = int(class_id)
            except Exception:
                return jsonify({'success': False, 'error': 'class_id 参数无效'})
        else:
            with open(yaml_path, 'r', encoding='utf-8') as f:
                y = yaml.safe_load(f) or {}
            names = y.get('names')
            resolved = []
            if isinstance(names, list):
                resolved = list(names)
            elif isinstance(names, dict):
                pairs = []
                for k, v in names.items():
                    try:
                        kk = int(k)
                    except Exception:
                        continue
                    pairs.append((kk, v))
                resolved = [v for _, v in sorted(pairs, key=lambda x: x[0])] if pairs else list(names.values())
            else:
                return jsonify({'success': False, 'error': 'data.yaml 缺少 names'})

            target = str(class_name).strip()
            try:
                delete_id = resolved.index(target)
            except ValueError:
                return jsonify({'success': False, 'error': '未找到该标签'})

        result = _dataset_delete_label(ds_root, yaml_path, delete_id, splits=splits, delete_empty_files=True)
        return jsonify({'success': True, **result})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@bp.route('/api/dataset/update_tags', methods=['POST'])
def api_dataset_update_tags():
    try:
        data = request.get_json() or {}
        project_path = data.get('project_path')
        dataset_name = data.get('dataset_name')
        tags = data.get('tags') or []
        
        if not project_path or not dataset_name:
            return jsonify({'success': False, 'error': '缺少必要参数'})

        ds_candidates = [
            os.path.join(project_path, 'training', dataset_name),
            os.path.join(project_path, 'datasets', dataset_name),
        ]
        ds_root = None
        for p in ds_candidates:
            if p and os.path.isdir(p):
                ds_root = p
                break
        if not ds_root:
            return jsonify({'success': False, 'error': '数据集不存在'})

        yaml_path = os.path.join(ds_root, 'data.yaml')
        if not os.path.exists(yaml_path):
             # If data.yaml doesn't exist, create minimal one or error?
             # For raw datasets, maybe it doesn't exist.
             # We can create it just for tags.
             with open(yaml_path, 'w', encoding='utf-8') as f:
                 yaml.safe_dump({'tags': tags}, f, allow_unicode=True, sort_keys=False)
        else:
            with open(yaml_path, 'r', encoding='utf-8') as f:
                y = yaml.safe_load(f) or {}
            y['tags'] = tags
            with open(yaml_path, 'w', encoding='utf-8') as f:
                yaml.safe_dump(y, f, allow_unicode=True, sort_keys=False)
                
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@bp.route('/api/dataset/delete_folder', methods=['POST'])
def api_dataset_delete_folder():
    try:
        data = request.get_json() or {}
        project_path = data.get('project_path')
        dataset_name = data.get('dataset_name')
        dataset_path = data.get('dataset_path')
        if not project_path or not dataset_name:
            return jsonify({'success': False, 'error': '缺少必要参数'})

        project_real = os.path.realpath(project_path)

        candidates = []
        if dataset_path:
            candidates.append(dataset_path)
        else:
            candidates.append(os.path.join(project_path, 'training', dataset_name))
            candidates.append(os.path.join(project_path, 'datasets', dataset_name))

        deleted_path = None
        for p in candidates:
            if not p:
                continue
            rp = os.path.realpath(p)
            if not (rp == project_real or rp.startswith(project_real + os.sep)):
                continue
            if os.path.isdir(rp):
                shutil.rmtree(rp)
                deleted_path = rp
                break

        if not deleted_path:
            return jsonify({'success': False, 'error': '数据集不存在'})

        return jsonify({'success': True, 'deleted_path': deleted_path})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@bp.route('/api/dataset/validate', methods=['POST'])
def api_validate_dataset():
    """验证数据集"""
    try:
        data = request.get_json()
        dataset_path = data.get('dataset_path')
        
        if not dataset_path or not os.path.exists(dataset_path):
            return jsonify({'success': False, 'error': '数据集路径无效'})
        
        # 分析数据集
        dataset_info = ProjectManager.analyze_dataset(dataset_path)
        if not dataset_info:
            return jsonify({'success': False, 'error': '无法分析数据集'})
        
        # 检查是否可以进行训练
        validation_result = {
            'can_train': dataset_info['annotation_rate'] > 0.8,  # 标注率大于80%才能训练
            'can_validate': dataset_info['has_val'],
            'can_test': dataset_info['has_test'],
            'annotation_rate': dataset_info['annotation_rate'],
            'image_count': dataset_info['image_count'],
            'label_count': dataset_info['label_count']
        }
        
        return jsonify({
            'success': True,
            'validation': validation_result,
            'dataset_info': dataset_info
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@bp.route('/api/dataset/merge', methods=['POST'])
def api_dataset_merge():
    try:
        data = request.get_json() or {}
        project_path = data.get('project_path')
        dataset_a = data.get('dataset_a')
        dataset_b = data.get('dataset_b')
        new_dataset_name = data.get('new_dataset_name')

        if not project_path or not dataset_a or not dataset_b or not new_dataset_name:
            return jsonify({'success': False, 'error': '缺少必要参数'})
        if dataset_a == dataset_b:
            return jsonify({'success': False, 'error': '两个数据集不能相同'})

        project_real = os.path.realpath(project_path)

        def resolve_dataset_root(name):
            candidates = [
                os.path.join(project_path, 'training', name),
                os.path.join(project_path, 'datasets', name),
            ]
            for p in candidates:
                if not p:
                    continue
                rp = os.path.realpath(p)
                if not (rp == project_real or rp.startswith(project_real + os.sep)):
                    continue
                if os.path.isdir(rp):
                    return rp
            return None

        ds_a = resolve_dataset_root(dataset_a)
        ds_b = resolve_dataset_root(dataset_b)
        if not ds_a or not ds_b:
            return jsonify({'success': False, 'error': '数据集不存在'})

        target_root = os.path.realpath(os.path.join(project_path, 'training', new_dataset_name))
        if not (target_root == project_real or target_root.startswith(project_real + os.sep)):
            return jsonify({'success': False, 'error': '非法路径'})
        if os.path.exists(target_root):
            return jsonify({'success': False, 'error': f'数据集 {new_dataset_name} 已存在'})

        def pick_yaml(ds_root):
            p1 = os.path.join(ds_root, 'data.yaml')
            if os.path.exists(p1):
                return p1
            p2 = os.path.join(ds_root, 'dataset.yaml')
            if os.path.exists(p2):
                return p2
            return None

        def load_names_list(ds_root):
            ypath = pick_yaml(ds_root)
            if ypath and os.path.exists(ypath):
                try:
                    with open(ypath, 'r', encoding='utf-8') as f:
                        y = yaml.safe_load(f) or {}
                    names = y.get('names')
                    if isinstance(names, list):
                        return [str(x) for x in names]
                    if isinstance(names, dict):
                        pairs = []
                        for k, v in names.items():
                            try:
                                kk = int(k)
                            except Exception:
                                continue
                            pairs.append((kk, v))
                        if pairs:
                            return [str(v) for _, v in sorted(pairs, key=lambda x: x[0])]
                        return [str(v) for v in names.values()]
                except Exception:
                    pass
            info = ProjectManager.analyze_dataset(ds_root) or {}
            v = info.get('names') or []
            if isinstance(v, list):
                return [str(x) for x in v]
            return []

        names_a = load_names_list(ds_a)
        names_b = load_names_list(ds_b)
        if not names_a or not names_b:
            return jsonify({'success': False, 'error': '无法读取数据集类别信息'})
        if names_a != names_b:
            return jsonify({'success': False, 'error': '两个数据集类别不一致，无法合并', 'names_a': names_a, 'names_b': names_b})

        os.makedirs(target_root, exist_ok=False)
        for split in ('train', 'val', 'test'):
            os.makedirs(os.path.join(target_root, split, 'images'), exist_ok=True)
            os.makedirs(os.path.join(target_root, split, 'labels'), exist_ok=True)

        yaml_out = {
            'path': target_root,
            'train': 'train/images',
            'val': 'val/images',
            'test': 'test/images',
            'names': names_a,
        }
        with open(os.path.join(target_root, 'dataset.yaml'), 'w', encoding='utf-8') as f:
            yaml.safe_dump(yaml_out, f, allow_unicode=True, sort_keys=False)

        def resolve_split_dirs(ds_root, split):
            img_dir = os.path.join(ds_root, split, 'images')
            if os.path.isdir(img_dir):
                manual_v1 = os.path.join(ds_root, split, 'labels')
                manual_v2 = os.path.join(ds_root, 'labels', split)
                lbl_dir = manual_v1 if (os.path.isdir(manual_v1) or not os.path.isdir(manual_v2)) else manual_v2
                return img_dir, lbl_dir

            if split == 'train':
                img_dir2 = os.path.join(ds_root, 'images')
                if os.path.isdir(img_dir2):
                    lbl_dir2 = os.path.join(ds_root, 'labels')
                    return img_dir2, lbl_dir2
            return None, None

        def copy_dataset_into(ds_root, src_tag):
            stats = {'copied_images': 0, 'copied_labels': 0, 'renamed_images': 0, 'missing_labels': 0}
            for split in ('train', 'val', 'test'):
                src_img_dir, src_lbl_dir = resolve_split_dirs(ds_root, split)
                if not src_img_dir:
                    continue
                dst_img_dir = os.path.join(target_root, split, 'images')
                dst_lbl_dir = os.path.join(target_root, split, 'labels')

                for root, dirs, files in os.walk(src_img_dir):
                    dirs.sort()
                    files.sort()
                    for fn in files:
                        if not fn.lower().endswith(('.jpg', '.jpeg', '.png', '.bmp')):
                            continue
                        src_img = os.path.join(root, fn)
                        rel = os.path.relpath(src_img, src_img_dir)
                        rel_dir = os.path.dirname(rel)
                        base, ext = os.path.splitext(os.path.basename(rel))
                        dst_dir = os.path.join(dst_img_dir, rel_dir) if rel_dir else dst_img_dir
                        os.makedirs(dst_dir, exist_ok=True)

                        dst_img = os.path.join(dst_dir, base + ext)
                        dst_base = base
                        if os.path.exists(dst_img):
                            idx = 1
                            while True:
                                candidate_base = f"{base}_{src_tag}{idx}"
                                candidate_img = os.path.join(dst_dir, candidate_base + ext)
                                if not os.path.exists(candidate_img):
                                    dst_img = candidate_img
                                    dst_base = candidate_base
                                    stats['renamed_images'] += 1
                                    break
                                idx += 1

                        shutil.copy2(src_img, dst_img)
                        stats['copied_images'] += 1

                        lbl_src = None
                        if src_lbl_dir:
                            lbl_src = os.path.join(src_lbl_dir, os.path.splitext(rel)[0] + '.txt')
                            if not os.path.exists(lbl_src):
                                lbl_src = None

                        dst_lbl_dir2 = os.path.join(dst_lbl_dir, rel_dir) if rel_dir else dst_lbl_dir
                        os.makedirs(dst_lbl_dir2, exist_ok=True)
                        dst_lbl = os.path.join(dst_lbl_dir2, dst_base + '.txt')

                        if lbl_src:
                            shutil.copy2(lbl_src, dst_lbl)
                            stats['copied_labels'] += 1
                        else:
                            stats['missing_labels'] += 1
            return stats

        s1 = copy_dataset_into(ds_a, 'a')
        s2 = copy_dataset_into(ds_b, 'b')

        return jsonify({
            'success': True,
            'dataset_root': target_root,
            'dataset_a_root': ds_a,
            'dataset_b_root': ds_b,
            'names': names_a,
            'stats': {'a': s1, 'b': s2},
        })
    except Exception as e:
        try:
            if 'target_root' in locals() and target_root and os.path.isdir(target_root):
                shutil.rmtree(target_root)
        except Exception:
            pass
        return jsonify({'success': False, 'error': str(e)})

@bp.route('/api/dataset/split', methods=['POST'])
def api_dataset_split():
    import random
    try:
        data = request.get_json() or {}
        project_path = data.get('project_path')
        dataset_name = data.get('dataset_name')
        val_ratio = float(data.get('val_ratio', 0.1))
        test_ratio = float(data.get('test_ratio', 0))

        if not project_path or not dataset_name:
            return jsonify({'success': False, 'error': '缺少必要参数'})

        # Find dataset root
        ds_candidates = [
            os.path.join(project_path, 'training', dataset_name),
            os.path.join(project_path, 'datasets', dataset_name),
        ]
        ds_root = None
        for p in ds_candidates:
            if p and os.path.isdir(p):
                ds_root = p
                break
        if not ds_root:
            return jsonify({'success': False, 'error': '数据集不存在'})

        # Validation
        if val_ratio + test_ratio >= 1.0:
             return jsonify({'success': False, 'error': '验证集和测试集比例之和必须小于1'})

        # Collect all images and labels
        pairs = [] 
        
        subsets = ['train', 'val', 'test']
        for subset in subsets:
            img_dir = os.path.join(ds_root, subset, 'images')
            lbl_dir = os.path.join(ds_root, subset, 'labels')
            
            if not os.path.exists(img_dir):
                continue
                
            for f in os.listdir(img_dir):
                if f.lower().endswith(('.jpg', '.jpeg', '.png', '.bmp')):
                    img_path = os.path.join(img_dir, f)
                    name_no_ext = os.path.splitext(f)[0]
                    lbl_path = None
                    if os.path.exists(lbl_dir):
                        p = os.path.join(lbl_dir, name_no_ext + '.txt')
                        if os.path.exists(p):
                            lbl_path = p
                    
                    pairs.append({
                        'img': img_path,
                        'lbl': lbl_path,
                        'base': f,
                        'name_no_ext': name_no_ext
                    })

        if not pairs:
            return jsonify({'success': False, 'error': '未找到图片文件'})

        # Shuffle
        random.shuffle(pairs)
        
        total = len(pairs)
        n_val = int(total * val_ratio)
        n_test = int(total * test_ratio)
        n_train = total - n_val - n_test
        
        # Split
        train_set = pairs[:n_train]
        val_set = pairs[n_train:n_train+n_val]
        test_set = pairs[n_train+n_val:]
        
        # Use a temporary directory for safe moving
        with tempfile.TemporaryDirectory(dir=ds_root) as tmp_dir:
            # 1. Move all to temp staging
            for p in pairs:
                # Move image
                dst_img = os.path.join(tmp_dir, f"img_{p['base']}") 
                shutil.move(p['img'], dst_img)
                p['current_img'] = dst_img
                
                # Move label
                if p['lbl']:
                    dst_lbl = os.path.join(tmp_dir, f"lbl_{p['name_no_ext']}.txt")
                    shutil.move(p['lbl'], dst_lbl)
                    p['current_lbl'] = dst_lbl
                else:
                    p['current_lbl'] = None
            
            # 2. Clear/Re-create target directories
            for subset in subsets:
                # We don't remove the root subset dir to preserve other files (like cache), 
                # but we clean images/labels dirs.
                # Actually, simpler to just ensure they exist. 
                # Since we moved files OUT, they should be clean of the files we moved.
                # But there might be leftover files (e.g. non-images in images dir?).
                # Let's just ensure dirs exist.
                os.makedirs(os.path.join(ds_root, subset, 'images'), exist_ok=True)
                os.makedirs(os.path.join(ds_root, subset, 'labels'), exist_ok=True)
                
            # 3. Move from staging to targets
            def move_to_subset(items, subset):
                for item in items:
                    # Image
                    dst_img = os.path.join(ds_root, subset, 'images', item['base'])
                    if os.path.exists(dst_img): # Should not happen if names are unique
                        base, ext = os.path.splitext(item['base'])
                        dst_img = os.path.join(ds_root, subset, 'images', f"{base}_{random.randint(1000,9999)}{ext}")
                    shutil.move(item['current_img'], dst_img)
                    
                    # Label
                    if item['current_lbl']:
                        # Match the image name if we renamed image? 
                        # Assuming we didn't rename image or if we did we should rename label too.
                        # For now assume unique names.
                        dst_lbl = os.path.join(ds_root, subset, 'labels', item['name_no_ext'] + '.txt')
                        shutil.move(item['current_lbl'], dst_lbl)

            move_to_subset(train_set, 'train')
            move_to_subset(val_set, 'val')
            move_to_subset(test_set, 'test')

        return jsonify({
            'success': True, 
            'message': f'划分完成: 训练集 {len(train_set)}, 验证集 {len(val_set)}, 测试集 {len(test_set)}'
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)})

@bp.route('/api/dataset/diagnose')
def api_dataset_diagnose():
    try:
        project_path = request.args.get('project_path')
        training_id = request.args.get('training_id')
        if not project_path:
            return jsonify({'success': False, 'error': '缺少项目路径'})
        cfg = None
        base = os.path.join(project_path, 'training_outputs')
        if training_id:
            if os.path.exists(base):
                for ds in os.listdir(base):
                    p = os.path.join(base, ds, training_id, 'training_config.json')
                    if os.path.exists(p):
                        cfg = p
                        break
        else:
            _, training_id = TrainingManager.get_latest_run_dir(project_path)
            if training_id and os.path.exists(base):
                for ds in os.listdir(base):
                    p = os.path.join(base, ds, training_id, 'training_config.json')
                    if os.path.exists(p):
                        cfg = p
                        break
        dataset_yaml = None
        if cfg and os.path.exists(cfg):
            try:
                with open(cfg, 'r', encoding='utf-8') as f:
                    j = json.load(f)
                    dataset_yaml = j.get('dataset_yaml')
            except Exception:
                pass
        diag = {'training_id': training_id, 'dataset_yaml': dataset_yaml}
        images_train = None; labels_train = None
        exists_images = False; exists_labels = False
        if dataset_yaml and os.path.exists(dataset_yaml):
            try:
                with open(dataset_yaml, 'r', encoding='utf-8') as f:
                    y = yaml.safe_load(f) or {}
                base_path = y.get('path') or os.path.dirname(dataset_yaml)
                def ap(p):
                    return p if (p and os.path.isabs(p)) else (os.path.join(base_path, p) if p else None)
                images_train = ap(y.get('train')) or os.path.join(base_path, 'images', 'train')
                labels_train = os.path.join(base_path, 'labels', 'train')
                exists_images = bool(images_train and os.path.exists(images_train))
                exists_labels = bool(labels_train and os.path.exists(labels_train))
            except Exception:
                pass
        diag.update({
            'images_train': images_train,
            'labels_train': labels_train,
            'exists_images_train': exists_images,
            'exists_labels_train': exists_labels,
        })
        msg = ''
        if not exists_images:
            msg = '缺少 images/train 目录；请在 dataset.yaml 设置 path 与 train 或创建该目录'
        elif not exists_labels:
            msg = '缺少 labels/train 目录；将按图片均匀采样，不做类别均匀'
        return jsonify({'success': True, 'diagnose': diag, 'message': msg})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})
