from flask import Blueprint, jsonify, request
import os
import sys
import json
import yaml
import shutil

# Ensure parent directory is in sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from managers.project_manager import ProjectManager
from managers.training_manager import TrainingManager

bp = Blueprint('dataset', __name__)

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
        
        if not project_path or not dataset_name:
            return jsonify({'success': False, 'error': '缺少必要参数'})
            
        ds_root = os.path.join(project_path, 'training', dataset_name)
        img_dir = os.path.join(ds_root, split, 'images')
        lbl_dir = os.path.join(ds_root, split, 'labels')
        
        if not os.path.exists(img_dir):
            return jsonify({'success': True, 'images': [], 'total': 0})
            
        def parse_bool(v):
            if v is None:
                return False
            if isinstance(v, bool):
                return v
            return str(v).strip().lower() in ('1', 'true', 'yes', 'y', 'on')

        unannotated = parse_bool(unannotated_raw)

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
