import os
import sys
import logging
from flask import Flask, send_from_directory
from flask_cors import CORS

# Ensure current directory is in sys.path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from routes import register_blueprints

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

app = Flask(__name__, static_folder='dist', static_url_path='')
CORS(app)

# 注册路由
register_blueprints(app)

# 首页路由 (前端)
@app.route('/')
def index():
    return send_from_directory(app.static_folder, 'index.html')

<<<<<<< HEAD
# 静态资源路由 (Vue Router History Mode support)
@app.errorhandler(404)
def not_found(e):
    if app.static_folder:
        return send_from_directory(app.static_folder, 'index.html')
    return "Not Found", 404
=======
@app.route('/api/projects')
def api_projects():
    """获取项目列表"""
    try:
        projects = ProjectManager.scan_projects()
        return jsonify({
            'success': True,
            'projects': projects
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/training/start', methods=['POST'])
def api_start_training():
    """开始训练任务"""
    try:
        data = request.get_json()
        project_path = data.get('project_path')
        dataset_name = data.get('dataset_name')
        model_name = data.get('model_name')
        training_config = data.get('training_config', {})
        dataset_path = data.get('dataset_path')
        
        result = TrainingManager.start_training(project_path, dataset_name, model_name, training_config, dataset_path)
        return jsonify(result)
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/training/stop', methods=['POST'])
def api_stop_training():
    """停止训练任务"""
    try:
        global training_status
        if training_status.get('is_running'):
            training_status['is_running'] = False
            training_status['message'] = '训练已停止'
            return jsonify({'success': True, 'message': '训练任务已停止'})
        else:
            return jsonify({'success': False, 'error': '没有正在运行的训练任务'})
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/training/status')
def api_training_status():
    """获取训练状态"""
    try:
        status = training_status.copy()
        return jsonify({
            'success': True,
            'status': status
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/training/history')
def api_training_history():
    """获取训练历史"""
    try:
        project_path = request.args.get('project_path')
        dataset_name = request.args.get('dataset_name')
        if not project_path:
            return jsonify({'success': False, 'error': '缺少项目路径'})
        # Use get_training_runs which now supports all datasets if dataset_name is None
        runs = TrainingManager.get_training_runs(project_path, dataset_name)
        return jsonify({
            'success': True,
            'history': runs
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/models')
def api_models():
    """获取预训练模型列表"""
    try:
        models = ModelManager.get_pretrained_models()
        return jsonify({
            'success': True,
            'models': models
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/training/artifacts')
def api_training_artifacts():
    try:
        project_path = request.args.get('project_path')
        training_id = request.args.get('training_id')
        if not project_path:
            return jsonify({'success': False, 'error': '缺少项目路径'})
        artifacts = TrainingManager.get_latest_artifacts(project_path, training_id)
        metrics = {}
        csv_path = artifacts.get('results_csv')
        if csv_path and os.path.exists(csv_path):
            try:
                with open(csv_path, 'r') as f:
                    rows = list(csv.DictReader(f))
                    if rows:
                        metrics = rows[-1]
            except Exception:
                pass
        
        # 获取训练元数据
        metadata = {}
        base = os.path.join(project_path, 'training_outputs')
        if os.path.exists(base):
            # 如果指定了training_id，尝试查找对应的配置文件
            if training_id:
                for ds in os.listdir(base):
                    cfg_path = os.path.join(base, ds, training_id, 'training_config.json')
                    if os.path.exists(cfg_path):
                        try:
                            with open(cfg_path, 'r', encoding='utf-8') as f:
                                metadata = json.load(f)
                        except Exception:
                            pass
                        break
        
        def url_for_path(p):
            return f"/api/file?path={p}" if p else ''
        def to_url(v):
            if isinstance(v, str):
                return url_for_path(v)
            if isinstance(v, (list, tuple)):
                return [url_for_path(x) for x in v]
            return v
        artifacts = {k: to_url(v) for k, v in artifacts.items()}
        return jsonify({'success': True, 'artifacts': artifacts, 'metrics': metrics, 'metadata': metadata})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/training/artifact', methods=['DELETE'])
def api_delete_training_artifact():
    try:
        project_path = request.args.get('project_path')
        training_id = request.args.get('training_id')
        if not project_path or not training_id:
            return jsonify({'success': False, 'error': '缺少必要参数'})
            
        base = os.path.join(project_path, 'training_outputs')
        deleted = False
        if os.path.exists(base):
            for ds in os.listdir(base):
                t_dir = os.path.join(base, ds, training_id)
                if os.path.isdir(t_dir):
                    import shutil
                    shutil.rmtree(t_dir)
                    deleted = True
                    break
        
        if deleted:
            return jsonify({'success': True})
        else:
            return jsonify({'success': False, 'error': '未找到指定训练记录'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

# 统一数据集接口：返回 training/ 下所有以 datasets* 命名的子目录
@app.route('/api/datasets')
def api_datasets():
    try:
        project_path = request.args.get('project_path')
        if not project_path:
            return jsonify({'success': False, 'error': '缺少项目路径'})
        info = ProjectManager.load_project_info(project_path)
        dsets = info.get('datasets', {}) if info else {}
        return jsonify({'success': True, 'datasets': {'trainable': dsets.get('trainable', [])}})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

# 数据集详情
@app.route('/api/dataset/info')
def api_dataset_info():
    try:
        project_path = request.args.get('project_path')
        dataset_name = request.args.get('dataset_name')
        if not project_path or not dataset_name:
            return jsonify({'success': False, 'error': '缺少必要参数'})
        ds_path = os.path.join(project_path, 'training', dataset_name)
        if not os.path.isdir(ds_path):
            # 兼容 dataset_name 传入完整路径或非标准命名
            alt = os.path.join(project_path, 'training')
            for entry in os.listdir(alt):
                if entry.startswith('datasets') and os.path.isdir(os.path.join(alt, entry)):
                    if os.path.basename(os.path.join(alt, entry)) == dataset_name:
                        ds_path = os.path.join(alt, entry)
                        break
        info = ProjectManager.analyze_training_structure(ds_path) or {}
        names = []
        nc = None
        yfile = None
        for fn in ('dataset.yaml', 'data.yaml'):
            p = os.path.join(ds_path, fn)
            if os.path.exists(p):
                yfile = p
                break
        if not yfile:
            for f in os.listdir(ds_path):
                if f.endswith(('.yaml', '.yml')):
                    yfile = os.path.join(ds_path, f)
                    break
        if yfile and os.path.exists(yfile):
            try:
                with open(yfile, 'r', encoding='utf-8') as f:
                    y = yaml.safe_load(f) or {}
                n = y.get('names')
                if isinstance(n, dict):
                    names = [n[k] for k in sorted(n.keys(), key=lambda x: int(x))]
                elif isinstance(n, list):
                    names = n
                nc = y.get('nc')
            except Exception:
                pass
        
        # 统计分类数量和占比
        class_counts = {}
        total_objects = 0
        splits = ['train', 'val', 'test']
        for split in splits:
            lbl_dir = os.path.join(ds_path, split, 'labels')
            if not os.path.exists(lbl_dir):
                continue
                
            for root, _, fs in os.walk(lbl_dir):
                for f in fs:
                    if not f.endswith('.txt'):
                        continue
                    try:
                        with open(os.path.join(root, f), 'r') as lf:
                            for line in lf:
                                parts = line.strip().split()
                                if parts:
                                    try:
                                        cls_id = int(float(parts[0]))
                                        class_counts[cls_id] = class_counts.get(cls_id, 0) + 1
                                        total_objects += 1
                                    except ValueError:
                                        pass
                    except Exception:
                        pass
        
        class_stats = []
        if names:
            for idx, name in enumerate(names):
                cnt = class_counts.get(idx, 0)
                pct = (cnt / total_objects * 100) if total_objects > 0 else 0
                class_stats.append({
                    'id': idx,
                    'name': name,
                    'count': cnt,
                    'percentage': round(pct, 2)
                })
        else:
            for idx in sorted(class_counts.keys()):
                cnt = class_counts[idx]
                pct = (cnt / total_objects * 100) if total_objects > 0 else 0
                class_stats.append({
                    'id': idx,
                    'name': str(idx),
                    'count': cnt,
                    'percentage': round(pct, 2)
                })
        
        info['names'] = names
        info['class_stats'] = class_stats
        info['total_objects'] = total_objects
        if nc is not None:
            info['nc'] = nc
        return jsonify({'success': True, 'info': info})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

# 数据集图片分页
@app.route('/api/dataset/images')
def api_dataset_images():
    try:
        project_path = request.args.get('project_path')
        dataset_name = request.args.get('dataset_name')
        split = request.args.get('split', 'train')
        offset = int(request.args.get('offset', '0'))
        limit = int(request.args.get('limit', '50'))
        classes_param = request.args.get('classes', '')
        mode = request.args.get('mode', 'include')
        unannotated_only = request.args.get('unannotated', 'false') == 'true'
        if not project_path or not dataset_name:
            return jsonify({'success': False, 'error': '缺少必要参数'})
        ds_root = os.path.join(project_path, 'training', dataset_name)
        base = os.path.join(ds_root, split, 'images')
        auto_lbl_base = os.path.join(ds_root, 'auto_labels', split)
        lbl_dir = os.path.join(ds_root, split, 'labels')
        files = []
        total = 0
        if os.path.exists(base):
            all = []
            for root, _, fs in os.walk(base):
                for f in fs:
                    if f.lower().endswith(('.jpg', '.jpeg', '.png')):
                        all.append(os.path.join(root, f))
            if classes_param or unannotated_only:
                class_ids = set()
                if classes_param:
                    yfile = None
                    for fn in ('dataset.yaml', 'data.yaml'):
                        p = os.path.join(ds_root, fn)
                        if os.path.exists(p):
                            yfile = p
                            break
                    names = []
                    if yfile and os.path.exists(yfile):
                        try:
                            with open(yfile, 'r', encoding='utf-8') as f:
                                y = yaml.safe_load(f) or {}
                            n = y.get('names')
                            if isinstance(n, dict):
                                names = [n[k] for k in sorted(n.keys(), key=lambda x: int(x))]
                            elif isinstance(n, list):
                                names = n
                        except Exception:
                            names = []
                    tokens = [t.strip() for t in classes_param.split(',') if t.strip()]
                    for t in tokens:
                        if t.isdigit():
                            try:
                                class_ids.add(int(t))
                            except Exception:
                                pass
                        else:
                            try:
                                if names:
                                    for i, nm in enumerate(names):
                                        if str(nm) == t:
                                            class_ids.add(i)
                                            break
                            except Exception:
                                pass

                filtered = []
                for p in all:
                    rel = os.path.relpath(p, base)
                    lblp = os.path.join(lbl_dir, os.path.splitext(rel)[0] + '.txt')

                    # 尝试其他目录结构
                    if not os.path.exists(lblp):
                        # 尝试 labels/split 结构
                        # base 是 split/images
                        # lbl_dir 是 split/labels
                        # 尝试 project/labels/split/xxxx.txt
                        # 假设 dataset_name/split/images -> dataset_name/labels/split
                        maybe_lbl_dir = os.path.join(ds_root, 'labels', split)
                        maybe_lblp = os.path.join(maybe_lbl_dir, os.path.splitext(rel)[0] + '.txt')
                        if os.path.exists(maybe_lblp):
                            lblp = maybe_lblp
                    
                    has_annotation = os.path.exists(lblp)

                    # 仅筛选未标注
                    if unannotated_only:
                        if not has_annotation:
                            filtered.append(p)
                        continue

                    has = False
                    if has_annotation:
                        try:
                            with open(lblp, 'r', encoding='utf-8') as f:
                                for line in f:
                                    s = line.strip().split()
                                    if not s:
                                        continue
                                    try:
                                        cid = int(float(s[0]))
                                    except Exception:
                                        continue
                                    if cid in class_ids:
                                        has = True
                                        break
                        except Exception:
                            has = False
                    if mode == 'include':
                        if has:
                            filtered.append(p)
                    else:
                        if not has:
                            filtered.append(p)
                all = filtered
            total = len(all)
            page = all[offset:offset+limit]
            files = []
            for p in page:
                rel = os.path.relpath(p, base)
                lbl = os.path.join(auto_lbl_base, os.path.splitext(rel)[0] + '.txt')
                files.append({'url': f"/api/file?path={p}", 'path': p, 'pending': os.path.exists(lbl)})
        return jsonify({'success': True, 'images': files, 'total': total})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/dataset/create_subset', methods=['POST'])
def create_subset():
    try:
        data = request.json
        project_path = data.get('project_path')
        source_dataset = data.get('source_dataset')
        new_dataset_name = data.get('new_dataset_name')
        image_paths = data.get('image_paths', [])

        if not all([project_path, source_dataset, new_dataset_name]) or not image_paths:
            return jsonify({'success': False, 'error': '参数不完整或未选择图片'})

        # Check if new dataset exists
        new_dataset_dir = os.path.join(project_path, 'training', new_dataset_name)
        if os.path.exists(new_dataset_dir):
            return jsonify({'success': False, 'error': '目标数据集名称已存在'})

        # Create directories
        # Default structure: put all selected images into 'train' split of the new dataset
        target_train_img_dir = os.path.join(new_dataset_dir, 'train', 'images')
        target_train_lbl_dir = os.path.join(new_dataset_dir, 'train', 'labels')
        os.makedirs(target_train_img_dir, exist_ok=True)
        os.makedirs(target_train_lbl_dir, exist_ok=True)
        
        # Also create val/test dirs just in case (empty)
        os.makedirs(os.path.join(new_dataset_dir, 'val', 'images'), exist_ok=True)
        os.makedirs(os.path.join(new_dataset_dir, 'val', 'labels'), exist_ok=True)
        os.makedirs(os.path.join(new_dataset_dir, 'test', 'images'), exist_ok=True)
        os.makedirs(os.path.join(new_dataset_dir, 'test', 'labels'), exist_ok=True)

        # Copy images and labels
        import shutil
        success_count = 0
        
        for img_path in image_paths:
            if not os.path.exists(img_path):
                continue
                
            # Copy image
            fname = os.path.basename(img_path)
            shutil.copy2(img_path, os.path.join(target_train_img_dir, fname))
            
            # Try to copy label
            # Assume standard structure: .../images/xxx.jpg -> .../labels/xxx.txt
            # Or adjacent?
            # Using the logic similar to get_label_path
            label_path = None
            
            # Check standard 'images' -> 'labels' replacement
            parent = os.path.dirname(img_path)
            if parent.endswith('images'):
                lbl_dir = os.path.join(os.path.dirname(parent), 'labels')
                base_name = os.path.splitext(fname)[0]
                candidate = os.path.join(lbl_dir, base_name + '.txt')
                if os.path.exists(candidate):
                    label_path = candidate
            
            if label_path:
                shutil.copy2(label_path, os.path.join(target_train_lbl_dir, os.path.basename(label_path)))
            
            success_count += 1

        # Create dataset.yaml
        # Try to read source dataset.yaml to get class names
        source_dir = os.path.join(project_path, 'training', source_dataset)
        names = {}
        nc = 0
        
        # Find source yaml
        source_yaml = None
        for f in ['dataset.yaml', 'data.yaml']:
            p = os.path.join(source_dir, f)
            if os.path.exists(p):
                source_yaml = p
                break
        
        if source_yaml:
            try:
                with open(source_yaml, 'r') as f:
                    y = yaml.safe_load(f)
                    names = y.get('names', {})
                    nc = y.get('nc', 0)
            except:
                pass
        
        new_yaml_content = {
            'path': new_dataset_dir,
            'train': 'train/images',
            'val': 'val/images',
            'test': 'test/images',
            'nc': nc,
            'names': names
        }
        
        with open(os.path.join(new_dataset_dir, 'dataset.yaml'), 'w') as f:
            yaml.safe_dump(new_yaml_content, f, allow_unicode=True, sort_keys=False)

        return jsonify({'success': True, 'count': success_count, 'message': f'成功创建数据集 {new_dataset_name}，包含 {success_count} 张图片'})

    except Exception as e:
        print(traceback.format_exc())
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/dataset/split', methods=['POST'])
def split_dataset():
    try:
        data = request.json
        project_path = data.get('project_path')
        dataset_name = data.get('dataset_name')
        val_ratio = float(data.get('val_ratio', 0.2))
        test_ratio = float(data.get('test_ratio', 0.0))
        
        if not project_path or not dataset_name:
             return jsonify({'success': False, 'error': 'Missing parameters'})
             
        dataset_dir = os.path.join(project_path, 'training', dataset_name)
        if not os.path.exists(dataset_dir):
            return jsonify({'success': False, 'error': 'Dataset not found'})
            
        # 1. Collect all images and labels
        all_items = [] 
        
        for split in ['train', 'val', 'test']:
            img_dir = os.path.join(dataset_dir, split, 'images')
            lbl_dir = os.path.join(dataset_dir, split, 'labels')
            
            if os.path.exists(img_dir):
                for f in os.listdir(img_dir):
                    if f.lower().endswith(('.jpg', '.jpeg', '.png', '.bmp')):
                        img_path = os.path.join(img_dir, f)
                        lbl_name = os.path.splitext(f)[0] + '.txt'
                        lbl_path = os.path.join(lbl_dir, lbl_name) if os.path.exists(lbl_dir) else None
                        
                        if lbl_path and not os.path.exists(lbl_path):
                            lbl_path = None
                            
                        all_items.append({'image': img_path, 'label': lbl_path, 'filename': f})

        if not all_items:
             return jsonify({'success': False, 'error': 'No images found'})
             
        # 2. Shuffle
        random.shuffle(all_items)
        
        # 3. Calculate counts
        total = len(all_items)
        val_count = int(total * val_ratio)
        test_count = int(total * test_ratio)
        train_count = total - val_count - test_count
        
        # 4. Use temp dir to avoid conflicts
        temp_dir = os.path.join(dataset_dir, 'temp_split_staging_' + str(int(time.time())))
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)
        os.makedirs(temp_dir)
        
        for item in all_items:
            shutil.move(item['image'], os.path.join(temp_dir, item['filename']))
            item['temp_image'] = os.path.join(temp_dir, item['filename'])
            if item['label']:
                lbl_name = os.path.basename(item['label'])
                shutil.move(item['label'], os.path.join(temp_dir, lbl_name))
                item['temp_label'] = os.path.join(temp_dir, lbl_name)
            else:
                item['temp_label'] = None
                
        # 5. Clear and Re-create structure
        for split in ['train', 'val', 'test']:
            idir = os.path.join(dataset_dir, split, 'images')
            ldir = os.path.join(dataset_dir, split, 'labels')
            os.makedirs(idir, exist_ok=True)
            os.makedirs(ldir, exist_ok=True)
            
        # 6. Distribute
        splits = []
        splits.extend(['train'] * train_count)
        splits.extend(['val'] * val_count)
        splits.extend(['test'] * test_count)
        
        while len(splits) < total:
            splits.insert(0, 'train')
            
        for i, item in enumerate(all_items):
            target_split = splits[i]
            target_img_dir = os.path.join(dataset_dir, target_split, 'images')
            target_lbl_dir = os.path.join(dataset_dir, target_split, 'labels')
            
            shutil.move(item['temp_image'], os.path.join(target_img_dir, item['filename']))
            
            if item['temp_label']:
                lbl_name = os.path.basename(item['temp_label'])
                shutil.move(item['temp_label'], os.path.join(target_lbl_dir, lbl_name))
                
        shutil.rmtree(temp_dir)
        
        return jsonify({'success': True, 'counts': {'train': train_count, 'val': val_count, 'test': test_count}})
        
    except Exception as e:
        print(traceback.format_exc())
        return jsonify({'success': False, 'error': str(e)})

# 未标注图片列表
@app.route('/api/annotation/missing')
def api_annotation_missing():
    try:
        project_path = request.args.get('project_path')
        dataset_name = request.args.get('dataset_name')
        split = request.args.get('split', 'train')
        offset = int(request.args.get('offset', '0'))
        limit = int(request.args.get('limit', '50'))
        if not project_path or not dataset_name:
            return jsonify({'success': False, 'error': '缺少必要参数'})
        ds_root = os.path.join(project_path, 'training', dataset_name)
        img_dir = os.path.join(ds_root, split, 'images')
        lbl_dir = os.path.join(ds_root, split, 'labels')
        items = []
        if os.path.exists(img_dir):
            all_imgs = []
            for root, _, fs in os.walk(img_dir):
                for f in fs:
                    if f.lower().endswith(('.jpg', '.jpeg', '.png')):
                        p = os.path.join(root, f)
                        rel = os.path.relpath(p, img_dir)
                        lbl = os.path.join(lbl_dir, os.path.splitext(rel)[0] + '.txt')
                        if not os.path.exists(lbl):
                            all_imgs.append(p)
            total = len(all_imgs)
            page = all_imgs[offset:offset+limit]
            items = [f"/api/file?path={p}" for p in page]
            return jsonify({'success': True, 'images': items, 'total': total})
        return jsonify({'success': True, 'images': [], 'total': 0})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

# 自动标注
@app.route('/api/auto_annotate', methods=['POST'])
def api_auto_annotate():
    try:
        data = request.get_json() or {}
        project_path = data.get('project_path')
        dataset_name = data.get('dataset_name')
        image_path = data.get('image_path')
        threshold = float(data.get('threshold', 0.25))
        max_boxes = int(data.get('max_boxes', 100))
        if not project_path or not dataset_name or not image_path:
            return jsonify({'success': False, 'error': '缺少必要参数'})
        model = _get_auto_annotate_model(project_path, prefer_project_best=True)
        if model is None:
            return jsonify({'success': False, 'error': '自动标注模型不可用'})
        # 运行推理
        res = model.predict(image_path, conf=threshold, max_det=max_boxes, verbose=False)
        boxes = []
        try:
            out = res[0]
            for b in out.boxes:
                xyxy = b.xyxy[0].tolist()
                cls = int(b.cls.item()) if hasattr(b, 'cls') else 0
                conf = float(b.conf.item()) if hasattr(b, 'conf') else 0.0
                boxes.append({'class': cls, 'conf': conf, 'x1': xyxy[0], 'y1': xyxy[1], 'x2': xyxy[2], 'y2': xyxy[3]})
        except Exception:
            boxes = []
        return jsonify({'success': True, 'boxes': boxes})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

# 批量自动标注
@app.route('/api/auto_annotate/batch', methods=['POST'])
def api_auto_annotate_batch():
    try:
        global batch_status
        data = request.get_json() or {}
        project_path = data.get('project_path')
        dataset_name = data.get('dataset_name')
        split = data.get('split', 'train')
        model_path = data.get('model_path')
        conf = float(data.get('conf', 0.25))
        max_det = int(data.get('max_det', 200))
        batch_size = int(data.get('batch_size', 1))
        if not project_path or not dataset_name:
            return jsonify({'success': False, 'error': '缺少必要参数'})
        from ultralytics import YOLO
        model = YOLO(model_path) if model_path else _get_auto_annotate_model(project_path, prefer_project_best=True)
        if model is None:
            return jsonify({'success': False, 'error': '模型不可用'})
        ds_root = os.path.join(project_path, 'training', dataset_name)
        img_dir = os.path.join(ds_root, split, 'images')
        lbl_dir = os.path.join(ds_root, 'auto_labels', split)
        os.makedirs(lbl_dir, exist_ok=True)
        images = []
        for root, _, fs in os.walk(img_dir):
            for f in fs:
                if f.lower().endswith(('.jpg', '.jpeg', '.png')):
                    images.append(os.path.join(root, f))
        images.sort()
        total = len(images)
        batch_status.update({'is_running': True, 'progress': 0, 'message': '执行批量自动标注...'})
        added = 0
        pending = 0
        def to_lbl(p):
            rel = os.path.relpath(p, img_dir)
            return os.path.join(lbl_dir, os.path.splitext(rel)[0] + '.txt')
        # 批量推理
        for i in range(0, len(images), batch_size):
            batch = images[i:i+batch_size]
            try:
                results = model.predict(batch, conf=conf, max_det=max_det, verbose=False)
            except Exception:
                continue
            for bi, res in enumerate(results):
                img_path = batch[bi]
                auto_lbl_path = to_lbl(img_path)
                boxes = []
                try:
                    for b in res.boxes:
                        xyxy = b.xyxy[0].tolist()
                        cls = int(b.cls.item()) if hasattr(b, 'cls') else 0
                        boxes.append({'class': cls, 'x1': xyxy[0], 'y1': xyxy[1], 'x2': xyxy[2], 'y2': xyxy[3]})
                except Exception:
                    boxes = []
                if not boxes:
                    continue
                # 写入到 auto_labels（不修改人工 labels）
                try:
                    from PIL import Image
                    with Image.open(img_path) as im:
                        w, h = im.size
                except Exception:
                    w, h = 1, 1
                # 读取已有人工与自动标签用于去重
                def _read_yolo(file_path):
                    arr = []
                    if not os.path.exists(file_path):
                        return arr
                    try:
                        with open(file_path, 'r', encoding='utf-8') as f:
                            for ln in f:
                                parts = ln.strip().split()
                                if len(parts) >= 5:
                                    cid = int(float(parts[0]))
                                    cx = float(parts[1]) * w
                                    cy = float(parts[2]) * h
                                    ww = float(parts[3]) * w
                                    hh = float(parts[4]) * h
                                    x1 = max(0.0, cx - ww/2)
                                    y1 = max(0.0, cy - hh/2)
                                    x2 = min(float(w), cx + ww/2)
                                    y2 = min(float(h), cy + hh/2)
                                    arr.append({'class': cid, 'x1': x1, 'y1': y1, 'x2': x2, 'y2': y2})
                    except Exception:
                        return arr
                    return arr
                manual_lbl = os.path.join(ds_root, 'labels', split, os.path.splitext(os.path.relpath(img_path, img_dir))[0] + '.txt')
                # 尝试更通用的路径查找，如果默认路径不存在
                if not os.path.exists(manual_lbl):
                     # 尝试在上级目录找 labels
                     alt_lbl = os.path.join(ds_root, split, 'labels', os.path.splitext(os.path.relpath(img_path, img_dir))[0] + '.txt')
                     if os.path.exists(alt_lbl):
                         manual_lbl = alt_lbl
                     else:
                         # 尝试标准 YOLO 结构 ../labels/
                         parent = os.path.dirname(os.path.dirname(img_path))
                         alt_lbl_2 = os.path.join(parent, 'labels', os.path.basename(os.path.splitext(img_path)[0]) + '.txt')
                         if os.path.exists(alt_lbl_2):
                             manual_lbl = alt_lbl_2

                exist_manual = _read_yolo(manual_lbl)
                exist_auto = _read_yolo(auto_lbl_path)
                def _iou(a, b):
                    ix1 = max(a['x1'], b['x1']); iy1 = max(a['y1'], b['y1'])
                    ix2 = min(a['x2'], b['x2']); iy2 = min(a['y2'], b['y2'])
                    iw = max(0.0, ix2 - ix1); ih = max(0.0, iy2 - iy1)
                    inter = iw * ih
                    area_a = max(0.0, (a['x2']-a['x1'])) * max(0.0, (a['y2']-a['y1']))
                    area_b = max(0.0, (b['x2']-b['x1'])) * max(0.0, (b['y2']-b['y1']))
                    union = area_a + area_b - inter + 1e-6
                    return inter / union
                iou_thresh = float(data.get('iou_thresh', 0.7))
                filtered = []
                for l in boxes:
                    dup = False
                    for e in exist_manual:
                        if e['class'] == l['class'] and _iou(e, l) >= iou_thresh:
                            dup = True; break
                    if not dup:
                        for e in exist_auto:
                            if e['class'] == l['class'] and _iou(e, l) >= iou_thresh:
                                dup = True; break
                    if not dup:
                        filtered.append(l)
                if not filtered:
                    continue
                lines = []
                # 读取已有 auto 标签（允许追加）
                if os.path.exists(auto_lbl_path):
                    try:
                        with open(auto_lbl_path, 'r', encoding='utf-8') as f:
                            lines = [ln.strip() for ln in f if ln.strip()]
                    except Exception:
                        lines = []
                # 追加自动标注（标注来源不可见写入，可在旁文件记录）
                for l in filtered:
                    cx = ((l['x1'] + l['x2']) / 2.0) / w
                    cy = ((l['y1'] + l['y2']) / 2.0) / h
                    ww = (l['x2'] - l['x1']) / w
                    hh = (l['y2'] - l['y1']) / h
                    lines.append(f"{l['class']} {cx:.6f} {cy:.6f} {ww:.6f} {hh:.6f}")
                os.makedirs(os.path.dirname(auto_lbl_path), exist_ok=True)
                try:
                    with open(auto_lbl_path, 'w', encoding='utf-8') as f:
                        f.write('\n'.join(lines))
                    added += len(filtered)
                    pending += 1
                except Exception:
                    pass
            batch_status['progress'] = int((i + len(batch)) / total * 100) if total else 100
        batch_status.update({'is_running': False, 'message': '完成'})
        return jsonify({'success': True, 'count': len(images), 'added_boxes': added, 'pending_count': pending})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/auto_annotate/batch/status')
def api_auto_annotate_batch_status():
    global batch_status
    if 'batch_status' not in globals():
        batch_status = {'is_running': False, 'progress': 0, 'message': ''}
    return jsonify({'success': True, 'status': batch_status})

# 待复核列表：含最近自动标注的图片
@app.route('/api/annotation/pending')
def api_annotation_pending():
    try:
        project_path = request.args.get('project_path')
        dataset_name = request.args.get('dataset_name')
        split = request.args.get('split', 'train')
        offset = int(request.args.get('offset', '0'))
        limit = int(request.args.get('limit', '50'))
        if not project_path or not dataset_name:
            return jsonify({'success': False, 'error': '缺少必要参数'})
        ds_root = os.path.join(project_path, 'training', dataset_name)
        img_dir = os.path.join(ds_root, split, 'images')
        lbl_dir = os.path.join(ds_root, 'auto_labels', split)
        items = []
        for root, _, fs in os.walk(img_dir):
            for f in fs:
                if f.lower().endswith(('.jpg', '.jpeg', '.png')):
                    ip = os.path.join(root, f)
                    rel = os.path.relpath(ip, img_dir)
                    lp = os.path.join(lbl_dir, os.path.splitext(rel)[0] + '.txt')
                    if os.path.exists(lp):
                        items.append({'url': f"/api/file?path={ip}", 'path': ip})
        total = len(items)
        page = items[offset:offset+limit]
        return jsonify({'success': True, 'images': page, 'total': total})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

# 保存标注（转 YOLO 归一化）
@app.route('/api/annotation/save', methods=['POST'])
def api_annotation_save():
    try:
        data = request.get_json() or {}
        project_path = data.get('project_path')
        dataset_name = data.get('dataset_name')
        split = data.get('split', 'train')
        image_path = data.get('image_path')
        labels = data.get('labels') or []
        if not project_path or not dataset_name or not image_path:
            return jsonify({'success': False, 'error': '缺少必要参数'})
        # 获取尺寸
        try:
            from PIL import Image
            with Image.open(image_path) as im:
                w, h = im.size
        except Exception:
            return jsonify({'success': False, 'error': '无法读取图片尺寸'})
        # 写入 YOLO 文本
        ds_root = os.path.join(project_path, 'training', dataset_name)
        img_dir = os.path.join(ds_root, split, 'images')
        lbl_dir = os.path.join(ds_root, split, 'labels')
        auto_dir = os.path.join(ds_root, 'auto_labels', split)
        os.makedirs(lbl_dir, exist_ok=True)
        rel = os.path.relpath(image_path, img_dir)
        rel_noext = os.path.splitext(rel)[0]
        lbl_path = os.path.join(lbl_dir, rel_noext + '.txt')
        auto_path = os.path.join(auto_dir, rel_noext + '.txt')
        lines = []
        for l in labels:
            cls = int(l.get('class', 0))
            x1, y1, x2, y2 = float(l['x1']), float(l['y1']), float(l['x2']), float(l['y2'])
            cx = ((x1 + x2) / 2.0) / w
            cy = ((y1 + y2) / 2.0) / h
            ww = (x2 - x1) / w
            hh = (y2 - y1) / h
            lines.append(f"{cls} {cx:.6f} {cy:.6f} {ww:.6f} {hh:.6f}")
        with open(lbl_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(lines))
        # 保存后若存在对应 auto_labels，则删除以完成合并效果
        try:
            if os.path.exists(auto_path):
                os.remove(auto_path)
        except Exception:
            pass
        return jsonify({'success': True, 'label_path': lbl_path})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

# 读取标签
@app.route('/api/annotation/get')
def api_annotation_get():
    try:
        project_path = request.args.get('project_path')
        dataset_name = request.args.get('dataset_name')
        split = request.args.get('split', 'train')
        image_path = request.args.get('image_path')
        if not project_path or not dataset_name or not image_path:
            return jsonify({'success': False, 'error': '缺少必要参数'})
        ds_root = os.path.join(project_path, 'training', dataset_name)
        img_dir = os.path.join(ds_root, split, 'images')
        lbl_dir = os.path.join(ds_root, split, 'labels')
        auto_dir = os.path.join(ds_root, 'auto_labels', split)
        rel = os.path.relpath(image_path, img_dir)
        lbl_path = os.path.join(lbl_dir, os.path.splitext(rel)[0] + '.txt')
        auto_path = os.path.join(auto_dir, os.path.splitext(rel)[0] + '.txt')
        boxes = []
        auto_boxes = []
        from PIL import Image
        with Image.open(image_path) as im:
            w, h = im.size
        if os.path.exists(lbl_path):
            try:
                with open(lbl_path, 'r', encoding='utf-8') as f:
                    for line in f:
                        parts = line.strip().split()
                        if len(parts) >= 5:
                            cls = int(float(parts[0]))
                            cx = float(parts[1]) * w
                            cy = float(parts[2]) * h
                            ww = float(parts[3]) * w
                            hh = float(parts[4]) * h
                            x1 = max(0.0, cx - ww/2)
                            y1 = max(0.0, cy - hh/2)
                            x2 = min(float(w), cx + ww/2)
                            y2 = min(float(h), cy + hh/2)
                            boxes.append({'class': cls, 'x1': x1, 'y1': y1, 'x2': x2, 'y2': y2})
            except Exception:
                boxes = []
        if os.path.exists(auto_path):
            try:
                with open(auto_path, 'r', encoding='utf-8') as f:
                    for line in f:
                        parts = line.strip().split()
                        if len(parts) >= 5:
                            cls = int(float(parts[0]))
                            cx = float(parts[1]) * w
                            cy = float(parts[2]) * h
                            ww = float(parts[3]) * w
                            hh = float(parts[4]) * h
                            x1 = max(0.0, cx - ww/2)
                            y1 = max(0.0, cy - hh/2)
                            x2 = min(float(w), cx + ww/2)
                            y2 = min(float(h), cy + hh/2)
                            auto_boxes.append({'class': cls, 'x1': x1, 'y1': y1, 'x2': x2, 'y2': y2})
            except Exception:
                auto_boxes = []
        return jsonify({'success': True, 'boxes': boxes, 'auto_boxes': auto_boxes, 'width': w, 'height': h})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

# 上传图片扩充数据集
@app.route('/api/dataset/upload', methods=['POST'])
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

@app.route('/api/training/continue', methods=['POST'])
def api_training_continue():
    try:
        data = request.get_json()
        project_path = data.get('project_path')
        dataset_name = data.get('dataset_name', 'training')
        use_best = data.get('use_best', False)
        training_config = data.get('training_config', {})
        if not project_path:
            return jsonify({'success': False, 'error': '缺少项目路径'})
        result = TrainingManager.start_training_from_artifact(project_path, dataset_name, use_best, training_config)
        return jsonify(result)
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/training/resume', methods=['POST'])
def api_training_resume():
    try:
        data = request.get_json()
        project_path = data.get('project_path')
        dataset_name = data.get('dataset_name', 'training')
        if not project_path:
            return jsonify({'success': False, 'error': '缺少项目路径'})
        result = TrainingManager.resume_last_run(project_path, dataset_name)
        return jsonify(result)
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})
@app.route('/api/model/evaluate', methods=['POST'])
def api_model_evaluate():
    # Deprecated: use /api/model/evaluate/start
    return api_model_evaluate_start()

@app.route('/api/model/evaluate/start', methods=['POST'])
def api_model_evaluate_start():
    try:
        data = request.get_json() or {}
        project_path = data.get('project_path')
        split = data.get('split', 'val')
        if not project_path:
            return jsonify({'success': False, 'error': '缺少项目路径'})
            
        dataset_name = data.get('dataset_name')
        run_id = data.get('run_id') or data.get('training_id')
        
        if not dataset_name or not run_id:
            runs = TrainingManager.get_training_runs(project_path)
            if not runs:
                return jsonify({'success': False, 'error': '未找到训练记录'})
            # get_training_runs 已经按时间倒序排序
            latest = runs[0]
            dataset_name = latest['dataset']
            run_id = latest['training_id']
            
        result = TrainingManager.evaluate_model(project_path, dataset_name, run_id, split=split)
        return jsonify(result)
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/model/evaluate/status')
def api_model_evaluate_status():
    try:
        st = TrainingManager.get_evaluate_status()
        # 将路径转换为可访问 URL
        imgs = st.get('results', {}).get('images', [])
        st['results']['images'] = [f"/api/file?path={p}" for p in imgs]
        return jsonify({'success': True, 'status': st})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/dataset/validate', methods=['POST'])
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

   
@app.route('/api/training/runs')
def api_training_runs():
    try:
        project_path = request.args.get('project_path')
        dataset_name = request.args.get('dataset_name')
        if not project_path:
            return jsonify({'success': False, 'error': '缺少项目路径'})
        runs = TrainingManager.get_training_runs(project_path, dataset_name)
        return jsonify({'success': True, 'runs': runs})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/dataset/diagnose')
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
                
                # 推导 labels 目录
                labels_train = None
                if images_train:
                    p = images_train
                    # 1. 尝试替换 images 为 labels
                    maybe_lbl = p.replace(f'{os.sep}images{os.sep}', f'{os.sep}labels{os.sep}')
                    if maybe_lbl != p and os.path.exists(maybe_lbl):
                        labels_train = maybe_lbl
                    else:
                        # 2. 尝试替换结尾 images 为 labels
                        if p.endswith('images'):
                            maybe_lbl = p[:-6] + 'labels'
                            if os.path.exists(maybe_lbl):
                                labels_train = maybe_lbl
                
                if not labels_train:
                    # 3. 常见结构 Fallback
                    cand_a = os.path.join(base_path, 'labels', 'train')
                    if os.path.exists(cand_a):
                        labels_train = cand_a
                    else:
                        cand_b = os.path.join(base_path, 'train', 'labels')
                        if os.path.exists(cand_b):
                            labels_train = cand_b
                        else:
                            # 默认显示 labels/train 以提示缺失
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



 
# 将已复核的 auto_labels 合并到人工 labels
@app.route('/api/annotation/commit', methods=['POST'])
def api_annotation_commit():
    try:
        data = request.get_json() or {}
        project_path = data.get('project_path')
        dataset_name = data.get('dataset_name')
        split = data.get('split', 'train')
        image_path = data.get('image_path')
        if not project_path or not dataset_name or not image_path:
            return jsonify({'success': False, 'error': '缺少必要参数'})
        ds_root = os.path.join(project_path, 'training', dataset_name)
        img_dir = os.path.join(ds_root, split, 'images')
        manual_dir = os.path.join(ds_root, 'labels', split)
        auto_dir = os.path.join(ds_root, 'auto_labels', split)
        os.makedirs(manual_dir, exist_ok=True)
        os.makedirs(auto_dir, exist_ok=True)
        rel = os.path.relpath(image_path, img_dir)
        manual_lbl = os.path.join(manual_dir, os.path.splitext(rel)[0] + '.txt')
        auto_lbl = os.path.join(auto_dir, os.path.splitext(rel)[0] + '.txt')
        lines_manual = []
        lines_auto = []
        if os.path.exists(manual_lbl):
            try:
                with open(manual_lbl, 'r', encoding='utf-8') as f:
                    lines_manual = [ln.strip() for ln in f if ln.strip()]
            except Exception:
                lines_manual = []
        if os.path.exists(auto_lbl):
            try:
                with open(auto_lbl, 'r', encoding='utf-8') as f:
                    lines_auto = [ln.strip() for ln in f if ln.strip()]
            except Exception:
                lines_auto = []
        # 合并策略：人工优先，简单追加 auto 行（复核后提交）
        merged = lines_manual + lines_auto
        with open(manual_lbl, 'w', encoding='utf-8') as f:
            f.write('\n'.join(merged))
        # 提交后删除 auto 文件
        try:
            if os.path.exists(auto_lbl):
                os.remove(auto_lbl)
        except Exception:
            pass
        return jsonify({'success': True, 'label_path': manual_lbl})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/dataset/delete', methods=['POST'])
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
        if not image_rel and image_path:
            key = os.sep + split + os.sep + 'images' + os.sep
            pos = image_path.find(key)
            if pos >= 0:
                image_rel = image_path[pos+len(key):]
            else:
                # 退化为文件名
                image_rel = os.path.basename(image_path)
        if not image_rel:
            return jsonify({'success': False, 'error': '缺少必要参数'})
        img_path = os.path.join(img_dir, image_rel)
        lbl_path = os.path.join(lbl_dir, os.path.splitext(image_rel)[0] + '.txt')
        deleted = {'image': False, 'label': False}
        if os.path.exists(img_path):
            os.remove(img_path)
            deleted['image'] = True
        if os.path.exists(lbl_path):
            os.remove(lbl_path)
            deleted['label'] = True
        return jsonify({'success': True, 'deleted': deleted})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

 
# 批量自动标注进度状态
batch_status = {
    'is_running': False,
    'progress': 0,
    'message': ''
}

 
# 保存自动标注到 auto_labels（转 YOLO 归一化）
@app.route('/api/annotation/save_auto', methods=['POST'])
def api_annotation_save_auto():
    try:
        data = request.get_json() or {}
        project_path = data.get('project_path')
        dataset_name = data.get('dataset_name')
        split = data.get('split', 'train')
        image_path = data.get('image_path')
        labels = data.get('labels') or []
        if not project_path or not dataset_name or not image_path:
            return jsonify({'success': False, 'error': '缺少必要参数'})
        try:
            from PIL import Image
            with Image.open(image_path) as im:
                w, h = im.size
        except Exception:
            return jsonify({'success': False, 'error': '无法读取图片尺寸'})
        ds_root = os.path.join(project_path, 'training', dataset_name)
        img_dir = os.path.join(ds_root, split, 'images')
        auto_dir = os.path.join(ds_root, 'auto_labels', split)
        os.makedirs(auto_dir, exist_ok=True)
        rel = os.path.relpath(image_path, img_dir)
        lbl_path = os.path.join(auto_dir, os.path.splitext(rel)[0] + '.txt')
        lines = []
        for l in labels:
            cls = int(l.get('class', 0))
            x1, y1, x2, y2 = float(l['x1']), float(l['y1']), float(l['x2']), float(l['y2'])
            cx = ((x1 + x2) / 2.0) / w
            cy = ((y1 + y2) / 2.0) / h
            ww = (x2 - x1) / w
            hh = (y2 - y1) / h
            lines.append(f"{cls} {cx:.6f} {cy:.6f} {ww:.6f} {hh:.6f}")
        with open(lbl_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(lines))
        return jsonify({'success': True, 'label_path': lbl_path})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

 
>>>>>>> 2dc75e0 (feat)

if __name__ == '__main__':
    print("🎯 数据集工具启动中...")
    print("🌐 请在浏览器中打开: http://localhost:5001")
    
    # 检查 dist 目录是否存在
    dist_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'dist')
    if not os.path.exists(dist_dir):
        print(f"⚠️ 警告: 前端静态文件目录 {dist_dir} 不存在。")
        print("   请确保已运行前端构建 (cd frontend && npm run build) 并将产物复制到 src/web/dist")
    
    app.run(host='0.0.0.0', port=5001, debug=True)
